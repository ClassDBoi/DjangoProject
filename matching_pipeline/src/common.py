"""Paths, configuration, file helpers, prompts and the JSON schema for generated topics."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parent.parent          # matching_pipeline/
PROJECT_ROOT = ROOT.parent                              # repository root
CONFIG_PATH = ROOT / "config" / "pipeline.json"
PROMPT_DIR = ROOT / "prompts"
RUNS_DIR = ROOT / "runs"                                # gitignored: contains client text

DATA_DIR = PROJECT_ROOT / "data"                        # gitignored client data files
SUBSET_PATH = DATA_DIR / "senior_design_subset.json"
FULL_PATH = DATA_DIR / "senior_design_full_announcements.json"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def load_client_data() -> tuple[dict, dict]:
    for path in (SUBSET_PATH, FULL_PATH):
        if not path.exists():
            raise SystemExit(f"Missing client data file: {path}\n"
                             "These files are not in the repository; get them from the project team.")
    return (json.loads(SUBSET_PATH.read_text(encoding="utf-8")),
            json.loads(FULL_PATH.read_text(encoding="utf-8")))


# ---------------------------------------------------------------- files
def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- prompts
def load_prompt(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def prompt_fingerprint() -> str:
    """Hash of the prompt files. Saved outputs made with other prompts are regenerated."""
    return sha256_text("\n".join(load_prompt(p.name) for p in sorted(PROMPT_DIR.glob("*.txt"))))[:12]


def generation_messages(unit: dict) -> list[dict]:
    return [
        {"role": "system", "content": load_prompt("generate_system.txt")},
        {"role": "user", "content": Template(load_prompt("generate_user.txt")).substitute(
            doc_kind=unit["doc_kind_label"],
            context_note=unit.get("context_note", ""),
            title=unit["title"],
            text=unit["text"],
        )},
    ]


# ---------------------------------------------------------------- output schema
GENERATION_SCHEMA = {
    "type": "object",
    "properties": {
        "analysis": {"type": "string"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "term": {"type": "string"},
                    "type": {"type": "string", "enum": ["topic", "keyword"]},
                    "importance": {"type": "integer", "minimum": 1, "maximum": 5},
                    "justification": {"type": "string"},
                },
                "required": ["term", "type", "importance", "justification"],
            },
        },
    },
    "required": ["analysis", "items"],
}


def validate(data, schema: dict, path: str = "$") -> list[str]:
    """Minimal JSON-schema check for the subset used above (no extra dependency)."""
    errors: list[str] = []
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(data, dict):
            return [f"{path}: expected object"]
        errors += [f"{path}.{key}: missing" for key in schema.get("required", []) if key not in data]
        for key, sub in schema.get("properties", {}).items():
            if key in data:
                errors += validate(data[key], sub, f"{path}.{key}")
    elif kind == "array":
        if not isinstance(data, list):
            return [f"{path}: expected array"]
        for i, item in enumerate(data):
            errors += validate(item, schema["items"], f"{path}[{i}]")
    elif kind == "string":
        if not isinstance(data, str):
            errors.append(f"{path}: expected string")
        elif "enum" in schema and data not in schema["enum"]:
            errors.append(f"{path}: {data!r} not in {schema['enum']}")
    elif kind == "integer":
        if isinstance(data, bool) or not isinstance(data, int):
            errors.append(f"{path}: expected integer")
        elif not schema.get("minimum", data) <= data <= schema.get("maximum", data):
            errors.append(f"{path}: {data} out of range")
    return errors


def extract_json(text: str):
    """Parse the first JSON object in model output (tolerates code fences or extra words)."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None


def normalize_term(term: str) -> str:
    """Lowercase, no punctuation, single spaces: used to spot duplicate terms."""
    term = re.sub(r"[^\w\s-]", " ", str(term or "").casefold()).replace("-", " ")
    return " ".join(term.split())
