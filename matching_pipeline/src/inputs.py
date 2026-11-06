"""Build the model inputs ("units") from the client data files.

Papers: title + abstract, one unit per paper with an abstract of at least
min_abstract_words words.

Opportunities: only the scientific sections of each full announcement (sections.py),
split into windows that fit the model's context; the short description is used when
there is no full announcement.
"""
from __future__ import annotations

import html
import math
import re
from datetime import datetime, timezone
from pathlib import Path

from common import load_client_data, write_csv, write_json, write_jsonl
from sections import split_announcement


def _clean(text: str) -> str:
    text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", text or "", flags=re.I | re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _windows(text: str, max_words: int) -> list[str]:
    """Split on line boundaries into the fewest windows of at most max_words, balanced in size
    so no window is a tiny tail (a pathological long line is hard-split)."""
    total = len(text.split())
    if total <= max_words:
        return [text]
    target = math.ceil(total / math.ceil(total / max_words))
    out, cur, n = [], [], 0
    for line in text.splitlines():
        words = line.split()
        while len(words) > max_words:
            if cur:
                out.append("\n".join(cur)); cur, n = [], 0
            out.append(" ".join(words[:max_words])); words = words[max_words:]
        if cur and n + len(words) > max_words:
            out.append("\n".join(cur)); cur, n = [], 0
        cur.append(" ".join(words)); n += len(words)
        if n >= target:
            out.append("\n".join(cur)); cur, n = [], 0
    if cur:
        if out and len(out[-1].split()) + n <= max_words:
            out[-1] += "\n" + "\n".join(cur)
        else:
            out.append("\n".join(cur))
    return out


def _clean_keep_blanks(text: str) -> str:
    """Like _clean, but keeps blank lines: they mark heading boundaries for the section splitter."""
    text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", text or "", flags=re.I | re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return "\n".join(" ".join(line.split()) for line in text.splitlines())


def prepare_papers(settings: dict, run_dir: Path) -> dict:
    """One unit per paper with a usable abstract, written to run_dir/units.jsonl."""
    subset, full = load_client_data()
    abstracts = {int(p["paper_id"]): p.get("description") for p in full.get("papers", [])}
    units, skipped = [], 0
    for paper in subset["papers"]:
        abstract = _clean(abstracts.get(int(paper["id"])) or paper.get("abstract") or "")
        if len(abstract.split()) < settings["min_abstract_words"]:
            skipped += 1
            continue
        units.append({
            "unit_id": f"paper-{paper['id']}", "doc_id": f"paper-{paper['id']}", "doc_kind": "paper",
            "doc_kind_label": "Research paper (title and abstract)", "context_note": "",
            "title": _clean(paper["title"]), "text": abstract,
        })
    write_jsonl(run_dir / "units.jsonl", units)
    manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "paper_units": len(units),
                "papers_skipped_short_or_missing_abstract": skipped}
    write_json(run_dir / "manifest.json", manifest)
    return manifest


def prepare_opportunities(settings: dict, run_dir: Path, min_words: int = 40, short_kept: int = 300) -> dict:
    """Section-aware inputs for every opportunity, written into the run folder (run_dir/units.jsonl).

    Full announcements: only scientific sections are kept (sections.py), then split into windows of
    at most window_words. If little scientific text is found, the short description is added first.
    No full announcement: the short description is used if it has at least min_words words.
    Every keep/drop decision is written to run_dir/sections/ for the team to check.
    """
    subset, full = load_client_data()
    announcements = {str(o["opp_id"]): o.get("full_announcement") for o in full.get("opportunities", [])}
    window_words = settings["window_words"]
    units, decisions, docs = [], [], []
    preview = ["# Scientific text kept per opportunity (client data: do not share or commit)", ""]
    for o in subset["opportunities"]:
        oid = str(o["opp_id"])
        base = {"doc_id": f"opp-{oid}", "doc_kind": "opportunity", "title": _clean(o["title"])}
        desc = _clean(o.get("description") or "")
        full_text = announcements.get(oid) or ""
        total_words = len(full_text.split())
        if full_text:
            res = split_announcement(_clean_keep_blanks(full_text))
            for sec in res["sections"]:
                decisions.append({"opp_id": oid, "line": sec["line"], "heading": sec["heading"],
                                  "strength": sec["strength"], "label": sec["label"],
                                  "decision": sec["decision"], "words": sec["words"]})
            text, source = _clean(res["kept_text"]), "scientific_sections"
            if res["kept_words"] < short_kept and len(desc.split()) >= min_words:
                text, source = desc + "\n" + text, "scientific_sections_plus_short_description"
        elif len(desc.split()) >= min_words:
            text, source = desc, "short_description_no_full_announcement"
        else:
            text, source = "", "insufficient_text"
        wins = _windows(text, window_words) if text.strip() else []
        for k, win in enumerate(wins, 1):
            if source == "short_description_no_full_announcement":
                label, note = ("Funding opportunity (short description)",
                               "Extract only the scientific research topics; ignore administrative language.")
            else:
                label = "Funding opportunity announcement (scientific sections)"
                note = (f"This text is part {k} of {len(wins)} of the scientific sections of a funding announcement "
                        "(purpose, background, objectives, research scope). Extract only the scientific research "
                        "topics it covers; ignore any remaining administrative, eligibility or application language.")
            units.append({**base, "unit_id": f"opp-{oid}-s{k}", "doc_kind_label": label, "context_note": note,
                          "text": win, "source_section": source, "window": k, "windows": len(wins)})
        docs.append({"opp_id": oid, "title": base["title"], "agency": _clean(str(o.get("agency", "")))[:80],
                     "full_announcement_words": total_words, "kept_words": len(text.split()),
                     "source": source, "windows": len(wins)})
        preview += [f"## opp-{oid}: {base['title']}", f"Source: {source}; {len(text.split())} of "
                    f"{total_words or len(desc.split())} words kept; {len(wins)} window(s)", "", text or "(nothing kept)", ""]

    run_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(run_dir / "units.jsonl", units)
    write_csv(run_dir / "sections" / "opportunities.csv", docs)
    write_csv(run_dir / "sections" / "section_decisions.csv", decisions)
    (run_dir / "sections" / "kept_text.md").write_text("\n".join(preview), encoding="utf-8")
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "opportunity_docs": len({u["doc_id"] for u in units}),
        "opportunity_units": len(units), "window_words": window_words,
        "skipped_opportunities": [d["opp_id"] for d in docs if d["source"] == "insufficient_text"],
    }
    write_json(run_dir / "manifest.json", manifest)
    return {"manifest": manifest, "docs": docs}
