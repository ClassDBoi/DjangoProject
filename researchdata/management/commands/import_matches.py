"""Import researcher-opportunity matches produced by the matching pipeline.

Source: the matches.json written by

    python matching_pipeline\\run_pipeline.py match

(see matching_pipeline/README.md).

Usage (dry run by default; nothing is written without --apply):

    python manage.py import_matches matching_pipeline\\runs\\matches\\matches.json
    python manage.py import_matches <file> --apply

Behavior:
- Writes only to the project-created ausme_* tables; client tables are never changed.
- The run is named after its folder (e.g. "matches") unless --name is given.
  Importing a run with an existing name replaces that run.
- The imported run becomes the active run served by the API (use --no-activate to skip).
- --cutoff sets the semantic similarity below which matches are not shown
  (default 0.50, from the team's blind review of matches, 2026-11).
- Fails without writing anything if a researcher, opportunity or paper in the file
  is not in the database, or if the file came from a mock (test) run.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from researchdata.models import (
    MatchEvidence,
    MatchRun,
    Opportunity,
    Paper,
    Researcher,
    ResearcherOpportunityMatch,
)

REASON_NO_TOPICS = "no_research_topics"      # only administrative or career-stage topics were found
REASON_NO_TEXT = "insufficient_text"         # too little announcement text to extract topics


class Command(BaseCommand):
    help = "Import researcher-opportunity matches (matches.json) into the ausme_* tables."

    def add_arguments(self, parser):
        parser.add_argument("file", type=Path, help="Path to matches.json")
        parser.add_argument("--name", help="Run name (default: the file's folder name)")
        parser.add_argument("--cutoff", type=float, default=0.5,
                            help="Semantic similarity below which matches are not shown (default 0.50)")
        parser.add_argument("--apply", action="store_true", help="Write to the database")
        parser.add_argument("--no-activate", action="store_true",
                            help="Import without making this the run the API serves")

    def handle(self, *args, **options):
        path = options["file"]
        if not path.exists():
            raise CommandError(f"File not found: {path}")

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise CommandError(f"Could not read {path}: {exc}") from exc

        if data.get("mock"):
            raise CommandError("This file came from a mock (test) run and has no real similarities.")

        rows = data.get("matches")
        if not isinstance(rows, list) or not rows:
            raise CommandError("The file has no 'matches' list.")
        if "evidence" not in rows[0]:
            raise CommandError("These matches have no structured evidence. Re-run the match step "
                               "with matching_pipeline/run_pipeline.py.")

        name = options["name"] or path.parent.name
        cutoff = options["cutoff"]

        researchers = set(Researcher.objects.values_list("auid", flat=True))
        opportunities = set(Opportunity.objects.values_list("opp_id", flat=True))
        papers = set(Paper.objects.values_list("id", flat=True))

        missing = set()
        for row in rows:
            if row["auid"] not in researchers:
                missing.add(f"researcher {row['auid']}")
            if int(row["opp_id"]) not in opportunities:
                missing.add(f"opportunity {row['opp_id']}")
            for link in row["evidence"]:
                for paper_id in link.get("paper_ids", [])[:1]:
                    if int(paper_id) not in papers:
                        missing.add(f"paper {paper_id}")
        if missing:
            raise CommandError("Not in the database: " + ", ".join(sorted(missing)[:20]))

        matched_opps = {int(row["opp_id"]) for row in rows}
        no_topics = {int(o) for o in data.get("opportunities_not_matched", [])}
        unmatched = {}
        for opp_id in sorted(opportunities - matched_opps):
            unmatched[str(opp_id)] = REASON_NO_TOPICS if opp_id in no_topics else REASON_NO_TEXT

        shown = sum(1 for row in rows if row["strongest_links_similarity"] >= cutoff)
        self.stdout.write(
            f"Run '{name}': {len(rows)} matches, {len({r['auid'] for r in rows})} researchers, "
            f"{len(matched_opps)} opportunities, {sum(len(r['evidence']) for r in rows)} evidence links.\n"
            f"{shown} matches at or above the {cutoff:.2f} semantic similarity cutoff.\n"
            f"Opportunities not matched: {len(unmatched)} "
            f"({', '.join(f'{k}: {v}' for k, v in unmatched.items()) or 'none'})."
        )

        if not options["apply"]:
            self.stdout.write(self.style.WARNING("Dry run: nothing written. Add --apply to import."))
            return

        with transaction.atomic():
            MatchRun.objects.filter(name=name).delete()
            run = MatchRun.objects.create(
                name=name,
                embedding_model=data.get("embedding_model", ""),
                embedding_revision=data.get("embedding_revision", "") or "",
                generator=data.get("generator", "") or "",
                scoring=data.get("scoring", "") or "",
                description=data.get("scoring_description", "") or "",
                similarity_cutoff=cutoff,
                unmatched_opportunities=unmatched,
            )

            matches = ResearcherOpportunityMatch.objects.bulk_create([
                ResearcherOpportunityMatch(
                    run=run,
                    researcher_id=row["auid"],
                    opportunity_id=int(row["opp_id"]),
                    rank_for_researcher=int(row["rank_for_researcher"]),
                    rank_for_opportunity=int(row["rank_for_opportunity"]),
                    semantic_similarity=float(row["strongest_links_similarity"]),
                    ranking_score=float(row.get("ranking_score", row["strongest_links_similarity"])),
                )
                for row in rows
            ])

            # bulk_create does not return primary keys on every database, so look them up.
            ids = {
                (m.researcher_id, m.opportunity_id): m.id
                for m in ResearcherOpportunityMatch.objects.filter(run=run)
            }
            evidence = []
            for row in rows:
                match_id = ids[(row["auid"], int(row["opp_id"]))]
                for position, link in enumerate(row["evidence"], start=1):
                    paper_ids = link.get("paper_ids") or []
                    evidence.append(MatchEvidence(
                        match_id=match_id,
                        position=position,
                        opportunity_topic=link["opportunity_topic"][:255],
                        researcher_term=link["researcher_term"][:255],
                        paper_id=int(paper_ids[0]) if paper_ids else None,
                        other_paper_count=max(0, len(paper_ids) - 1),
                        semantic_similarity=float(link["semantic_similarity"]),
                    ))
            MatchEvidence.objects.bulk_create(evidence, batch_size=500)

            if not options["no_activate"]:
                MatchRun.objects.exclude(pk=run.pk).update(is_active=False)
                run.is_active = True
                run.save(update_fields=["is_active"])

        self.stdout.write(self.style.SUCCESS(
            f"Imported run '{name}' ({len(matches)} matches, {len(evidence)} evidence links)"
            + ("" if options["no_activate"] else "; it is now the active run.")
        ))
