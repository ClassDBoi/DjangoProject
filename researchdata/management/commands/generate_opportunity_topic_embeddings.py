import hashlib
import json
import math
from pathlib import Path

import numpy as np
import torch
from django.core.management.base import BaseCommand, CommandError
from FlagEmbedding import BGEM3FlagModel


DEFAULT_INPUT = Path(
    "data/opportunity_topics/approved_opportunity_topics.json"
)
DEFAULT_OUTPUT = Path(
    "data/opportunity_topics/opportunity_topic_embeddings.json"
)


def build_topic_text(record):
    topics = record.get("approved_topics", [])
    if not topics:
        raise ValueError(
            f"No approved subject topics for opportunity "
            f"{record.get('opportunity_id')}"
        )

    # Deliberately exclude raw title, description, and approved_metadata.
    # This vector represents only the reviewed scientific/academic subjects.
    return "Opportunity subject areas: " + "; ".join(topics) + "."


class Command(BaseCommand):
    help = (
        "Generate BGE-M3 vectors for approved opportunity subject topics. "
        "Only opportunities enabled for semantic matching are embedded. "
        "No database writes are performed."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--input",
            default=str(DEFAULT_INPUT),
        )
        parser.add_argument(
            "--output",
            default=str(DEFAULT_OUTPUT),
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=4,
        )
        parser.add_argument(
            "--max-length",
            type=int,
            default=256,
        )
        parser.add_argument(
            "--threads",
            type=int,
            default=8,
        )
        parser.add_argument(
            "--sample",
            type=int,
            default=8,
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
        )

    def handle(self, *args, **options):
        input_path = Path(options["input"])
        output_path = Path(options["output"])

        if not input_path.exists():
            raise CommandError(f"Input file not found: {input_path}")

        with input_path.open(encoding="utf-8") as f:
            source = json.load(f)

        records = source.get("records", {})
        if not records:
            raise CommandError("No opportunity records found.")

        prepared = []

        for oid, record in sorted(
            records.items(), key=lambda item: int(item[0])
        ):
            if not record.get("semantic_matching_enabled"):
                continue

            text = build_topic_text(record)

            prepared.append(
                {
                    "opportunity_id": int(oid),
                    "title": record["title"],
                    "review_scope": record["review_scope"],
                    "matching_action": record["matching_action"],
                    "approved_topics": record["approved_topics"],
                    "approved_metadata": record.get(
                        "approved_metadata", []
                    ),
                    "embedding_text": text,
                    "text_sha256": hashlib.sha256(
                        text.encode("utf-8")
                    ).hexdigest(),
                }
            )

        expected = int(source.get("semantic_matching_count", -1))
        if expected != len(prepared):
            raise CommandError(
                f"Expected {expected} semantic opportunities, "
                f"prepared {len(prepared)}."
            )

        self.stdout.write(
            f"Prepared {len(prepared)} approved opportunity topic texts."
        )
        self.stdout.write(
            f"Excluded from semantic ranking: "
            f"{source.get('separate_filter_or_manual_count', 0)} "
            f"separate/manual + "
            f"{source.get('insufficient_source_count', 0)} "
            f"insufficient-source."
        )

        for record in prepared[: options["sample"]]:
            self.stdout.write(
                f"\n{record['opportunity_id']} — {record['title']}"
            )
            self.stdout.write(
                f"  {record['embedding_text']}"
            )
            if record["approved_metadata"]:
                self.stdout.write(
                    "  metadata kept outside embedding: "
                    + "; ".join(record["approved_metadata"])
                )

        if options["dry_run"]:
            self.stdout.write(
                self.style.SUCCESS(
                    "\nDry run passed: no model loaded, "
                    "no database changes, no output written."
                )
            )
            return

        torch.set_num_threads(options["threads"])

        self.stdout.write("\nLoading BGE-M3 on CPU (FP32)...")
        model = BGEM3FlagModel(
            "BAAI/bge-m3",
            use_fp16=False,
            devices=["cpu"],
        )

        texts = [record["embedding_text"] for record in prepared]
        token_counts = [
            len(
                model.tokenizer(
                    text,
                    truncation=False,
                    add_special_tokens=True,
                )["input_ids"]
            )
            for text in texts
        ]

        longest = max(token_counts)
        self.stdout.write(
            f"Longest opportunity topic input: {longest} tokens"
        )

        if longest > options["max_length"]:
            raise CommandError(
                f"Input exceeds --max-length: {longest}"
            )

        result = model.encode(
            texts,
            batch_size=options["batch_size"],
            max_length=options["max_length"],
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )

        vectors = np.asarray(
            result["dense_vecs"], dtype=np.float32
        )

        if vectors.ndim != 2:
            raise CommandError(
                f"Unexpected embedding shape: {vectors.shape}"
            )
        if vectors.shape[0] != len(prepared):
            raise CommandError(
                "Embedding count does not match opportunity count."
            )
        if vectors.shape[1] != 1024:
            raise CommandError(
                f"Expected 1024 dimensions, got {vectors.shape[1]}."
            )
        if not np.isfinite(vectors).all():
            raise CommandError(
                "Embedding array contains non-finite values."
            )

        output_records = {}

        for record, vector, token_count in zip(
            prepared, vectors, token_counts
        ):
            norm = float(np.linalg.norm(vector))
            if not math.isfinite(norm) or norm <= 0:
                raise CommandError(
                    f"Invalid vector norm for opportunity "
                    f"{record['opportunity_id']}: {norm}"
                )

            output_records[str(record["opportunity_id"])] = {
                **record,
                "token_count": int(token_count),
                "dimensions": int(vector.shape[0]),
                "vector_norm": round(norm, 8),
                "embedding": vector.tolist(),
            }

        output = {
            "model": "BAAI/bge-m3",
            "method": (
                "approved opportunity subject topics -> "
                "BGE-M3 dense embedding"
            ),
            "comparison_normalizes_vectors": True,
            "dimensions": 1024,
            "dtype": "float32",
            "opportunity_count": len(output_records),
            "excluded_opportunity_ids": [
                int(oid)
                for oid, record in records.items()
                if not record.get("semantic_matching_enabled")
            ],
            "records": output_records,
        }

        output_path.parent.mkdir(
            parents=True, exist_ok=True
        )
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(
                output,
                f,
                indent=2,
                ensure_ascii=False,
                allow_nan=False,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSaved {len(output_records)} opportunity topic "
                f"embeddings to {output_path}"
            )
        )
