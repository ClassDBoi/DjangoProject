from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np


def load_model_configs(path: Path) -> dict[str, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    models = payload.get("models", [])
    configs = {}
    for item in models:
        key = item.get("key")
        if not key or key in configs:
            raise ValueError(f"Invalid or duplicate model key: {key!r}")
        configs[key] = item
    if not configs:
        raise ValueError("No models were configured")
    return configs


def _model_commit_hash(model) -> str | None:
    try:
        first_module = model._first_module()
        auto_model = getattr(first_module, "auto_model", None)
        config = getattr(auto_model, "config", None)
        return getattr(config, "_commit_hash", None)
    except Exception:
        return None


def encode_model(
    config: dict,
    phrases: list[str],
    device: str | None,
    batch_size: int,
) -> tuple[np.ndarray, dict]:
    from sentence_transformers import SentenceTransformer

    model_id = config["model_id"]
    trust_remote_code = bool(config.get("trust_remote_code", False))
    prefix = config.get("prefix", "")

    kwargs = {"trust_remote_code": trust_remote_code}
    if device:
        kwargs["device"] = device

    started = time.perf_counter()
    model = SentenceTransformer(model_id, **kwargs)
    prepared = [f"{prefix}{phrase}" for phrase in phrases]
    embeddings = model.encode(
        prepared,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    elapsed = time.perf_counter() - started

    embeddings = np.asarray(embeddings, dtype=np.float32)
    if embeddings.ndim != 2 or embeddings.shape[0] != len(phrases):
        raise RuntimeError(
            f"Unexpected embedding shape from {model_id}: {embeddings.shape}"
        )
    if not np.isfinite(embeddings).all():
        raise RuntimeError(f"Non-finite embedding values produced by {model_id}")

    norms = np.linalg.norm(embeddings, axis=1)
    if not np.allclose(norms, 1.0, atol=2e-4):
        raise RuntimeError(
            f"Normalized embeddings expected from {model_id}; norm range "
            f"{norms.min():.6f}-{norms.max():.6f}"
        )

    metadata = {
        "key": config["key"],
        "family": config.get("family"),
        "model_id": model_id,
        "prefix": prefix,
        "trust_remote_code": trust_remote_code,
        "embedding_dimension": int(embeddings.shape[1]),
        "model_commit_hash": _model_commit_hash(model),
        "runtime_seconds": round(elapsed, 3),
        "normalization": "L2 via SentenceTransformer.encode(normalize_embeddings=True)",
        "similarity": "cosine implemented as dot product of normalized embeddings",
    }
    return embeddings, metadata
