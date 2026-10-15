"""Reproducible exploration of the Senior Design dataset and supplemental text.

This version understands both:
1) data/senior_design_subset.json
2) data/senior_design_full_announcements.json

The supplemental file is merged IN MEMORY only:
- papers[].description -> paper["abstract"]
- opportunities[].full_announcement -> opportunity["full_announcement"]

Nothing in MySQL or either JSON source file is modified.

From the Django project root:
    python -m pip install beautifulsoup4 matplotlib

Recommended:
    python Scripts/analyze_dataset.py

Explicit paths:
    python Scripts/analyze_dataset.py ^
        --input data/senior_design_subset.json ^
        --supplemental data/senior_design_full_announcements.json

Embedding-model evaluation is intentionally handled separately by the 75-pair
semantic benchmark under benchmark/. This script remains model-agnostic and
focuses on dataset coverage, lengths, and RAG planning diagnostics.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import html
import json
import math
from pathlib import Path
import re
import statistics

from bs4 import BeautifulSoup


DEFAULT_INPUT = Path("data/senior_design_subset.json")
DEFAULT_SUPPLEMENTAL = Path("data/senior_design_full_announcements.json")
DEFAULT_OUTPUT = Path("analysis_output")

DEFAULT_RAG_CHUNK_WORDS = 500
DEFAULT_RAG_CHUNK_OVERLAP = 75


def clean_text(value: object) -> str:
    """Remove HTML markup and normalize whitespace without inventing content."""
    if not value:
        return ""

    text = str(value)

    # Avoid parsing bare URLs as HTML, which can cause BeautifulSoup warnings.
    if "<" in text and ">" in text:
        soup = BeautifulSoup(text, "html.parser")
        for item in soup(["script", "style"]):
            item.decompose()
        text = soup.get_text(" ", strip=True)

    return " ".join(html.unescape(text).split())


def word_count(value: str) -> int:
    return len(value.split())


def describe(nums: list[int]) -> dict:
    """Simple descriptive statistics suitable for JSON/report output."""
    if not nums:
        return {
            "count": 0,
            "minimum": 0,
            "q1": 0,
            "median": 0,
            "mean": 0,
            "q3": 0,
            "maximum": 0,
        }

    numbers = sorted(nums)

    if len(numbers) > 1:
        q1, _, q3 = statistics.quantiles(numbers, n=4, method="inclusive")
    else:
        q1 = q3 = numbers[0]

    return {
        "count": len(numbers),
        "minimum": min(numbers),
        "q1": round(q1, 2),
        "median": statistics.median(numbers),
        "mean": round(statistics.mean(numbers), 2),
        "q3": round(q3, 2),
        "maximum": max(numbers),
    }


def bin_counts(values: list[int], edges: list[int]) -> dict[str, int]:
    result: dict[str, int] = {}

    for index, start in enumerate(edges):
        end = edges[index + 1] if index + 1 < len(edges) else None
        label = f"{start}+" if end is None else f"{start}-{end - 1}"
        result[label] = sum(
            value >= start and (end is None or value < end)
            for value in values
        )

    return result


def estimated_chunk_count(
    words: int,
    chunk_words: int,
    overlap_words: int,
) -> int:
    """Estimate fixed-size word chunks for future RAG planning."""
    if words <= 0:
        return 0

    if words <= chunk_words:
        return 1

    stride = chunk_words - overlap_words
    return 1 + math.ceil((words - chunk_words) / stride)


def title_keywords_input(paper: dict) -> str:
    """Current paper semantic representation: title + real abstract/summary + keywords."""
    keyword_text = "; ".join(
        entry["keyword"]
        for entry in paper.get("keywords", [])
        if entry.get("keyword")
    )

    fields = [f"Research paper: {clean_text(paper.get('title'))}"]

    abstract = clean_text(paper.get("abstract"))
    summary = clean_text(paper.get("summary"))

    if abstract:
        fields.append(f"Abstract: {abstract}")
    elif summary:
        fields.append(f"Summary: {summary}")

    if keyword_text:
        fields.append(f"Keywords: {keyword_text}")

    return "\n".join(fields)


def opportunity_input(opp: dict) -> str:
    """Keep the earlier short-description baseline representation comparable."""
    title = clean_text(opp.get("title"))
    description = clean_text(opp.get("description"))
    return f"Funding opportunity: {title}\nDescription: {description}"


def opportunity_full_input(opp: dict) -> str:
    """Long-form opportunity input for context-window/RAG diagnostics only."""
    title = clean_text(opp.get("title"))
    announcement = clean_text(opp.get("full_announcement"))

    if not announcement:
        return ""

    return f"Funding opportunity: {title}\nFull announcement: {announcement}"


def load_json(path: Path, label: str) -> dict:
    if not path.exists():
        raise SystemExit(f"{label} file not found: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not read {label} JSON {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise SystemExit(f"{label} JSON must contain a top-level object.")

    return data


def merge_supplemental(base: dict, supplemental: dict) -> dict:
    """Merge supplemental text into the base dataset in memory.

    Safety:
    - No new records are created.
    - Unknown IDs fail loudly.
    - Base structure is not modified on disk.
    """
    papers = base.get("papers", [])
    opportunities = base.get("opportunities", [])

    paper_by_id = {int(p["id"]): p for p in papers}
    opportunity_by_id = {int(o["opp_id"]): o for o in opportunities}

    supplemental_papers = supplemental.get("papers", [])
    supplemental_opportunities = supplemental.get("opportunities", [])

    seen_papers: set[int] = set()
    seen_opportunities: set[int] = set()

    paper_descriptions_available = 0
    opportunity_announcements_available = 0

    for row in supplemental_papers:
        paper_id = int(row["paper_id"])

        if paper_id in seen_papers:
            raise SystemExit(f"Duplicate supplemental paper_id: {paper_id}")
        seen_papers.add(paper_id)

        if paper_id not in paper_by_id:
            raise SystemExit(
                f"Supplemental paper_id {paper_id} is not present in the base dataset."
            )

        description = clean_text(row.get("description"))
        if description:
            paper_descriptions_available += 1
            # This mirrors the database import mapping.
            paper_by_id[paper_id]["abstract"] = row.get("description")

    for row in supplemental_opportunities:
        opp_id = int(row["opp_id"])

        if opp_id in seen_opportunities:
            raise SystemExit(f"Duplicate supplemental opp_id: {opp_id}")
        seen_opportunities.add(opp_id)

        if opp_id not in opportunity_by_id:
            raise SystemExit(
                f"Supplemental opp_id {opp_id} is not present in the base dataset."
            )

        announcement = clean_text(row.get("full_announcement"))
        if announcement:
            opportunity_announcements_available += 1
            opportunity_by_id[opp_id]["full_announcement"] = row.get(
                "full_announcement"
            )

    return {
        "source_papers": len(supplemental_papers),
        "source_opportunities": len(supplemental_opportunities),
        "paper_descriptions_available": paper_descriptions_available,
        "paper_descriptions_missing": (
            len(supplemental_papers) - paper_descriptions_available
        ),
        "opportunity_announcements_available": opportunity_announcements_available,
        "opportunity_announcements_missing": (
            len(supplemental_opportunities) - opportunity_announcements_available
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Base subset JSON (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--supplemental",
        type=Path,
        default=DEFAULT_SUPPLEMENTAL,
        help=(
            "Supplemental announcements/abstracts JSON "
            f"(default: {DEFAULT_SUPPLEMENTAL}). "
            "If the default file is absent, base-only analysis is used."
        ),
    )
    parser.add_argument(
        "--no-supplemental",
        action="store_true",
        help="Analyze only the original subset JSON.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    parser.add_argument(
        "--rag-chunk-words",
        type=int,
        default=DEFAULT_RAG_CHUNK_WORDS,
        help=f"Word target for rough RAG chunk estimate (default: {DEFAULT_RAG_CHUNK_WORDS}).",
    )
    parser.add_argument(
        "--rag-overlap-words",
        type=int,
        default=DEFAULT_RAG_CHUNK_OVERLAP,
        help=f"Word overlap for rough RAG chunk estimate (default: {DEFAULT_RAG_CHUNK_OVERLAP}).",
    )

    args = parser.parse_args()

    if args.rag_chunk_words < 1:
        parser.error("--rag-chunk-words must be >= 1")

    if not 0 <= args.rag_overlap_words < args.rag_chunk_words:
        parser.error(
            "--rag-overlap-words must be >= 0 and smaller than --rag-chunk-words"
        )

    return args


def main() -> None:
    args = parse_args()

    data = load_json(args.input, "Base dataset")

    required_sections = ("papers", "researchers", "opportunities")
    missing_sections = [key for key in required_sections if key not in data]
    if missing_sections:
        raise SystemExit(
            "Base dataset is missing required section(s): "
            + ", ".join(missing_sections)
        )

    supplemental_summary = None
    supplemental_used = False

    if not args.no_supplemental:
        if args.supplemental.exists():
            supplemental = load_json(args.supplemental, "Supplemental dataset")
            supplemental_summary = merge_supplemental(data, supplemental)
            supplemental_used = True
        elif args.supplemental != DEFAULT_SUPPLEMENTAL:
            raise SystemExit(
                f"Supplemental file explicitly requested but not found: {args.supplemental}"
            )
        else:
            print(
                f"Supplemental file not found at {args.supplemental}; "
                "continuing with base dataset only."
            )

    papers = data["papers"]
    researchers = data["researchers"]
    opportunities = data["opportunities"]

    args.output.mkdir(parents=True, exist_ok=True)

    paper_by_researcher: defaultdict[str, list[dict]] = defaultdict(list)
    for paper in papers:
        for auid in paper.get("researcher_auids", []):
            paper_by_researcher[auid].append(paper)

    # ------------------------------------------------------------------
    # Paper metrics
    # ------------------------------------------------------------------
    paper_rows = []

    for paper in papers:
        title = clean_text(paper.get("title"))
        abstract = clean_text(paper.get("abstract"))
        summary = clean_text(paper.get("summary"))
        p_input = title_keywords_input(paper)

        paper_rows.append(
            {
                "id": paper["id"],
                "title": title,
                "title_words": word_count(title),
                "title_chars": len(title),
                "abstract_words": word_count(abstract),
                "abstract_chars": len(abstract),
                "summary_words": word_count(summary),
                "keyword_count": len(paper.get("keywords", [])),
                "researcher_links": len(paper.get("researcher_auids", [])),
                "embedding_input_words": word_count(p_input),
                "_input": p_input,
            }
        )

    # ------------------------------------------------------------------
    # Opportunity metrics
    # ------------------------------------------------------------------
    opp_rows = []

    for opp in opportunities:
        title = clean_text(opp.get("title"))
        description = clean_text(opp.get("description"))
        full_announcement = clean_text(opp.get("full_announcement"))

        short_input = opportunity_input(opp)
        full_input = opportunity_full_input(opp)

        full_words = word_count(full_announcement)

        opp_rows.append(
            {
                "opp_id": opp["opp_id"],
                "title": title,
                "title_words": word_count(title),
                "description_words": word_count(description),
                "description_chars": len(description),
                "full_announcement_words": full_words,
                "full_announcement_chars": len(full_announcement),
                "has_full_announcement": bool(full_announcement),
                "has_html": bool(
                    re.search(
                        r"<\s*/?\s*[A-Za-z][^>]*>",
                        str(opp.get("description") or ""),
                    )
                ),
                "provided_topics": len(opp.get("topics", [])),
                "provided_domains": len(opp.get("domains", [])),
                "embedding_input_words": word_count(short_input),
                "full_announcement_input_words": word_count(full_input),
                "estimated_rag_chunks": estimated_chunk_count(
                    full_words,
                    args.rag_chunk_words,
                    args.rag_overlap_words,
                ),
                "_input": short_input,
                "_full_input": full_input,
            }
        )

    # ------------------------------------------------------------------
    # Researcher aggregate metrics
    # ------------------------------------------------------------------
    researcher_rows = []

    for researcher in researchers:
        r_papers = paper_by_researcher[researcher["auid"]]

        researcher_input = (
            f"Researcher: {clean_text(researcher.get('name'))}\n"
            + "\n\n".join(title_keywords_input(paper) for paper in r_papers)
        )

        researcher_rows.append(
            {
                "auid": researcher["auid"],
                "name": clean_text(researcher.get("name")),
                "papers": len(r_papers),
                "papers_with_abstract": sum(
                    bool(clean_text(p.get("abstract"))) for p in r_papers
                ),
                "expertise_provided": bool(researcher.get("expertise")),
                "embedding_input_words": word_count(researcher_input),
                "_input": researcher_input,
            }
        )

    # ------------------------------------------------------------------
    # Dataset-wide counts
    # ------------------------------------------------------------------
    keyword_counts = Counter(
        clean_text(keyword.get("keyword")).casefold()
        for paper in papers
        for keyword in paper.get("keywords", [])
        if keyword.get("keyword")
    )

    known_auids = {researcher["auid"] for researcher in researchers}

    all_paper_auids = [
        auid
        for paper in papers
        for auid in paper.get("researcher_auids", [])
    ]

    matched_links = sum(
        auid in known_auids
        for auid in all_paper_auids
    )

    normalized_titles = [
        clean_text(paper.get("title")).casefold()
        for paper in papers
        if clean_text(paper.get("title"))
    ]
    duplicate_titles = len(normalized_titles) - len(set(normalized_titles))

    full_announcement_rows = [
        row for row in opp_rows if row["has_full_announcement"]
    ]

    stats = {
        "source": {
            "base": str(args.input),
            "supplemental": (
                str(args.supplemental) if supplemental_used else None
            ),
            "supplemental_used": supplemental_used,
            "supplemental_summary": supplemental_summary,
        },
        "rag_chunk_estimate": {
            "chunk_words": args.rag_chunk_words,
            "overlap_words": args.rag_overlap_words,
            "note": (
                "Planning estimate only; final RAG chunking should respect "
                "document structure/headings rather than fixed word counts alone."
            ),
        },
        "record_counts": {
            "researchers": len(researchers),
            "papers": len(papers),
            "opportunities": len(opportunities),
            "papers_with_abstract": sum(
                bool(clean_text(paper.get("abstract")))
                for paper in papers
            ),
            "opportunities_with_full_announcement": len(
                full_announcement_rows
            ),
            "paper_keyword_records": sum(
                len(paper.get("keywords", []))
                for paper in papers
            ),
            "unique_keyword_phrases_casefolded": len(keyword_counts),
            "paper_researcher_references_in_source": len(all_paper_auids),
            "paper_researcher_links_matching_25_researchers": matched_links,
            "paper_researcher_references_to_external_researchers": (
                len(all_paper_auids) - matched_links
            ),
            "distinct_external_researcher_auids": len(
                set(all_paper_auids) - known_auids
            ),
            "provided_opportunity_topics": sum(
                len(opp.get("topics", []))
                for opp in opportunities
            ),
            "provided_opportunity_domains": sum(
                len(opp.get("domains", []))
                for opp in opportunities
            ),
            "duplicate_paper_titles_not_necessarily_duplicate_papers": (
                duplicate_titles
            ),
        },
        "missingness": {
            "researcher_expertise": sum(
                not researcher.get("expertise")
                for researcher in researchers
            ),
            "paper_abstract": sum(
                not clean_text(paper.get("abstract"))
                for paper in papers
            ),
            "paper_summary": sum(
                not clean_text(paper.get("summary"))
                for paper in papers
            ),
            "paper_title": sum(
                not clean_text(paper.get("title"))
                for paper in papers
            ),
            "paper_publication_date": sum(
                not paper.get("publication_date")
                for paper in papers
            ),
            "paper_published_in": sum(
                not paper.get("published_in")
                for paper in papers
            ),
            "opportunity_summary": sum(
                not clean_text(opp.get("summary"))
                for opp in opportunities
            ),
            "opportunity_description": sum(
                not clean_text(opp.get("description"))
                for opp in opportunities
            ),
            "opportunity_full_announcement": sum(
                not clean_text(opp.get("full_announcement"))
                for opp in opportunities
            ),
            "opportunities_without_provided_topics": sum(
                not opp.get("topics")
                for opp in opportunities
            ),
            "opportunities_without_provided_domains": sum(
                not opp.get("domains")
                for opp in opportunities
            ),
            "opportunity_description_with_html": sum(
                row["has_html"] for row in opp_rows
            ),
        },
        "words": {
            "paper_title": describe(
                [row["title_words"] for row in paper_rows]
            ),
            "paper_abstract_all_records": describe(
                [row["abstract_words"] for row in paper_rows]
            ),
            "paper_abstract_available_only": describe(
                [
                    row["abstract_words"]
                    for row in paper_rows
                    if row["abstract_words"] > 0
                ]
            ),
            "paper_embedding_input": describe(
                [row["embedding_input_words"] for row in paper_rows]
            ),
            "opportunity_title": describe(
                [row["title_words"] for row in opp_rows]
            ),
            "opportunity_clean_description": describe(
                [row["description_words"] for row in opp_rows]
            ),
            "opportunity_short_embedding_input": describe(
                [row["embedding_input_words"] for row in opp_rows]
            ),
            "opportunity_full_announcement_available_only": describe(
                [
                    row["full_announcement_words"]
                    for row in full_announcement_rows
                ]
            ),
            "opportunity_full_announcement_input_available_only": describe(
                [
                    row["full_announcement_input_words"]
                    for row in full_announcement_rows
                ]
            ),
            "researcher_aggregate_embedding_input": describe(
                [row["embedding_input_words"] for row in researcher_rows]
            ),
        },
        "characters": {
            "paper_title": describe(
                [row["title_chars"] for row in paper_rows]
            ),
            "paper_abstract_available_only": describe(
                [
                    row["abstract_chars"]
                    for row in paper_rows
                    if row["abstract_chars"] > 0
                ]
            ),
            "opportunity_clean_description": describe(
                [row["description_chars"] for row in opp_rows]
            ),
            "opportunity_full_announcement_available_only": describe(
                [
                    row["full_announcement_chars"]
                    for row in full_announcement_rows
                ]
            ),
        },
        "histograms": {
            "paper_title_words": bin_counts(
                [row["title_words"] for row in paper_rows],
                [0, 5, 10, 15, 20, 30],
            ),
            "paper_abstract_words": bin_counts(
                [row["abstract_words"] for row in paper_rows],
                [0, 1, 100, 200, 400, 800],
            ),
            "opportunity_description_words": bin_counts(
                [row["description_words"] for row in opp_rows],
                [0, 50, 100, 200, 400],
            ),
            "opportunity_full_announcement_words": bin_counts(
                [row["full_announcement_words"] for row in opp_rows],
                [0, 1, 2500, 5000, 10000, 20000, 30000],
            ),
            "opportunity_estimated_rag_chunks": bin_counts(
                [row["estimated_rag_chunks"] for row in opp_rows],
                [0, 1, 6, 11, 21, 41, 61],
            ),
        },
        "rag_chunk_counts": {
            "available_announcements": len(full_announcement_rows),
            "total_estimated_chunks": sum(
                row["estimated_rag_chunks"]
                for row in full_announcement_rows
            ),
            "distribution": describe(
                [
                    row["estimated_rag_chunks"]
                    for row in full_announcement_rows
                ]
            ),
        },
        "longest_paper_abstracts": sorted(
            [
                {
                    "id": row["id"],
                    "title": row["title"],
                    "abstract_words": row["abstract_words"],
                    "embedding_input_words": row["embedding_input_words"],
                }
                for row in paper_rows
                if row["abstract_words"] > 0
            ],
            key=lambda row: row["abstract_words"],
            reverse=True,
        )[:5],
        "longest_opportunity_descriptions": sorted(
            [
                {
                    "opp_id": row["opp_id"],
                    "title": row["title"],
                    "description_words": row["description_words"],
                    "embedding_input_words": row["embedding_input_words"],
                }
                for row in opp_rows
            ],
            key=lambda row: row["description_words"],
            reverse=True,
        )[:5],
        "longest_full_announcements": sorted(
            [
                {
                    "opp_id": row["opp_id"],
                    "title": row["title"],
                    "full_announcement_words": row[
                        "full_announcement_words"
                    ],
                    "estimated_rag_chunks": row["estimated_rag_chunks"],
                }
                for row in full_announcement_rows
            ],
            key=lambda row: row["full_announcement_words"],
            reverse=True,
        )[:10],
        "shortest_opportunity_descriptions": sorted(
            [
                {
                    "opp_id": row["opp_id"],
                    "title": row["title"],
                    "description_words": row["description_words"],
                }
                for row in opp_rows
            ],
            key=lambda row: row["description_words"],
        )[:5],
        "opportunities_without_full_announcement": [
            {
                "opp_id": row["opp_id"],
                "title": row["title"],
            }
            for row in opp_rows
            if not row["has_full_announcement"]
        ],
        "papers_without_abstract": [
            {
                "id": row["id"],
                "title": row["title"],
            }
            for row in paper_rows
            if row["abstract_words"] == 0
        ],
        "most_common_keywords": keyword_counts.most_common(15),
    }

    # ------------------------------------------------------------------
    # Record-level output
    # ------------------------------------------------------------------
    for rows in (paper_rows, opp_rows, researcher_rows):
        for row in rows:
            row.pop("_input", None)
            row.pop("_full_input", None)

    args.output.joinpath("statistics.json").write_text(
        json.dumps(
            stats,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    args.output.joinpath("record_metrics.json").write_text(
        json.dumps(
            {
                "papers": paper_rows,
                "opportunities": opp_rows,
                "researchers": researcher_rows,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # ------------------------------------------------------------------
    # Markdown report
    # ------------------------------------------------------------------
    report = [
        "# Senior Design dataset analysis",
        "",
        f"Base input: `{args.input}`.",
        (
            f"Supplemental input: `{args.supplemental}`."
            if supplemental_used
            else "Supplemental input: not used."
        ),
        "All word counts use whitespace-separated words on cleaned text.",
        "",
        "## Records and missing data",
        "",
        "| Metric | Count |",
        "|---|---:|",
    ]

    for key, value in stats["record_counts"].items():
        report.append(
            f"| {key.replace('_', ' ').title()} | {value} |"
        )

    for key, value in stats["missingness"].items():
        report.append(
            f"| Missing: {key.replace('_', ' ')} | {value} |"
        )

    if supplemental_summary:
        report += [
            "",
            "## Supplemental source validation",
            "",
            "| Metric | Count |",
            "|---|---:|",
        ]

        for key, value in supplemental_summary.items():
            report.append(
                f"| {key.replace('_', ' ').title()} | {value} |"
            )

    report += [
        "",
        "## Word length distributions",
        "",
        "| Field | Min | Q1 | Median | Mean | Q3 | Max |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]

    for name, dist in stats["words"].items():
        report.append(
            f"| {name.replace('_', ' ').title()} | "
            + " | ".join(
                str(dist[key])
                for key in (
                    "minimum",
                    "q1",
                    "median",
                    "mean",
                    "q3",
                    "maximum",
                )
            )
            + " |"
        )

    report += [
        "",
        "## Paper abstract word-count histogram",
        "",
        "| Word range | Papers |",
        "|---|---:|",
    ]

    for key, value in stats["histograms"]["paper_abstract_words"].items():
        report.append(f"| {key} | {value} |")

    report += [
        "",
        "## Full-announcement word-count histogram",
        "",
        "| Word range | Opportunities |",
        "|---|---:|",
    ]

    for key, value in stats["histograms"][
        "opportunity_full_announcement_words"
    ].items():
        report.append(f"| {key} | {value} |")

    report += [
        "",
        "## Longest paper abstracts",
        "",
        "| ID | Title | Abstract words | Current embedding-input words |",
        "|---:|---|---:|---:|",
    ]

    for paper in stats["longest_paper_abstracts"]:
        report.append(
            f"| {paper['id']} | "
            f"{paper['title'].replace('|', '/')} | "
            f"{paper['abstract_words']} | "
            f"{paper['embedding_input_words']} |"
        )

    report += [
        "",
        "## Longest full funding announcements",
        "",
        "| ID | Title | Full announcement words | Estimated RAG chunks |",
        "|---:|---|---:|---:|",
    ]

    for opp in stats["longest_full_announcements"]:
        report.append(
            f"| {opp['opp_id']} | "
            f"{opp['title'].replace('|', '/')} | "
            f"{opp['full_announcement_words']} | "
            f"{opp['estimated_rag_chunks']} |"
        )

    report += [
        "",
        "## Full-announcement RAG planning estimate",
        "",
        (
            f"Planning assumption: approximately {args.rag_chunk_words} words "
            f"per chunk with {args.rag_overlap_words} words of overlap."
        ),
        "",
        f"- Announcements available: {stats['rag_chunk_counts']['available_announcements']}",
        f"- Estimated total chunks: {stats['rag_chunk_counts']['total_estimated_chunks']}",
        (
            "- Estimated chunks per available announcement: "
            f"median {stats['rag_chunk_counts']['distribution']['median']}, "
            f"maximum {stats['rag_chunk_counts']['distribution']['maximum']}."
        ),
        "",
        "> This is only a planning estimate. Final RAG chunking should use "
        "announcement structure and section headings where possible.",
        "",
        "## Opportunities without full announcement",
        "",
        "| ID | Title |",
        "|---:|---|",
    ]

    for opp in stats["opportunities_without_full_announcement"]:
        report.append(
            f"| {opp['opp_id']} | {opp['title'].replace('|', '/')} |"
        )

    report += [
        "",
        "## Papers without abstract/description",
        "",
        "| ID | Title |",
        "|---:|---|",
    ]

    for paper in stats["papers_without_abstract"]:
        report.append(
            f"| {paper['id']} | {paper['title'].replace('|', '/')} |"
        )

    report += [
        "",
        "## Interpretation",
        "",
        (
            "- The supplemental source substantially improves paper-level "
            "semantic evidence because most papers now have an abstract/description."
        ),
        (
            "- Full funding announcements are intentionally kept separate from "
            "the short opportunity description. They are better suited to "
            "section-aware chunking/retrieval than to one whole-document embedding."
        ),
        (
            "- Researcher aggregate inputs now include paper abstracts where "
            "available, so their lengths may increase substantially. This is "
            "another reason to compare task-specific representations rather than "
            "force one aggregate vector strategy."
        ),
        (
            "- Embedding-model selection is handled by the separate human semantic "
            "benchmark and task-specific evaluations, not by this dataset analysis."
        ),
        (
            "- Some opportunity records still have no recovered full announcement; "
            "those records should remain flagged rather than having missing text invented."
        ),
        (
            "- The estimated RAG chunk counts are capacity-planning numbers only. "
            "Final retrieval experiments should prefer meaningful document sections "
            "such as purpose, research scope, eligibility, requirements, and review criteria."
        ),
    ]

    args.output.joinpath("analysis_report.md").write_text(
        "\n".join(report) + "\n",
        encoding="utf-8",
    )

    # ------------------------------------------------------------------
    # Optional charts
    # ------------------------------------------------------------------
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed; skipping PNG charts")
    else:
        charts = (
            (
                "paper_abstract_histogram.png",
                "Paper abstract / description lengths",
                "Number of papers",
                stats["histograms"]["paper_abstract_words"],
            ),
            (
                "opportunity_description_histogram.png",
                "Short funding-description lengths",
                "Number of opportunities",
                stats["histograms"]["opportunity_description_words"],
            ),
            (
                "opportunity_full_announcement_histogram.png",
                "Full funding-announcement lengths",
                "Number of opportunities",
                stats["histograms"]["opportunity_full_announcement_words"],
            ),
            (
                "opportunity_rag_chunk_histogram.png",
                "Estimated chunks per full announcement",
                "Number of opportunities",
                stats["histograms"]["opportunity_estimated_rag_chunks"],
            ),
        )

        for filename, title, y_label, histogram in charts:
            fig, ax = plt.subplots(figsize=(9, 4.5))
            bars = ax.bar(
                list(histogram),
                list(histogram.values()),
            )
            ax.bar_label(bars, padding=3)
            ax.set(
                title=title,
                xlabel="Range",
                ylabel=y_label,
            )

            maximum = max(histogram.values()) if histogram else 0
            ax.set_ylim(0, max(1, maximum * 1.2))

            fig.tight_layout()
            fig.savefig(
                args.output / filename,
                dpi=150,
            )
            plt.close(fig)

    # ------------------------------------------------------------------
    # Console summary
    # ------------------------------------------------------------------
    print(
        f"Processed: {len(researchers)} researchers, "
        f"{len(papers)} papers, "
        f"{len(opportunities)} opportunities"
    )
    print(
        "Paper abstracts/descriptions available:",
        stats["record_counts"]["papers_with_abstract"],
    )
    print(
        "Full opportunity announcements available:",
        stats["record_counts"]["opportunities_with_full_announcement"],
    )
    print(
        "Paper abstract word statistics (available only):",
        stats["words"]["paper_abstract_available_only"],
    )
    print(
        "Full announcement word statistics (available only):",
        stats["words"][
            "opportunity_full_announcement_available_only"
        ],
    )
    print(
        "Estimated total RAG chunks:",
        stats["rag_chunk_counts"]["total_estimated_chunks"],
    )
    print(
        "Researcher aggregate input word statistics:",
        stats["words"]["researcher_aggregate_embedding_input"],
    )


    print(
        "Wrote",
        args.output / "analysis_report.md",
        args.output / "statistics.json",
        args.output / "record_metrics.json",
    )


if __name__ == "__main__":
    main()
