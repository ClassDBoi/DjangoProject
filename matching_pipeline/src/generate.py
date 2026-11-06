"""Run the topic/keyword generator (Qwen3-4B through Ollama) over a run's units.

Resumable: each unit's output is saved as runs/<run>/generations/<unit_id>.json and
skipped next time, unless the prompt files have changed since it was made.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from common import GENERATION_SCHEMA, generation_messages, prompt_fingerprint, read_jsonl, validate, write_json
from ollama import BackendError, make_backend


def _is_done(path: Path, fingerprint: str) -> bool:
    if not path.exists():
        return False
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return record.get("prompt_fingerprint") == fingerprint and record.get("valid")


def run_generation(run_dir: Path, config: dict, limit: int | None = None, mock: bool = False) -> None:
    units_path = run_dir / "units.jsonl"
    if not units_path.exists():
        sys.exit(f"{units_path} not found. Run the matching prepare step first.")
    units = read_jsonl(units_path)[:limit] if limit else read_jsonl(units_path)

    fingerprint = prompt_fingerprint()
    out_dir = run_dir / "generations"
    backend = make_backend(config, mock)
    try:
        backend.check()
    except BackendError as exc:
        sys.exit(str(exc))

    todo = [u for u in units if not _is_done(out_dir / f"{u['unit_id']}.json", fingerprint)]
    print(f"{len(units) - len(todo)} already done, {len(todo)} to run "
          f"({'mock' if mock else config['generator']['model_id']})")
    started = time.perf_counter()
    failures = 0
    for i, unit in enumerate(todo, 1):
        try:
            result = backend.chat(generation_messages(unit), GENERATION_SCHEMA)
            errors = ["no JSON object found"] if result["parsed"] is None else validate(result["parsed"], GENERATION_SCHEMA)
        except BackendError as exc:
            result, errors = {"text": "", "parsed": None, "seconds": None}, [f"backend error: {exc}"]
        failures += bool(errors)
        write_json(out_dir / f"{unit['unit_id']}.json", {
            "unit_id": unit["unit_id"], "doc_id": unit["doc_id"],
            "model": "mock" if mock else config["generator"]["model_id"],
            "prompt_fingerprint": fingerprint, "valid": not errors, "errors": errors[:20], **result,
        })
        remaining = (time.perf_counter() - started) / i * (len(todo) - i)
        print(f"  [{i}/{len(todo)}] {unit['unit_id']}{'  (invalid output, will retry next run)' if errors else ''}"
              f"  (~{remaining / 60:.0f} min left)", flush=True)
    if failures:
        print(f"{failures} outputs were invalid; run the same command again to retry them.")
