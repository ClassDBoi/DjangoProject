"""Suggest near-synonym keyword pairs using BGE-M3 without modifying MySQL.

Run:
    python manage.py review_semantic_pairs --dry-run
    python manage.py review_semantic_pairs

The output is candidate pairs for solo/group review. Do not automatically merge based
on cosine similarity. Script is READ only and does not write to the MySQL database
"""

import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from django.core.management.base import BaseCommand, CommandError
from researchdata.models import Researcher
from researchdata.management.commands.preview_researcher_expertise import collect_researchers


MODEL_NAME = "BAAI/bge-m3"


def normalize_title(value):
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return " ".join(re.sub(r"[^\w\s]", " ", value).split())


def possible_duplicate_titles(person):
    """Report equal normalized paper titles having different paper IDs."""
    groups = defaultdict(dict)
    for papers in person["terms"].values():
        for paper in papers.values():
            title = paper["paper_title"].strip()
            if title:
                groups[normalize_title(title)][paper["paper_id"]] = title
    return [
        {"title": next(iter(id_to_title.values())), "paper_ids": sorted(id_to_title, key=int)}
        for id_to_title in groups.values()
        if len(id_to_title) > 1
    ]


def choose_labels(person):
    """Map canonical phrases to a representative original keyword spelling."""
    result = {}
    for term, labels in person["labels"].items():
        result[term] = sorted(
            labels.items(), key=lambda entry: (-entry[1], len(entry[0]), entry[0].casefold())
        )[0][0]
    return result


def suggest_pairs(person, vectors, min_similarity):
    """Cosine-similar phrases within one researcher; no automatic consolidation."""
    terms = sorted(person["terms"])
    if len(terms) < 2:
        return []
    matrix = np.stack([vectors[term] for term in terms])
    similarities = matrix @ matrix.T
    labels = choose_labels(person)
    candidates = []
    for i, first in enumerate(terms):
        for j in range(i + 1, len(terms)):
            similarity = float(similarities[i, j])
            if similarity < min_similarity:
                continue
            second = terms[j]
            first_papers = person["terms"][first]
            second_papers = person["terms"][second]
            candidates.append({
                "term_a": labels[first],
                "term_b": labels[second],
                "canonical_a": first,
                "canonical_b": second,
                "similarity": round(similarity, 5),
                "support_a": len(first_papers),
                "support_b": len(second_papers),
                "shared_paper_count": len(first_papers.keys() & second_papers.keys()),
                "evidence_a": [
                    {"paper_id": paper["paper_id"], "paper_title": paper["paper_title"]}
                    for paper in sorted(first_papers.values(), key=lambda x: int(x["paper_id"]))
                ],
                "evidence_b": [
                    {"paper_id": paper["paper_id"], "paper_title": paper["paper_title"]}
                    for paper in sorted(second_papers.values(), key=lambda x: int(x["paper_id"]))
                ],
                "review_decision": None,  # same_topic / related_distinct / unrelated
            })
    candidates.sort(key=lambda item: (-item["similarity"], item["canonical_a"], item["canonical_b"]))
    return candidates


class Command(BaseCommand):
    help = "Identify BGE-M3 candidate keyword synonyms for manual expertise review; read-only MySQL."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Count all terms and flag duplicate titles; don't load model.")
        parser.add_argument("--min-similarity", type=float, default=0.86, help="Candidate cosine threshold (default: 0.86).")
        parser.add_argument("--sample", type=int, default=12, help="Number of highest-similarity examples to print.")
        parser.add_argument("--batch-size", type=int, default=16, help="CPU encoding batch size for short keyword phrases.")
        parser.add_argument("--output", default="data/expertise/semantic_review_candidates.json")

    def handle(self, *args, **options):
        threshold = options["min_similarity"]
        if not 0 < threshold < 1 or options["sample"] < 0 or options["batch_size"] < 1:
            raise CommandError("Require 0 < --min-similarity < 1, --sample >= 0, --batch-size >= 1")

        people = collect_researchers(
            Researcher.objects.prefetch_related("papers__keywords").order_by("auid")
        )
        unique_terms = sorted({term for person in people for term in person["terms"]})
        duplicates = [
            {"researcher": person["name"], **group}
            for person in people for group in possible_duplicate_titles(person)
        ]
        self.stdout.write(f"Read {len(people)} researchers and {len(unique_terms)} distinct keyword phrases from MySQL.")
        self.stdout.write(f"Found {len(duplicates)} possible duplicate-title groups (check paper IDs before merging).")
        for group in duplicates[:10]:
            self.stdout.write(f"  {group['researcher']}: {group['paper_ids']} — {group['title']}")
        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("Dry run passed; model not loaded; no MySQL changes or output file."))
            return

        from FlagEmbedding import BGEM3FlagModel

        self.stdout.write("Loading BGE-M3 on CPU to encode unique keyword phrases...")
        model = BGEM3FlagModel(MODEL_NAME, use_fp16=False, devices=["cpu"])
        data = model.encode(
            unique_terms,
            batch_size=options["batch_size"],
            max_length=64,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        matrix = np.asarray(data["dense_vecs"], dtype=np.float32)
        if matrix.shape != (len(unique_terms), 1024) or not np.isfinite(matrix).all():
            raise CommandError(f"Unexpected embedding shape or nonfinite values: {matrix.shape}")
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        if not np.all(norms > 0):
            raise CommandError("Zero-magnitude embeddings found")
        matrix /= norms
        vectors = dict(zip(unique_terms, matrix))

        results = []
        all_candidates = []
        for person in people:
            proposals = suggest_pairs(person, vectors, threshold)
            results.append({
                "researcher_id": person["id"],
                "researcher_name": person["name"],
                "unique_keyword_count": len(person["terms"]),
                "duplicate_titles": possible_duplicate_titles(person),
                "candidates": proposals,
            })
            for pair in proposals:
                all_candidates.append((pair["similarity"], person["name"], pair))
        all_candidates.sort(key=lambda x: -x[0])
        result = {
            "method": "BGE-M3 semantic candidate retrieval for researcher keyword pairs",
            "model": MODEL_NAME,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "minimum_similarity": threshold,
            "candidate_only": True,
            "review_labels": ["same_topic", "related_distinct", "unrelated"],
            "warning": "A high cosine score does not establish synonymy. Human review is mandatory. No database changes have been made.",
            "total_researchers": len(people),
            "unique_keyword_phrases": len(unique_terms),
            "candidate_pair_count": len(all_candidates),
            "possible_duplicate_title_count": len(duplicates),
            "researchers": results,
        }
        output = Path(options["output"])
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + ".tmp")
        with temp.open("w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, allow_nan=False)
        temp.replace(output)
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(all_candidates)} candidate pairs to {output}. No MySQL changes."))
        for similarity, name, pair in all_candidates[:options["sample"]]:
            self.stdout.write(f"  {name}: {pair['term_a']} ↔ {pair['term_b']} ({similarity:.4f})")
