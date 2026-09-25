import json
from collections import Counter
from pathlib import Path

import numpy as np
from django.core.management.base import BaseCommand, CommandError

from researchdata.models import Opportunity


DEFAULT_RESEARCHERS = Path(
    "data/expertise/researcher_expertise_embeddings.json"
)
DEFAULT_ALL_EMBEDDINGS = Path(
    "data/embeddings/bge_m3_embeddings.json"
)
DEFAULT_BASELINE = Path(
    "data/embeddings/bge_m3_matches.json"
)
DEFAULT_OUTPUT = Path(
    "data/expertise/researcher_expertise_matches.json"
)


def normalize_matrix(vectors):
    matrix = np.asarray(vectors, dtype=np.float32)

    if matrix.ndim != 2:
        raise ValueError(f"Expected 2D matrix, got {matrix.shape}")
    if not np.isfinite(matrix).all():
        raise ValueError("Matrix contains non-finite values.")

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)

    if np.any(norms <= 0):
        raise ValueError("At least one vector has zero norm.")

    return matrix / norms


def top_frequency(top_map):
    counter = Counter()

    for matches in top_map.values():
        for match in matches:
            counter[str(match["opportunity_id"])] += 1

    return counter


class Command(BaseCommand):
    help = (
        "Compare reviewed researcher-expertise embeddings against the "
        "existing opportunity embeddings and optionally compare with the "
        "original baseline matches."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--researchers",
            default=str(DEFAULT_RESEARCHERS),
        )
        parser.add_argument(
            "--embeddings",
            default=str(DEFAULT_ALL_EMBEDDINGS),
        )
        parser.add_argument(
            "--baseline",
            default=str(DEFAULT_BASELINE),
        )
        parser.add_argument(
            "--output",
            default=str(DEFAULT_OUTPUT),
        )
        parser.add_argument(
            "--top-k",
            type=int,
            default=5,
        )

    def handle(self, *args, **options):
        researcher_path = Path(options["researchers"])
        embeddings_path = Path(options["embeddings"])
        baseline_path = Path(options["baseline"])
        output_path = Path(options["output"])
        top_k = options["top_k"]

        if not researcher_path.exists():
            raise CommandError(
                f"Researcher embedding file not found: {researcher_path}"
            )
        if not embeddings_path.exists():
            raise CommandError(
                f"Original embedding file not found: {embeddings_path}"
            )

        with researcher_path.open(encoding="utf-8") as f:
            researcher_data = json.load(f)

        with embeddings_path.open(encoding="utf-8") as f:
            all_embeddings = json.load(f)

        researchers = researcher_data["records"]
        opportunities = all_embeddings["records"]["opportunities"]

        researcher_ids = sorted(researchers)
        opportunity_ids = sorted(opportunities, key=int)

        r_matrix = normalize_matrix(
            [researchers[rid]["embedding"] for rid in researcher_ids]
        )
        o_matrix = normalize_matrix(
            [opportunities[oid]["embedding"] for oid in opportunity_ids]
        )

        if r_matrix.shape[1] != o_matrix.shape[1]:
            raise CommandError(
                "Researcher and opportunity vector dimensions differ."
            )

        similarities = r_matrix @ o_matrix.T

        opportunity_objects = Opportunity.objects.in_bulk(
            [int(oid) for oid in opportunity_ids]
        )

        missing_db_ids = [
            oid for oid in opportunity_ids
            if int(oid) not in opportunity_objects
        ]
        if missing_db_ids:
            raise CommandError(
                "Some opportunity IDs from the embeddings are missing "
                f"from MySQL: {missing_db_ids}"
            )

        matches = []
        top_map = {}

        for i, researcher_id in enumerate(researcher_ids):
            row = []

            for j, opportunity_id in enumerate(opportunity_ids):
                item = {
                    "researcher_id": researcher_id,
                    "researcher_name": researchers[
                        researcher_id
                    ]["researcher_name"],
                    "profile_strength": researchers[
                        researcher_id
                    ].get("profile_strength"),
                    "opportunity_id": int(opportunity_id),
                    "opportunity_title": opportunity_objects[
                        int(opportunity_id)
                    ].title,
                    "similarity": round(
                        float(similarities[i, j]), 6
                    ),
                }

                row.append(item)
                matches.append(item)

            row.sort(
                key=lambda item: item["similarity"],
                reverse=True,
            )
            top_map[researcher_id] = row[:top_k]

        if len(matches) != len(researcher_ids) * len(opportunity_ids):
            raise CommandError("Unexpected comparison count.")

        comparison = {
            "baseline_available": baseline_path.exists(),
        }

        new_frequency = top_frequency(top_map)

        comparison["new_top_opportunity_frequency"] = [
            {
                "opportunity_id": int(oid),
                "count": count,
            }
            for oid, count in new_frequency.most_common()
        ]

        if baseline_path.exists():
            with baseline_path.open(encoding="utf-8") as f:
                baseline = json.load(f)

            baseline_top = baseline.get("top_5_by_researcher", {})
            baseline_frequency = top_frequency(baseline_top)

            overlaps = {}
            overlap_counts = []

            for researcher_id in researcher_ids:
                new_ids = {
                    str(x["opportunity_id"])
                    for x in top_map[researcher_id]
                }
                old_ids = {
                    str(x["opportunity_id"])
                    for x in baseline_top.get(researcher_id, [])
                }

                overlap = len(new_ids & old_ids)
                overlaps[researcher_id] = overlap
                overlap_counts.append(overlap)

            comparison["top_k"] = top_k
            comparison["mean_top_k_overlap"] = round(
                float(np.mean(overlap_counts)), 3
            )
            comparison["per_researcher_top_k_overlap"] = overlaps
            comparison["baseline_top_opportunity_frequency"] = [
                {
                    "opportunity_id": int(oid),
                    "count": count,
                }
                for oid, count in baseline_frequency.most_common()
            ]

        output = {
            "model": researcher_data.get("model"),
            "metric": "cosine_similarity",
            "experiment": (
                "reviewed researcher expertise embeddings vs existing "
                "opportunity embeddings"
            ),
            "researcher_count": len(researcher_ids),
            "opportunity_count": len(opportunity_ids),
            "comparison_count": len(matches),
            "matches": matches,
            "top_5_by_researcher": top_map,
            "comparison_to_original_baseline": comparison,
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        self.stdout.write(
            self.style.SUCCESS(
                f"Saved {len(matches)} expertise-based comparisons "
                f"to {output_path}"
            )
        )

        self.stdout.write("\nSample top matches:")
        for researcher_id in researcher_ids[:3]:
            name = researchers[researcher_id]["researcher_name"]
            self.stdout.write(f"\n{name}")
            for match in top_map[researcher_id][:3]:
                self.stdout.write(
                    f"  {match['similarity']:.4f}  "
                    f"{match['opportunity_title']} "
                    f"(ID {match['opportunity_id']})"
                )

        self.stdout.write("\nMost frequent opportunities in new top-five lists:")
        for oid, count in new_frequency.most_common(5):
            title = opportunity_objects[int(oid)].title
            self.stdout.write(
                f"  {title} (ID {oid}): {count} researchers"
            )

        if baseline_path.exists():
            self.stdout.write(
                "\nMean number of top-five opportunities retained "
                f"from baseline: "
                f"{comparison['mean_top_k_overlap']:.2f} / {top_k}"
            )
