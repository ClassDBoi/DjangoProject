from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import platform
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from benchmark_io import load_benchmark, sha256_file, unique_phrases
from metrics import evaluate_scores, rank_disagreement_rows
from model_registry import encode_model, load_model_configs

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BENCHMARK = ROOT / "data" / "human_semantic_benchmark.csv"
DEFAULT_MODELS = ROOT / "config" / "models.json"
DEFAULT_RESULTS = ROOT / "results"


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    if not rows:
        return
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def make_plots(run_dir: Path, rows: list[dict], score_columns: dict[str, np.ndarray]) -> None:
    import matplotlib.pyplot as plt

    figures = run_dir / "figures"
    figures.mkdir(exist_ok=True)
    human = np.asarray([row["human_score"] for row in rows], dtype=float)

    for model_key, scores in score_columns.items():
        fig, ax = plt.subplots(figsize=(7.5, 5.0))
        ax.scatter(human, scores, alpha=0.72)
        ax.set(
            title=f"Human rating vs. model cosine — {model_key}",
            xlabel="Human semantic similarity (1-5)",
            ylabel="Cosine similarity",
            xticks=[1, 2, 3, 4, 5],
        )
        ax.grid(alpha=0.2)
        fig.tight_layout()
        fig.savefig(figures / f"human_vs_{model_key}.png", dpi=150)
        plt.close(fig)

    keys = list(score_columns)
    matrix = np.corrcoef([score_columns[key] for key in keys])
    fig, ax = plt.subplots(figsize=(7.5, 6.0))
    image = ax.imshow(matrix, vmin=-1, vmax=1, cmap="coolwarm")
    ax.set_xticks(range(len(keys)), labels=keys, rotation=30, ha="right")
    ax.set_yticks(range(len(keys)), labels=keys)
    ax.set_title("Correlation between model cosine rankings")
    for i in range(len(keys)):
        for j in range(len(keys)):
            ax.text(j, i, f"{matrix[i, j]:.2f}", ha="center", va="center")
    fig.colorbar(image, ax=ax, label="Pearson correlation")
    fig.tight_layout()
    fig.savefig(figures / "model_score_correlation.png", dpi=150)
    plt.close(fig)


