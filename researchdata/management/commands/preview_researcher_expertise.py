"""Preview publication-supported expertise topics, without changing shared MySQL.

Run:
    python manage.py preview_researcher_expertise --dry-run --sample 5
    python manage.py preview_researcher_expertise

This is an explainable baseline, not a final model-generated profile.
Review output before changing ResearcherExpertise records or embeddings.
"""

import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from researchdata.models import Researcher


def canonical_keyword(value):
    """Conservative spelling/punctuation normalization; no semantic merging."""
    value = unicodedata.normalize("NFKC", str(value or ""))
    value = value.replace("’", "'").replace("‘", "'")
    value = value.replace("‐", "-").replace("‑", "-").replace("–", "-").replace("—", "-")
    value = value.casefold()
    value = re.sub(r"[^\w\s']", " ", value)
    return " ".join(value.split())


def compact_join(phrases):
    if not phrases:
        return ""
    if len(phrases) == 1:
        return phrases[0]
    if len(phrases) == 2:
        return f"{phrases[0]} and {phrases[1]}"
    return ", ".join(phrases[:-1]) + f", and {phrases[-1]}"


def collect_researchers(researchers):
    """Gather one vote per paper per keyword, preserving source-paper evidence."""
    collected = []
    for researcher in researchers:
        grouped = defaultdict(dict)
        labels = defaultdict(Counter)
        paper_ids = set()
        for paper in researcher.papers.all():
            paper_id = str(paper.id)
            paper_ids.add(paper_id)
            title = str(paper.title or "")
            for item in paper.keywords.all():
                term = canonical_keyword(item.keyword)
                if not term:
                    continue
                source_score = float(item.score) if item.score is not None else 0.0
                # Duplicate spellings in the same paper are one occurrence.
                previous = grouped[term].get(paper_id)
                if previous is None or source_score > previous["keyword_score"]:
                    grouped[term][paper_id] = {
                        "paper_id": paper_id,
                        "paper_title": title,
                        "keyword_score": round(source_score, 6),
                    }
                labels[term][str(item.keyword).strip()] += 1
        collected.append({
            "id": str(researcher.auid),
            "name": researcher.name,
            "paper_count": len(paper_ids),
            "terms": grouped,
            "labels": labels,
        })
    return collected


def build_profiles(researchers, top=6, secondary=3, min_support=2):
    collected = collect_researchers(researchers)
    # Document frequency here counts researchers not individual papers.
    researcher_df = Counter(term for person in collected for term in person["terms"])
    researcher_count = len(collected)
    profiles = []

    for person in collected:
        scored = []
        for term, papers in person["terms"].items():
            support = len(papers)
            mean_source_score = sum(p["keyword_score"] for p in papers.values()) / support
            idf = math.log((researcher_count + 1) / (researcher_df[term] + 1))
            # Recurrence matters most. moderate IDF reduces generic cross-researcher terms
            # This is a ranking heuristic, NOT an estimated confidence/probability.
            rank_score = mean_source_score * (1 + math.log2(support)) * (1 + 0.15 * idf)
            label = sorted(
                person["labels"][term].items(),
                key=lambda pair: (-pair[1], len(pair[0]), pair[0].casefold()),
            )[0][0]
            scored.append({
                "topic": label,
                "canonical_topic": term,
                "paper_support": support,
                "mean_source_keyword_score": round(mean_source_score, 4),
                "researcher_document_frequency": researcher_df[term],
                "ranking_score": round(rank_score, 4),
                "evidence": sorted(papers.values(), key=lambda p: int(p["paper_id"])),
            })
        scored.sort(key=lambda x: (-x["ranking_score"], -x["paper_support"], x["canonical_topic"]))
        recurring = [x for x in scored if x["paper_support"] >= min_support][:top]
        single_paper = [x for x in scored if x["paper_support"] < min_support][:secondary]
        if recurring:
            description = (
                "Publications repeatedly address "
                + compact_join([x["topic"] for x in recurring[:5]])
                + "."
            )
        elif scored:
            description = (
                "Available publications mention "
                + compact_join([x["topic"] for x in scored[:5]])
                + "; none of these keywords meets the repeated-paper threshold."
            )
        else:
            description = "No paper keywords are available to infer research expertise."
        profiles.append({
            "researcher_id": person["id"],
            "researcher_name": person["name"],
            "paper_count": person["paper_count"],
            "expertise_description_draft": description,
            "recurring_topics": recurring,
            "single_paper_topics_for_review": single_paper,
            "unique_keyword_count": len(scored),
        })
    return profiles


class Command(BaseCommand):
    help = "Preview evidence-linked researcher expertise from scored paper keywords; does not modify MySQL."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Display sample profiles only; no output file.")
        parser.add_argument("--sample", type=int, default=5, help="Number of example researchers to print (default: 5).")
        parser.add_argument("--top", type=int, default=6, help="Maximum recurring topics per researcher (default: 6).")
        parser.add_argument("--secondary", type=int, default=3, help="One-paper topics to show for review (default: 3).")
        parser.add_argument("--min-support", type=int, default=2, help="Paper count required for recurring topic (default: 2).")
        parser.add_argument(
            "--output", default="data/expertise/researcher_expertise_preview.json",
            help="Local review JSON; shared database is never changed.",
        )

    def handle(self, *args, **options):
        for key in ("top", "min_support"):
            if options[key] < 1:
                raise CommandError(f"--{key.replace('_', '-')} must be >= 1")
        if options["sample"] < 0 or options["secondary"] < 0:
            raise CommandError("--sample and --secondary must be >= 0")

        researchers = list(
            Researcher.objects.prefetch_related("papers__keywords").order_by("auid")
        )
        profiles = build_profiles(
            researchers,
            top=options["top"],
            secondary=options["secondary"],
            min_support=options["min_support"],
        )
        self.stdout.write(f"Built expertise previews for {len(profiles)} researchers.")
        for item in profiles[:options["sample"]]:
            self.stdout.write(f"\n{item['researcher_name']} ({item['paper_count']} papers)")
            self.stdout.write(item["expertise_description_draft"])
            for topic in item["recurring_topics"]:
                self.stdout.write(
                    f"  {topic['topic']} — {topic['paper_support']} distinct papers; "
                    f"rank score {topic['ranking_score']:.3f}"
                )
            if not item["recurring_topics"]:
                self.stdout.write("  No recurring topics at current threshold; manually review single-paper terms.")

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("Dry run complete; MySQL unchanged, no file created."))
            return

        output_path = Path(options["output"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "method": "per-researcher distinct-paper recurrence + mean source score + modest researcher IDF",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "min_paper_support": options["min_support"],
            "researcher_count": len(profiles),
            "review_required": True,
            "notes": [
                "Candidate phrases come only from imported paper keywords; no subjects are invented.",
                "Rank score is a heuristic for sorting phrases, not a confidence probability.",
                "Near-synonym semantic clustering and human approval are subsequent steps.",
                "This export is for inspection, not a replacement for the shared MySQL database.",
            ],
            "researchers": profiles,
        }
        temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, allow_nan=False)
        temp_path.replace(output_path)
        self.stdout.write(self.style.SUCCESS(f"Saved preview to {output_path}; MySQL unchanged."))
