from __future__ import annotations

import math

import numpy as np
from scipy.stats import kendalltau, pearsonr, rankdata, spearmanr


def _finite(value) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None


def bootstrap_spearman_ci(
    human: np.ndarray,
    model_scores: np.ndarray,
    iterations: int = 5000,
    seed: int = 20261012,
) -> tuple[float | None, float | None]:
    rng = np.random.default_rng(seed)
    n = len(human)
    samples = []

    for _ in range(iterations):
        idx = rng.integers(0, n, size=n)
        h = human[idx]
        m = model_scores[idx]
        if np.unique(h).size < 2 or np.unique(m).size < 2:
            continue
        rho = spearmanr(h, m).statistic
        if math.isfinite(float(rho)):
            samples.append(float(rho))

    if not samples:
        return None, None

    low, high = np.percentile(samples, [2.5, 97.5])
    return float(low), float(high)


def evaluate_scores(human_scores, model_scores) -> dict:
    human = np.asarray(human_scores, dtype=np.float64)
    model = np.asarray(model_scores, dtype=np.float64)

    if human.shape != model.shape or human.ndim != 1:
        raise ValueError("human_scores and model_scores must be same-length 1D arrays")

    spearman = spearmanr(human, model).statistic
    pearson = pearsonr(human, model).statistic
    kendall = kendalltau(human, model, variant="b").statistic
    ci_low, ci_high = bootstrap_spearman_ci(human, model)

    return {
        "spearman_rho": _finite(spearman),
        "spearman_ci_95_low": ci_low,
        "spearman_ci_95_high": ci_high,
        "kendall_tau_b": _finite(kendall),
        "pearson_r": _finite(pearson),
    }


def rank_disagreement_rows(rows: list[dict], model_scores) -> list[dict]:
    human = np.asarray([row["human_score"] for row in rows], dtype=np.float64)
    model = np.asarray(model_scores, dtype=np.float64)

    # Percentile ranks make disagreement comparable across model score scales.
    # Higher values mean more semantically similar for both humans and models.
    human_pct = (rankdata(human, method="average") - 1) / max(1, len(human) - 1)
    model_pct = (rankdata(model, method="average") - 1) / max(1, len(model) - 1)
    gaps = np.abs(human_pct - model_pct)

    output = []
    for row, cosine, h_pct, m_pct, gap in zip(rows, model, human_pct, model_pct, gaps):
        output.append(
            {
                "pair_id": row["pair_id"],
                "reviewer_set": row["reviewer_set"],
                "phrase_a": row["phrase_a"],
                "phrase_b": row["phrase_b"],
                "human_score": row["human_score"],
                "cosine_similarity": float(cosine),
                "human_rank_percentile": float(h_pct),
                "model_rank_percentile": float(m_pct),
                "absolute_rank_gap": float(gap),
            }
        )

    output.sort(key=lambda item: item["absolute_rank_gap"], reverse=True)
    return output
