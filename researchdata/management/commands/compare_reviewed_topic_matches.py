import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from django.core.management.base import BaseCommand, CommandError


DEFAULT_RESEARCHERS = Path(
    "data/expertise/researcher_expertise_embeddings.json"
)
DEFAULT_OPPORTUNITIES = Path(
    "data/opportunity_topics/opportunity_topic_embeddings.json"
)
DEFAULT_APPROVED = Path(
    "data/opportunity_topics/approved_opportunity_topics.json"
)
DEFAULT_EXPERIMENT2 = Path(
    "data/expertise/researcher_expertise_matches.json"
)
DEFAULT_BASELINE = Path(
    "data/embeddings/bge_m3_matches.json"
)
DEFAULT_OUTPUT = Path(
    "data/opportunity_topics/reviewed_topic_matches.json"
)


def normalize_matrix(vectors):
    matrix = np.asarray(vectors, dtype=np.float32)
    if matrix.ndim != 2:
        raise ValueError(
            f"Expected a 2D matrix, got {matrix.shape}"
        )
    if not np.isfinite(matrix).all():
        raise ValueError("Matrix contains non-finite values.")

    norms = np.linalg.norm(
        matrix, axis=1, keepdims=True
    )
    if np.any(norms <= 0):
        raise ValueError("Encountered zero-norm vector.")

    return matrix / norms


def group_and_rank(matches, eligible_ids, top_k):
    eligible_ids = {int(x) for x in eligible_ids}
    grouped = defaultdict(list)

    for match in matches:
        oid = int(match["opportunity_id"])
        if oid not in eligible_ids:
            continue

        grouped[str(match["researcher_id"])].append(
            {
                **match,
                "opportunity_id": oid,
                "similarity": float(match["similarity"]),
            }
        )

    result = {}
    for researcher_id, rows in grouped.items():
        rows.sort(
            key=lambda x: x["similarity"],
            reverse=True,
        )
        result[researcher_id] = rows[:top_k]

    return result


def frequency(top_map):
    counter = Counter()
    for rows in top_map.values():
        for row in rows:
            counter[int(row["opportunity_id"])] += 1
    return counter


def overlap_stats(current, comparison, researcher_ids):
    per_researcher = {}
    counts = []

    for researcher_id in researcher_ids:
        a = {
            int(x["opportunity_id"])
            for x in current.get(researcher_id, [])
        }
        b = {
            int(x["opportunity_id"])
            for x in comparison.get(researcher_id, [])
        }
        count = len(a & b)
        per_researcher[researcher_id] = count
        counts.append(count)

    return {
        "mean_top_k_overlap": round(
            float(np.mean(counts)), 3
        ),
        "per_researcher_top_k_overlap": per_researcher,
    }


def frequency_rows(counter, approved_records):
    rows = []
    for oid, count in counter.most_common():
        rows.append(
            {
                "opportunity_id": int(oid),
                "opportunity_title": approved_records[
                    str(oid)
                ]["title"],
                "count": int(count),
            }
        )
    return rows


