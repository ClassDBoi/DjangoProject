"""Topic-to-topic matching of researchers and funding opportunities, with evidence.

Researcher side: the generated keywords of each researcher's papers (papers run). They are
not filtered: in papers, words like "grant" or "program" are often the research subject.

Opportunity side: the generated topics of every section window of an opportunity
(opportunities run), merged per opportunity, then
  - funding, administrative, eligibility and organization terms are removed (rules.flag_reason),
  - career-stage topics ("Postdoctoral Research Transition") are set aside for the eligibility
    layer (rules.career_stage_reason),
  - at most max_topics_per_opportunity topics are kept, taken in turn from each window
    (importance scores are given per window and are not comparable across windows).

Scoring, per researcher-opportunity pair:
  - every opportunity topic is compared with every researcher keyword (MPNet cosine similarity);
  - topics that closely match almost every researcher ("Clinical Trials") count less when ranking;
  - the evidence is the strongest `evidence_links` links, each using a different topic and a
    different keyword (so one look-alike word cannot supply all the evidence);
  - ranking_score orders the matches; semantic_similarity (shown to users as Strong/Possible)
    is the mean raw cosine similarity of the evidence links.

Semantic similarity is not a probability, a confidence or a likelihood of funding.
Eligibility, deadlines and amounts are not considered here.

Validated in a blind team review of 75 top matches (November 2026); see docs/DECISIONS.md.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

from common import normalize_term, read_jsonl, write_csv, write_json
from rules import career_stage_reason, flag_reason


# ---------------------------------------------------------------- embeddings
class Embedder:
    """MPNet sentence embeddings (normalized), cached per string.
    mock=True uses character-trigram vectors so the pipeline can be checked without the model."""

    def __init__(self, config: dict, mock: bool = False):
        self.mock = mock
        if not mock:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                sys.exit("sentence-transformers is not installed. See matching_pipeline/README.md.")
            self.model = SentenceTransformer(config["embedding"]["model"],
                                             revision=config["embedding"]["revision"], device="cpu")

    def matrix(self, terms: list[str]):
        import numpy as np
        if not self.mock:
            return np.asarray(self.model.encode(terms, normalize_embeddings=True, batch_size=32,
                                                show_progress_bar=False), dtype="float32")
        out = np.zeros((len(terms), 512), dtype="float32")
        for i, term in enumerate(terms):
            padded = f"  {normalize_term(term)}  "
            for j in range(len(padded) - 2):
                out[i, int(hashlib.md5(padded[j:j + 3].encode()).hexdigest(), 16) % 512] += 1.0
            out[i] /= math.sqrt(float((out[i] ** 2).sum())) or 1.0
        return out


# ---------------------------------------------------------------- loading
def _load(run_dir: Path):
    """units by id, and valid generations by unit id."""
    units_path = run_dir / "units.jsonl"
    if not units_path.exists():
        sys.exit(f"{units_path} not found. Run the prepare and generate steps first.")
    units = {u["unit_id"]: u for u in read_jsonl(units_path)}
    gens = {}
    for path in (run_dir / "generations").glob("*.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("valid") and record["unit_id"] in units:
            gens[record["unit_id"]] = record
    return units, gens


def _researcher_terms(papers_run: Path, subset: dict):
    """Keywords per researcher (only the client's researcher list), with the papers they came from."""
    units, gens = _load(papers_run)
    papers = {f"paper-{p['id']}": p for p in subset["papers"]}
    known = {r["auid"] for r in subset["researchers"]}
    by_researcher: dict[str, dict[str, dict]] = defaultdict(dict)
    for uid, gen in gens.items():
        paper = papers.get(units[uid]["doc_id"])
        if not paper:
            continue
        for auid in [a for a in paper.get("researcher_auids") or [] if a in known]:
            for item in gen["parsed"]["items"]:
                key = normalize_term(item["term"])
                if not key:
                    continue
                entry = by_researcher[auid].setdefault(key, {"term": item["term"], "papers": []})
                if paper["id"] not in [p["id"] for p in entry["papers"]]:
                    entry["papers"].append({"id": paper["id"], "title": paper["title"]})
    return by_researcher


def _opportunity_topics(opps_run: Path):
    units, gens = _load(opps_run)
    topics: dict[str, dict[str, dict]] = defaultdict(dict)
    titles, rows = {}, []
    for uid, gen in sorted(gens.items()):
        unit = units[uid]
        doc = unit["doc_id"]
        titles[doc] = unit["title"]
        topics[doc]  # an opportunity with no usable topics still appears (as "not matched")
        for item in gen["parsed"]["items"]:
            removed = flag_reason(item["term"])
            career = career_stage_reason(item["term"]) if not removed else None
            key = normalize_term(item["term"])
            duplicate = key in topics[doc]
            rows.append({"opp_id": doc.removeprefix("opp-"), "title": unit["title"], "unit_id": uid,
                         "topic": item["term"], "importance": item["importance"],
                         "removed_by_rule": removed or "", "eligibility_layer": career or "",
                         "duplicate": duplicate, "used": not (removed or career or duplicate) and bool(key)})
            if removed or career or not key:
                continue
            entry = topics[doc].setdefault(key, {"term": item["term"], "importance": item["importance"],
                                                 "units": [], "order": len(topics[doc])})
            entry["importance"] = max(entry["importance"], item["importance"])
            entry["units"].append(uid)
    return topics, titles, rows


def _cap_topics(o_topics: dict, max_topics: int, topic_rows: list[dict]) -> None:
    """Keep at most max_topics per opportunity, taken in turn from each section window.
    Without a limit, long announcements would win simply by offering more topics."""
    for doc, entries in o_topics.items():
        by_unit = defaultdict(list)
        for key_entry in entries.items():
            by_unit[key_entry[1]["units"][0]].append(key_entry)
        queues = [sorted(v, key=lambda kv: (-kv[1]["importance"], kv[1]["order"])) for _, v in sorted(by_unit.items())]
        ranked = []
        while any(queues):
            for queue in queues:
                if queue:
                    ranked.append(queue.pop(0))
        keep = dict(ranked[:max_topics])
        dropped = {k for k in entries if k not in keep}
        o_topics[doc] = keep
        for row in topic_rows:
            if row["used"] and f"opp-{row['opp_id']}" == doc and normalize_term(row["topic"]) in dropped:
                row["used"] = False
                row["beyond_topic_limit"] = True


def _pick_links(adjusted, k):
    """Greedy one-to-one links: highest value first, each topic and each keyword used once."""
    import numpy as np
    order = np.dstack(np.unravel_index(np.argsort(-adjusted, axis=None), adjusted.shape))[0]
    used_t, used_r, picked = set(), set(), []
    for i, j in order:
        if i in used_t or j in used_r:
            continue
        picked.append((int(i), int(j)))
        used_t.add(i)
        used_r.add(j)
        if len(picked) == k:
            break
    return picked


# ---------------------------------------------------------------- matching
def run_matching(papers_run: Path, opps_run: Path, out_dir: Path, config: dict, subset: dict,
                 mock: bool = False) -> Path:
    import numpy as np

    settings = config["matching"]
    researchers = {r["auid"]: r for r in subset["researchers"]}
    r_terms = _researcher_terms(papers_run, subset)
    o_topics, o_titles, topic_rows = _opportunity_topics(opps_run)
    _cap_topics(o_topics, settings["max_topics_per_opportunity"], topic_rows)
    not_matched = sorted(d.removeprefix("opp-") for d, t in o_topics.items() if not t)
    o_topics = {d: t for d, t in o_topics.items() if t}
    if not r_terms or not o_topics:
        sys.exit("No researcher keywords or opportunity topics found. Run the generate steps first.")

    embedder = Embedder(config, mock)
    all_terms = sorted({e["term"] for d in r_terms.values() for e in d.values()} |
                       {e["term"] for d in o_topics.values() for e in d.values()})
    index = {t: i for i, t in enumerate(all_terms)}
    vectors = embedder.matrix(all_terms)

    # Near-duplicate topics within an opportunity, listed for people to check (never merged automatically).
    duplicates = []
    for doc, entries in o_topics.items():
        terms = [e["term"] for e in entries.values()]
        sims = vectors[[index[t] for t in terms]] @ vectors[[index[t] for t in terms]].T
        duplicates += [{"opp_id": doc.removeprefix("opp-"), "topic_a": terms[i], "topic_b": terms[j],
                        "semantic_similarity": round(float(sims[i, j]), 3)}
                       for i in range(len(terms)) for j in range(i + 1, len(terms))
                       if sims[i, j] >= settings["near_duplicate_similarity"]]

    # How closely each topic matches the average researcher; generic topics count less when ranking.
    r_mats = {a: vectors[[index[e["term"]] for e in d.values()]] for a, d in r_terms.items()}
    generic = {}
    for doc, entries in o_topics.items():
        tm = vectors[[index[e["term"]] for e in entries.values()]]
        best = np.stack([(tm @ rm.T).max(axis=1) for rm in r_mats.values()])
        for entry, value in zip(entries.values(), best.mean(axis=0)):
            generic[(doc, entry["term"])] = float(value)
    generic_mean = sum(generic.values()) / len(generic)

    matches = []
    for auid, entries in r_terms.items():
        r_list = list(entries.values())
        for doc, topics in o_topics.items():
            t_list = list(topics.values())
            sims = vectors[[index[e["term"]] for e in t_list]] @ r_mats[auid].T
            penalty = np.array([generic[(doc, e["term"])] - generic_mean for e in t_list])[:, None]
            adjusted = sims - penalty
            k = min(settings["evidence_links"], len(t_list), len(r_list))
            links = _pick_links(adjusted, k)
            matches.append({
                "auid": auid,
                "researcher": researchers[auid]["name"],
                "department": researchers[auid].get("department") or "",
                "opp_id": doc.removeprefix("opp-"),
                "opportunity": o_titles[doc],
                "ranking_score": round(sum(float(adjusted[i, j]) for i, j in links) / k, 4),
                "strongest_links_similarity": round(sum(float(sims[i, j]) for i, j in links) / k, 4),
                "evidence": [{"opportunity_topic": t_list[i]["term"], "researcher_term": r_list[j]["term"],
                              "paper_ids": [p["id"] for p in r_list[j]["papers"]],
                              "semantic_similarity": round(float(sims[i, j]), 4)} for i, j in links],
            })

    for key, rank_field in (("auid", "rank_for_researcher"), ("opp_id", "rank_for_opportunity")):
        groups = defaultdict(list)
        for match in matches:
            groups[match[key]].append(match)
        for group in groups.values():
            group.sort(key=lambda m: -m["ranking_score"])
            for rank, match in enumerate(group, 1):
                match[rank_field] = rank
    matches.sort(key=lambda m: (m["researcher"], m["rank_for_researcher"]))

    write_json(out_dir / "matches.json", {
        "description": "Researcher-opportunity matches. Similarities are MPNet cosine similarity between "
                       "researcher keywords and opportunity topics: not a probability or likelihood of funding. "
                       "Import into the database with: python manage.py import_matches <this file> --apply",
        "embedding_model": config["embedding"]["model"], "embedding_revision": config["embedding"]["revision"],
        "generator": config["generator"]["model_id"], "scoring": "v2",
        "scoring_description": "career-stage topics set aside; topics taken evenly from every section; "
                               "evidence links use different topics and keywords; generic topics count less",
        "papers_run": papers_run.name, "opportunities_run": opps_run.name, "mock": mock,
        "opportunities_not_matched": not_matched,
        "matches": matches,
    })
    write_csv(out_dir / "opportunity_topics.csv", topic_rows)
    write_csv(out_dir / "near_duplicate_topics.csv", duplicates)
    write_csv(out_dir / "researcher_terms.csv", [
        {"auid": a, "researcher": researchers[a]["name"], "term": e["term"], "papers": len(e["papers"]),
         "paper_titles": " | ".join(p["title"] for p in e["papers"])}
        for a, d in sorted(r_terms.items()) for e in d.values()])
    _write_report(out_dir, matches, o_titles, not_matched, topic_rows, duplicates, mock)
    return out_dir


def _write_report(out_dir, matches, o_titles, not_matched, topic_rows, duplicates, mock):
    top3 = Counter(m["opp_id"] for m in matches if m["rank_for_researcher"] <= 3)
    researchers = sorted({m["auid"] for m in matches})
    opportunities = sorted({m["opp_id"] for m in matches})
    expected = 3 * len(researchers) / max(1, len(opportunities))
    lines = ["# Researcher-opportunity matches", ""]
    if mock:
        lines += ["> **Mock run: meaningless similarities. Do not import.**", ""]
    lines += [
        f"{len(researchers)} researchers x {len(opportunities)} opportunities. "
        f"{sum(1 for r in topic_rows if r['removed_by_rule'])} topics removed by the rule filter, "
        f"{sum(1 for r in topic_rows if r['eligibility_layer'])} career-stage topics set aside, "
        f"{len(duplicates)} near-duplicate topic pairs listed for review.",
        "",
        "Not matched (no research topics left): " + (", ".join(
            f"{o_titles.get('opp-' + o, o)} ({o})" for o in not_matched) or "none") + ".",
        "",
        "Similarities are semantic similarity, not a probability or likelihood of funding.",
        "",
        "## Concentration check",
        "",
        f"Researchers with each opportunity in their top 3 (about {expected:.1f} if spread evenly). "
        "An opportunity far above that may have generic topics that match everyone.",
        "",
        "| Opportunity | In top 3 of |",
        "|---|---:|",
    ]
    for opp_id, count in top3.most_common():
        lines.append(f"| {o_titles['opp-' + opp_id][:80]} ({opp_id}) | {count} |")
    lines += ["", "## Top 3 per researcher", ""]
    by_researcher = defaultdict(list)
    for match in matches:
        by_researcher[match["researcher"]].append(match)
    for name in sorted(by_researcher):
        lines.append(f"### {name}")
        for match in sorted(by_researcher[name], key=lambda m: m["rank_for_researcher"])[:3]:
            lines.append(f"{match['rank_for_researcher']}. **{match['opportunity']}** "
                         f"(semantic similarity {match['strongest_links_similarity']:.2f})")
            for link in match["evidence"]:
                lines.append(f"   - {link['opportunity_topic']} <-> {link['researcher_term']} "
                             f"({link['semantic_similarity']:.2f})")
        lines.append("")
    (out_dir / "match_report.md").write_text("\n".join(lines), encoding="utf-8")