def build_report(run_dir: Path, summaries: list[dict], manifest: dict) -> None:
    ordered = sorted(
        summaries,
        key=lambda row: (row.get("spearman_rho") is not None, row.get("spearman_rho") or -999),
        reverse=True,
    )

    lines = [
        "# AUSME semantic embedding benchmark",
        "",
        f"Run UTC: {manifest['created_at_utc']}",
        f"Benchmark pairs: {manifest['benchmark']['pair_count']}",
        f"Benchmark SHA256: `{manifest['benchmark']['sha256']}`",
        "",
        "## Model ranking",
        "",
        "Primary criterion: Spearman rank correlation between the 1-5 human semantic score and model cosine similarity.",
        "Kendall tau-b is included as a second rank-based measure; Pearson is supplementary only.",
        "",
        "| Rank | Model | Family | Spearman ρ | 95% bootstrap CI | Kendall τ-b | Pearson r |",
        "|---:|---|---|---:|---:|---:|---:|",
    ]

    for rank, row in enumerate(ordered, start=1):
        ci = f"[{row['spearman_ci_95_low']:.3f}, {row['spearman_ci_95_high']:.3f}]"
        lines.append(
            f"| {rank} | {row['model_key']} | {row['family']} | "
            f"{row['spearman_rho']:.4f} | {ci} | "
            f"{row['kendall_tau_b']:.4f} | {row['pearson_r']:.4f} |"
        )

    lines += [
        "",
        "## Interpretation guardrails",
        "",
        "- Do not compare models by average raw cosine magnitude; their score distributions differ.",
        "- This benchmark evaluates short scientific/research phrase similarity only.",
        "- A winner here is a strong candidate for keyword/topic semantic comparison, not automatically the best model for long-document retrieval or RAG.",
        "- Review `worst_disagreements_*.csv` before selecting a model so lexical traps and domain-specific failures are visible.",
        "",
    ]

    (run_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare embedding models against the AUSME 75-pair human semantic benchmark."
    )
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--model-config", type=Path, default=DEFAULT_MODELS)
    parser.add_argument(
        "--models",
        default="all",
        help="Comma-separated model keys from config/models.json, or 'all'.",
    )
    parser.add_argument(
        "--device",
        default="auto",
        help="Sentence Transformers device: auto, cpu, cuda, mps, etc.",
    )
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args()

    if args.batch_size < 1:
        raise SystemExit("--batch-size must be >= 1")

    # Alibaba-NLP/gte-large-en-v1.5 uses legacy remote modeling code written
    # for Transformers 4.x. Transformers 5.x can corrupt its RoPE position
    # buffers before the first forward pass. Fail early with a clear message
    # instead of downloading/loading every model and crashing on GTE.
    transformers_version = package_version("transformers")
    sentence_transformers_version = package_version("sentence-transformers")

    rows = load_benchmark(args.benchmark)
    configs = load_model_configs(args.model_config)

    if args.models == "all":
        selected_keys = list(configs)
    else:
        selected_keys = [key.strip() for key in args.models.split(",") if key.strip()]
        unknown = [key for key in selected_keys if key not in configs]
        if unknown:
            raise SystemExit(f"Unknown model keys: {unknown}. Available: {list(configs)}")

    if "gte_large_en_v1_5" in selected_keys and transformers_version:
        try:
            transformers_major = int(transformers_version.split(".", 1)[0])
        except ValueError:
            transformers_major = None
        if transformers_major is not None and transformers_major >= 5:
            raise SystemExit(
                "GTE preflight failed: Alibaba-NLP/gte-large-en-v1.5 uses "
                "Transformers-4-era remote code and is not reliable with "
                f"transformers {transformers_version}. Install the benchmark "
                "requirements (sentence-transformers==5.7.0, "
                "transformers==4.57.6) and rerun. Current "
                f"sentence-transformers={sentence_transformers_version}."
            )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.output_root / timestamp
    embeddings_dir = run_dir / "embeddings"
    run_dir.mkdir(parents=True, exist_ok=False)
    embeddings_dir.mkdir()

    phrases = unique_phrases(rows)
    phrase_index = {phrase: idx for idx, phrase in enumerate(phrases)}
    human_scores = np.asarray([row["human_score"] for row in rows], dtype=float)

    score_columns: dict[str, np.ndarray] = {}
    model_metadata = []
    summaries = []
    score_by_rating_rows = []

    device = None if args.device.lower() == "auto" else args.device

    for model_key in selected_keys:
        config = configs[model_key]
        print(f"\n=== {model_key}: {config['model_id']} ===")
        embeddings, metadata = encode_model(
            config=config,
            phrases=phrases,
            device=device,
            batch_size=args.batch_size,
        )
        model_metadata.append(metadata)

        np.savez_compressed(
            embeddings_dir / f"{model_key}.npz",
            phrases=np.asarray(phrases),
            embeddings=embeddings,
        )

        scores = np.asarray(
            [
                float(
                    np.dot(
                        embeddings[phrase_index[row["phrase_a"]]],
                        embeddings[phrase_index[row["phrase_b"]]],
                    )
                )
                for row in rows
            ],
            dtype=np.float64,
        )
        scores = np.clip(scores, -1.0, 1.0)
        score_columns[model_key] = scores

        metric_values = evaluate_scores(human_scores, scores)
        summaries.append(
            {
                "model_key": model_key,
                "family": config.get("family", ""),
                "model_id": config["model_id"],
                "embedding_dimension": metadata["embedding_dimension"],
                **metric_values,
                "runtime_seconds": metadata["runtime_seconds"],
            }
        )

        disagreement = rank_disagreement_rows(rows, scores)
        write_csv(run_dir / f"worst_disagreements_{model_key}.csv", disagreement[:15])

        grouped = defaultdict(list)
        for rating, score in zip(human_scores.astype(int), scores):
            grouped[int(rating)].append(float(score))
        for rating in range(1, 6):
            vals = np.asarray(grouped[rating], dtype=float)
            score_by_rating_rows.append(
                {
                    "model_key": model_key,
                    "human_score": rating,
                    "n": int(vals.size),
                    "mean_cosine": float(vals.mean()) if vals.size else None,
                    "median_cosine": float(np.median(vals)) if vals.size else None,
                    "std_cosine": float(vals.std(ddof=1)) if vals.size > 1 else None,
                }
            )

    pair_score_rows = []
    for idx, row in enumerate(rows):
        output = {
            "pair_id": row["pair_id"],
            "reviewer_set": row["reviewer_set"],
            "phrase_a": row["phrase_a"],
            "phrase_b": row["phrase_b"],
            "human_score": row["human_score"],
        }
        for model_key in selected_keys:
            output[f"{model_key}_cosine"] = float(score_columns[model_key][idx])
        pair_score_rows.append(output)

    write_csv(run_dir / "pair_scores.csv", pair_score_rows)
    write_csv(run_dir / "model_summary.csv", summaries)
    write_csv(run_dir / "score_by_human_rating.csv", score_by_rating_rows)

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "benchmark": {
            "path": str(args.benchmark),
            "sha256": sha256_file(args.benchmark),
            "pair_count": len(rows),
            "unique_phrase_count": len(phrases),
            "score_distribution": dict(sorted(Counter(int(x) for x in human_scores).items())),
            "reviewer_set_distribution": dict(sorted(Counter(row["reviewer_set"] for row in rows).items())),
        },
        "run": {
            "selected_models": selected_keys,
            "device_argument": args.device,
            "batch_size": args.batch_size,
            "python": sys.version,
            "platform": platform.platform(),
        },
        "packages": {
            "numpy": package_version("numpy"),
            "scipy": package_version("scipy"),
            "sentence-transformers": package_version("sentence-transformers"),
            "torch": package_version("torch"),
            "transformers": package_version("transformers"),
        },
        "models": model_metadata,
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    if not args.no_plots:
        make_plots(run_dir, rows, score_columns)

    build_report(run_dir, summaries, manifest)

    ordered = sorted(summaries, key=lambda row: row["spearman_rho"], reverse=True)
    print("\n=== Ranking by Spearman rho ===")
    for index, row in enumerate(ordered, start=1):
        print(
            f"{index}. {row['model_key']}: rho={row['spearman_rho']:.4f}, "
            f"tau-b={row['kendall_tau_b']:.4f}, r={row['pearson_r']:.4f}"
        )
    print(f"\nResults written to: {run_dir}")


if __name__ == "__main__":
    main()