class Command(BaseCommand):
    help = (
        "Experiment 3: compare reviewed researcher expertise vectors "
        "against reviewed opportunity-topic vectors. Baseline and "
        "Experiment 2 are re-ranked over the SAME semantic-eligible "
        "opportunity pool for a fair comparison."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--researchers",
            default=str(DEFAULT_RESEARCHERS),
        )
        parser.add_argument(
            "--opportunities",
            default=str(DEFAULT_OPPORTUNITIES),
        )
        parser.add_argument(
            "--approved",
            default=str(DEFAULT_APPROVED),
        )
        parser.add_argument(
            "--experiment2",
            default=str(DEFAULT_EXPERIMENT2),
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
        paths = {
            "researchers": Path(options["researchers"]),
            "opportunities": Path(options["opportunities"]),
            "approved": Path(options["approved"]),
        }

        for label, path in paths.items():
            if not path.exists():
                raise CommandError(
                    f"{label} file not found: {path}"
                )

        with paths["researchers"].open(
            encoding="utf-8"
        ) as f:
            researcher_data = json.load(f)

        with paths["opportunities"].open(
            encoding="utf-8"
        ) as f:
            opportunity_data = json.load(f)

        with paths["approved"].open(
            encoding="utf-8"
        ) as f:
            approved = json.load(f)

        researcher_records = researcher_data["records"]
        opportunity_records = opportunity_data["records"]
        approved_records = approved["records"]

        researcher_ids = sorted(researcher_records)
        opportunity_ids = sorted(
            opportunity_records, key=int
        )
        eligible_ids = [int(x) for x in opportunity_ids]

        expected = sorted(
            approved["semantic_matching_opportunity_ids"]
        )
        if sorted(eligible_ids) != expected:
            raise CommandError(
                "Opportunity embedding IDs do not match the "
                "approved semantic-matching pool."
            )

        r_matrix = normalize_matrix(
            [
                researcher_records[rid]["embedding"]
                for rid in researcher_ids
            ]
        )
        o_matrix = normalize_matrix(
            [
                opportunity_records[oid]["embedding"]
                for oid in opportunity_ids
            ]
        )

        if r_matrix.shape[1] != o_matrix.shape[1]:
            raise CommandError(
                "Researcher and opportunity vector dimensions differ."
            )

        similarities = r_matrix @ o_matrix.T

        matches = []
        top_map = {}

        for i, researcher_id in enumerate(researcher_ids):
            rows = []
            for j, opportunity_id in enumerate(
                opportunity_ids
            ):
                oid = int(opportunity_id)
                item = {
                    "researcher_id": researcher_id,
                    "researcher_name": researcher_records[
                        researcher_id
                    ]["researcher_name"],
                    "profile_strength": researcher_records[
                        researcher_id
                    ].get("profile_strength"),
                    "opportunity_id": oid,
                    "opportunity_title": approved_records[
                        str(oid)
                    ]["title"],
                    "opportunity_topics": approved_records[
                        str(oid)
                    ]["approved_topics"],
                    "similarity": round(
                        float(similarities[i, j]), 6
                    ),
                }
                rows.append(item)
                matches.append(item)

            rows.sort(
                key=lambda x: x["similarity"],
                reverse=True,
            )
            top_map[researcher_id] = rows[
                : options["top_k"]
            ]

        expected_pairs = (
            len(researcher_ids) * len(opportunity_ids)
        )
        if len(matches) != expected_pairs:
            raise CommandError(
                "Unexpected comparison count."
            )

        scores = np.asarray(
            [m["similarity"] for m in matches],
            dtype=np.float32,
        )

        current_freq = frequency(top_map)

        comparison = {
            "comparison_pool_note": (
                "All historical experiments are re-ranked over "
                "the same reviewed semantic-eligible opportunity "
                "pool before overlap/frequency comparison."
            ),
            "eligible_opportunity_count": len(eligible_ids),
            "eligible_opportunity_ids": eligible_ids,
            "experiment3_frequency": frequency_rows(
                current_freq, approved_records
            ),
        }

        experiment2_path = Path(options["experiment2"])
        if experiment2_path.exists():
            with experiment2_path.open(
                encoding="utf-8"
            ) as f:
                experiment2 = json.load(f)

            exp2_top = group_and_rank(
                experiment2["matches"],
                eligible_ids,
                options["top_k"],
            )
            comparison["experiment2"] = {
                **overlap_stats(
                    top_map,
                    exp2_top,
                    researcher_ids,
                ),
                "frequency": frequency_rows(
                    frequency(exp2_top),
                    approved_records,
                ),
            }
        else:
            comparison["experiment2"] = {
                "available": False
            }

        baseline_path = Path(options["baseline"])
        if baseline_path.exists():
            with baseline_path.open(
                encoding="utf-8"
            ) as f:
                baseline = json.load(f)

            baseline_top = group_and_rank(
                baseline["matches"],
                eligible_ids,
                options["top_k"],
            )
            comparison["baseline"] = {
                **overlap_stats(
                    top_map,
                    baseline_top,
                    researcher_ids,
                ),
                "frequency": frequency_rows(
                    frequency(baseline_top),
                    approved_records,
                ),
            }
        else:
            comparison["baseline"] = {
                "available": False
            }

        output = {
            "model": opportunity_data.get(
                "model", "BAAI/bge-m3"
            ),
            "metric": "cosine_similarity",
            "experiment": (
                "Experiment 3: reviewed researcher expertise "
                "vs reviewed opportunity subject topics"
            ),
            "researcher_count": len(researcher_ids),
            "semantic_opportunity_count": len(
                opportunity_ids
            ),
            "comparison_count": len(matches),
            "excluded_opportunities": [
                {
                    "opportunity_id": rec[
                        "opportunity_id"
                    ],
                    "title": rec["title"],
                    "review_scope": rec["review_scope"],
                    "matching_action": rec[
                        "matching_action"
                    ],
                }
                for rec in approved_records.values()
                if not rec[
                    "semantic_matching_enabled"
                ]
            ],
            "score_distribution": {
                "min": round(float(scores.min()), 6),
                "mean": round(float(scores.mean()), 6),
                "median": round(
                    float(np.median(scores)), 6
                ),
                "max": round(float(scores.max()), 6),
            },
            "matches": matches,
            "top_5_by_researcher": top_map,
            "comparison_to_previous_experiments": comparison,
        }

        output_path = Path(options["output"])
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
                f"Saved {len(matches)} Experiment 3 "
                f"comparisons to {output_path}"
            )
        )

        self.stdout.write(
            f"\nSemantic opportunity pool: "
            f"{len(opportunity_ids)} of "
            f"{approved['opportunity_count']}"
        )
        self.stdout.write(
            f"Comparisons: {len(researcher_ids)} x "
            f"{len(opportunity_ids)} = {len(matches)}"
        )

        self.stdout.write(
            "\nMost frequent Experiment 3 top-five opportunities:"
        )
        for row in comparison[
            "experiment3_frequency"
        ][:8]:
            self.stdout.write(
                f"  {row['count']:>2}  "
                f"{row['opportunity_title']} "
                f"(ID {row['opportunity_id']})"
            )

        if "mean_top_k_overlap" in comparison.get(
            "experiment2", {}
        ):
            self.stdout.write(
                "\nMean top-five overlap with Experiment 2 "
                f"(same 16-opportunity pool): "
                f"{comparison['experiment2']['mean_top_k_overlap']:.2f} / "
                f"{options['top_k']}"
            )

        if "mean_top_k_overlap" in comparison.get(
            "baseline", {}
        ):
            self.stdout.write(
                "Mean top-five overlap with original baseline "
                f"(same 16-opportunity pool): "
                f"{comparison['baseline']['mean_top_k_overlap']:.2f} / "
                f"{options['top_k']}"
            )

        self.stdout.write(
            "\nScore distribution: "
            f"min={output['score_distribution']['min']:.4f}, "
            f"mean={output['score_distribution']['mean']:.4f}, "
            f"median={output['score_distribution']['median']:.4f}, "
            f"max={output['score_distribution']['max']:.4f}"
        )
