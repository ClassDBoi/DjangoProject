from __future__ import annotations

import csv
import hashlib
from collections import Counter
from pathlib import Path

REQUIRED_COLUMNS = {
    "pair_id",
    "reviewer_set",
    "phrase_a",
    "phrase_b",
    "human_score",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_benchmark(path: Path, expected_pairs: int = 75) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - fieldnames
        if missing:
            raise ValueError(f"Benchmark is missing required columns: {sorted(missing)}")

        rows = []
        for line_number, row in enumerate(reader, start=2):
            pair_id = (row.get("pair_id") or "").strip()
            reviewer_set = (row.get("reviewer_set") or "").strip()
            phrase_a = (row.get("phrase_a") or "").strip()
            phrase_b = (row.get("phrase_b") or "").strip()

            try:
                human_score = int(row.get("human_score", ""))
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid human_score on CSV line {line_number}: {row.get('human_score')!r}"
                ) from exc

            if not pair_id or not reviewer_set or not phrase_a or not phrase_b:
                raise ValueError(f"Blank required value on CSV line {line_number}")
            if human_score not in {1, 2, 3, 4, 5}:
                raise ValueError(
                    f"human_score must be 1-5 on CSV line {line_number}; got {human_score}"
                )

            rows.append(
                {
                    "pair_id": pair_id,
                    "reviewer_set": reviewer_set,
                    "phrase_a": phrase_a,
                    "phrase_b": phrase_b,
                    "human_score": human_score,
                    "score_definition": (row.get("score_definition") or "").strip(),
                }
            )

    if len(rows) != expected_pairs:
        raise ValueError(f"Expected {expected_pairs} benchmark pairs; found {len(rows)}")

    ids = [row["pair_id"] for row in rows]
    duplicates = [key for key, count in Counter(ids).items() if count > 1]
    if duplicates:
        raise ValueError(f"Duplicate pair IDs found: {duplicates}")

    exact_pairs = [(row["phrase_a"], row["phrase_b"]) for row in rows]
    duplicate_pairs = [key for key, count in Counter(exact_pairs).items() if count > 1]
    if duplicate_pairs:
        raise ValueError(f"Duplicate phrase pairs found: {duplicate_pairs}")

    seen = set()
    reversed_duplicates = []
    for phrase_a, phrase_b in exact_pairs:
        if (phrase_b, phrase_a) in seen:
            reversed_duplicates.append((phrase_a, phrase_b))
        seen.add((phrase_a, phrase_b))
    if reversed_duplicates:
        raise ValueError(f"Reversed duplicate phrase pairs found: {reversed_duplicates}")

    return rows


def unique_phrases(rows: list[dict]) -> list[str]:
    seen = set()
    phrases = []
    for row in rows:
        for phrase in (row["phrase_a"], row["phrase_b"]):
            if phrase not in seen:
                seen.add(phrase)
                phrases.append(phrase)
    return phrases
