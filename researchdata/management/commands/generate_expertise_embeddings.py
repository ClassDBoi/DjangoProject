import hashlib
import json
import math
from pathlib import Path

import numpy as np
import torch
from django.core.management.base import BaseCommand, CommandError
from FlagEmbedding import BGEM3FlagModel


DEFAULT_INPUT = Path("data/expertise/researcher_expertise_reviewed.json")
DEFAULT_OUTPUT = Path("data/expertise/researcher_expertise_embeddings.json")


def build_expertise_text(researcher):
    """
    Build a concise, focused representation of researcher expertise.

    For normal profiles, use recurring topics only.
    For limited-evidence profiles, fall back to the top five ranked topics.
    """
    recurring = researcher.get("recurring_topics", [])

    if recurring:
        topics = [topic["topic"] for topic in recurring]
        basis = "recurring_topics"
    else:
        ranked = researcher.get("all_ranked_topics", [])
        topics = [topic["topic"] for topic in ranked[:5]]
        basis = "limited_evidence_fallback"

    if not topics:
        raise ValueError(
            f"No usable expertise topics for researcher "
            f"{researcher.get('researcher_id')}"
        )

    # Do not include the researcher's name. The vector should represent
    # subject-matter expertise, not identity.
    text = "Research expertise: " + "; ".join(topics) + "."

    return text, topics, basis


class Command(BaseCommand):
    help = (
        "Generate BGE-M3 embeddings from reviewed researcher expertise "
        "profiles without modifying the database."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--input",
            default=str(DEFAULT_INPUT),
            help=f"Reviewed expertise JSON (default: {DEFAULT_INPUT})",
        )
        parser.add_argument(
            "--output",
            default=str(DEFAULT_OUTPUT),
            help=f"Output JSON (default: {DEFAULT_OUTPUT})",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=2,
            help="BGE-M3 batch size (default: 2)",
        )
        parser.add_argument(
            "--max-length",
            type=int,
            default=256,
            help="Maximum BGE-M3 input length (default: 256)",
        )
        parser.add_argument(
            "--threads",
            type=int,
            default=8,
            help="PyTorch CPU threads (default: 8)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Build and display texts without loading BGE-M3.",
        )

    def handle(self, *args, **options):
        input_path = Path(options["input"])
        output_path = Path(options["output"])

        if not input_path.exists():
            raise CommandError(f"Input file not found: {input_path}")

        with input_path.open(encoding="utf-8") as f:
            source = json.load(f)

        researchers = source.get("researchers", [])
        if not researchers:
            raise CommandError("No researchers found in reviewed expertise file.")

        prepared = []
        for researcher in sorted(
            researchers, key=lambda r: str(r["researcher_id"])
        ):
            text, topics, basis = build_expertise_text(researcher)

            prepared.append(
                {
                    "researcher_id": str(researcher["researcher_id"]),
                    "researcher_name": researcher["researcher_name"],
                    "profile_strength": researcher.get("profile_strength"),
                    "basis": basis,
                    "topics": topics,
                    "embedding_text": text,
                    "text_sha256": hashlib.sha256(
                        text.encode("utf-8")
                    ).hexdigest(),
                }
            )

        if len(prepared) != source.get("researcher_count", len(prepared)):
            raise CommandError(
                "Researcher count does not match source metadata."
            )

        limited = [
            r for r in prepared
            if r["basis"] == "limited_evidence_fallback"
        ]

        self.stdout.write(
            f"Prepared {len(prepared)} researcher expertise texts."
        )
        self.stdout.write(
            f"Recurring-topic profiles: {len(prepared) - len(limited)}"
        )
        self.stdout.write(
            f"Limited-evidence fallbacks: {len(limited)}"
        )

        for record in prepared[:5]:
            self.stdout.write(
                f"\n{record['researcher_name']} "
                f"({record['researcher_id']})"
            )
            self.stdout.write(f"  {record['embedding_text']}")

        if limited:
            self.stdout.write("\nLimited-evidence researchers:")
            for record in limited:
                self.stdout.write(
                    f"  {record['researcher_name']}: "
                    f"{record['embedding_text']}"
                )

        if options["dry_run"]:
            self.stdout.write(
                self.style.SUCCESS(
                    "\nDry run passed: no model loaded and no output written."
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
            f"Longest researcher expertise input: {longest} tokens"
        )

        if longest > options["max_length"]:
            raise CommandError(
                f"At least one input exceeds --max-length "
                f"{options['max_length']}; longest is {longest}."
            )

        self.stdout.write(
            f"Encoding {len(texts)} researcher expertise profiles..."
        )

        result = model.encode(
            texts,
            batch_size=options["batch_size"],
            max_length=options["max_length"],
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )

        vectors = np.asarray(result["dense_vecs"], dtype=np.float32)

        if vectors.ndim != 2:
            raise CommandError(
                f"Unexpected embedding array shape: {vectors.shape}"
            )
        if vectors.shape[0] != len(prepared):
            raise CommandError(
                "Embedding row count does not match researcher count."
            )
        if vectors.shape[1] != 1024:
            raise CommandError(
                f"Expected 1024 dimensions, got {vectors.shape[1]}."
            )
        if not np.isfinite(vectors).all():
            raise CommandError("Embedding array contains non-finite values.")

        records = {}

        for record, vector, token_count in zip(
            prepared, vectors, token_counts
        ):
            norm = float(np.linalg.norm(vector))
            if not math.isfinite(norm) or norm <= 0:
                raise CommandError(
                    f"Invalid vector norm for "
                    f"{record['researcher_id']}: {norm}"
                )

            records[record["researcher_id"]] = {
                **record,
                "token_count": int(token_count),
                "dimensions": int(vector.shape[0]),
                "vector_norm": round(norm, 8),
                "embedding": vector.tolist(),
            }

        output = {
            "model": "BAAI/bge-m3",
            "method": (
                "reviewed researcher expertise topics -> BGE-M3 dense embedding"
            ),
            "dimensions": 1024,
            "dtype": "float32",
            "max_length": options["max_length"],
            "batch_size": options["batch_size"],
            "researcher_count": len(records),
            "limited_evidence_researcher_ids": [
                r["researcher_id"] for r in limited
            ],
            "source_decision_summary": source.get("decision_summary"),
            "source_duplicate_paper_policy": source.get(
                "duplicate_paper_policy"
            ),
            "records": records,
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSaved {len(records)} researcher expertise embeddings "
                f"to {output_path}"
            )
        )
