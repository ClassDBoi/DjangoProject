"""Django command: export BGE-M3 dense embeddings without changing MySQL.

Examples:
    python manage.py generate_embeddings --dry-run
    python manage.py generate_embeddings --limit 2 --output data/embeddings/bge_m3_preview.json
    python manage.py generate_embeddings
"""

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand, CommandError
from transformers import AutoTokenizer

from researchdata.models import Opportunity, Paper, Researcher

MODEL_NAME = "BAAI/bge-m3"
VECTOR_DIMENSION = 1024


def clean_text(value):
    """Remove HTML and normalize whitespace, leaving the original DB unchanged."""
    soup = BeautifulSoup(str(value or ""), "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def keyword_text(paper):
    """Use keyword phrases in decreasing source score; don't embed numeric scores."""
    keywords = sorted(
        paper.keywords.all(),
        key=lambda item: (-item.score, item.keyword.casefold()),
    )
    return "; ".join(item.keyword for item in keywords if item.keyword)


def paper_input(paper):
    parts = [f"Paper title: {clean_text(paper.title)}"]
    phrases = keyword_text(paper)
    if phrases:
        parts.append(f"Keywords: {phrases}")
    abstract = clean_text(getattr(paper, "abstract", ""))
    if abstract:
        parts.append(f"Abstract: {abstract}")
    return "\n".join(parts)


def researcher_input(researcher):
    parts = [f"Researcher: {clean_text(researcher.name)}", "Research publications:"]
    for paper in sorted(researcher.papers.all(), key=lambda item: item.id):
        title = clean_text(paper.title)
        phrases = keyword_text(paper)
        parts.append(f"- {title}" + (f"; keywords: {phrases}" if phrases else ""))
    return "\n".join(parts)


def opportunity_input(opportunity):
    # Prefer imported cleaned text when present; also handle older imported rows.
    description = clean_text(
        getattr(opportunity, "clean_description", "") or opportunity.description
    )
    return f"Opportunity title: {clean_text(opportunity.title)}\nDescription: {description}"


class Command(BaseCommand):
    help = "Generate CPU-based BGE-M3 embeddings for researchers, papers, and opportunities. Read-only DB access."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output", default="data/embeddings/bge_m3_embeddings.json",
            help="JSON output path (relative to manage.py unless absolute)",
        )
        parser.add_argument("--batch-size", type=int, default=2)
        parser.add_argument("--max-length", type=int, default=1536)
        parser.add_argument("--cpu-threads", type=int, default=8)
        parser.add_argument(
            "--limit", type=int, default=0,
            help="Use at most N records per type (0 = all); useful for a preview",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Build input texts and check BGE-M3 token lengths without loading model or writing output",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        max_length = options["max_length"]
        cpu_threads = options["cpu_threads"]
        limit = options["limit"]
        if batch_size < 1 or cpu_threads < 1 or limit < 0:
            raise CommandError("Batch size and CPU threads must be >= 1; limit must be >= 0.")
        if not 1 <= max_length <= 8192:
            raise CommandError("--max-length must be between 1 and BGE-M3's 8192-token limit.")

        # Prefetch keywords/publications once rather than running SQL per record.
        paper_objects = list(Paper.objects.prefetch_related("keywords").order_by("id"))
        researcher_objects = list(
            Researcher.objects.prefetch_related("papers__keywords").order_by("auid")
        )
        opportunity_objects = list(Opportunity.objects.order_by("opp_id"))
        if limit:
            paper_objects = paper_objects[:limit]
            researcher_objects = researcher_objects[:limit]
            opportunity_objects = opportunity_objects[:limit]

        records = {
            "papers": [{"id": str(p.id), "text": paper_input(p)} for p in paper_objects],
            "researchers": [
                {"id": str(r.auid), "text": researcher_input(r)}
                for r in researcher_objects
            ],
            "opportunities": [
                {"id": str(o.opp_id), "text": opportunity_input(o)}
                for o in opportunity_objects
            ],
        }
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        max_observed = {}
        for record_type, group in records.items():
            longest = 0
            for record in group:
                token_count = len(
                    tokenizer(record["text"], truncation=False, add_special_tokens=True)["input_ids"]
                )
                record["tokens"] = token_count
                longest = max(longest, token_count)
                if token_count > max_length:
                    raise CommandError(
                        f"{record_type} {record['id']} requires {token_count} tokens "
                        f"but --max-length={max_length}. Increase the limit or "
                        "change the input preparation; refusing silent truncation."
                    )
            max_observed[record_type] = longest
            self.stdout.write(f"{record_type}: {len(group)} records; longest {longest} tokens")

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("Dry run passed: no model loaded or output written."))
            return

        # Load the model only after the full token-length validation passes.
        import torch
        from FlagEmbedding import BGEM3FlagModel

        torch.set_num_threads(min(cpu_threads, os.cpu_count() or cpu_threads))
        self.stdout.write("Loading BGE-M3 on CPU (FP32)...")
        model = BGEM3FlagModel(MODEL_NAME, use_fp16=False, devices=["cpu"])
        exported = {}
        for record_type, group in records.items():
            self.stdout.write(f"Encoding {len(group)} {record_type}...")
            if not group:
                exported[record_type] = {}
                continue
            result = model.encode(
                [record["text"] for record in group],
                batch_size=batch_size,
                max_length=max_length,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False,
            )
            vectors = np.asarray(result["dense_vecs"], dtype=np.float32)
            expected_shape = (len(group), VECTOR_DIMENSION)
            if vectors.shape != expected_shape or not np.isfinite(vectors).all():
                raise CommandError(
                    f"Unexpected or nonfinite vectors for {record_type}: "
                    f"got {vectors.shape}; expected {expected_shape}."
                )
            # BGE-M3 normally produces normalized vectors; make it explicit for cosine similarity.
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            if (norms == 0).any():
                raise CommandError(f"Zero-length vector found in {record_type}.")
            vectors = vectors / norms
            exported[record_type] = {
                record["id"]: {
                    "input_sha256": hashlib.sha256(record["text"].encode("utf-8")).hexdigest(),
                    "token_count": record["tokens"],
                    "embedding": vector.tolist(),
                }
                for record, vector in zip(group, vectors)
            }
            self.stdout.write(self.style.SUCCESS(f"Finished {record_type}."))

        payload = {
            "model": MODEL_NAME,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "dimension": VECTOR_DIMENSION,
            "normalized": True,
            "max_length": max_length,
            "input_fields": {
                "papers": "title, scored keyword phrases (ordered by score), optional abstract",
                "researchers": "researcher name and associated paper titles/keyword phrases",
                "opportunities": "title and HTML-cleaned description",
            },
            "record_counts": {kind: len(entries) for kind, entries in exported.items()},
            "max_observed_tokens": max_observed,
            "records": exported,
        }
        output_path = Path(options["output"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        temp_path.replace(output_path)
        self.stdout.write(self.style.SUCCESS(f"Saved {sum(payload['record_counts'].values())} embeddings to {output_path}"))
