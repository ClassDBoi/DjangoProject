"""Safely import supplemental paper descriptions and opportunity full announcements.

Source JSON shape:
{
  "opportunities": [
    {"opp_id": 45638, "full_announcement": "..."},
    ...
  ],
  "papers": [
    {"paper_id": 1065, "description": "..."},
    ...
  ]
}

Behavior:
- Dry-run by default.
- Requires --apply to write to MySQL.
- Never creates Paper or Opportunity rows.
- Never overwrites non-empty destination fields unless --overwrite is passed.
- Updates Paper.abstract from source "description".
- Updates Opportunity.full_announcement from source "full_announcement".
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from researchdata.models import Opportunity, Paper


def _clean_text(value):
    """Normalize only outer whitespace; preserve internal announcement formatting."""
    if value is None:
        return ""
    return str(value).strip()


def _index_unique(records, key_name, section_name):
    """Return {id: record}; fail loudly on malformed/duplicate IDs."""
    if not isinstance(records, list):
        raise CommandError(f"Top-level '{section_name}' must be a list.")

    indexed = {}
    for i, row in enumerate(records, start=1):
        if not isinstance(row, dict):
            raise CommandError(
                f"{section_name}[{i}] must be an object, got {type(row).__name__}."
            )

        raw_id = row.get(key_name)
        if raw_id is None:
            raise CommandError(
                f"{section_name}[{i}] is missing required key '{key_name}'."
            )

        try:
            record_id = int(raw_id)
        except (TypeError, ValueError) as exc:
            raise CommandError(
                f"{section_name}[{i}] has invalid {key_name}: {raw_id!r}"
            ) from exc

        if record_id in indexed:
            raise CommandError(
                f"Duplicate {key_name} {record_id} found in '{section_name}'."
            )

        indexed[record_id] = row

    return indexed


class Command(BaseCommand):
    help = (
        "Import supplemental paper descriptions and opportunity full announcements. "
        "Dry-run by default; use --apply to write changes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--input",
            required=True,
            help="Path to senior_design_full_announcements.json",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually write changes to the database. Without this flag, dry-run only.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help=(
                "Allow replacing an already non-empty Paper.abstract or "
                "Opportunity.full_announcement. Use only deliberately."
            ),
        )

    def handle(self, *args, **options):
        input_path = Path(options["input"]).expanduser()

        if not input_path.exists():
            raise CommandError(f"Input file not found: {input_path}")
        if not input_path.is_file():
            raise CommandError(f"Input path is not a file: {input_path}")

        try:
            source = json.loads(input_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise CommandError(f"Could not read valid JSON from {input_path}: {exc}") from exc

        if not isinstance(source, dict):
            raise CommandError("Top-level JSON value must be an object.")

        opportunity_rows = _index_unique(
            source.get("opportunities", []),
            "opp_id",
            "opportunities",
        )
        paper_rows = _index_unique(
            source.get("papers", []),
            "paper_id",
            "papers",
        )

        if not opportunity_rows and not paper_rows:
            raise CommandError("No opportunity or paper records found in the source file.")

        # Load only IDs present in the supplemental source.
        db_opportunities = Opportunity.objects.in_bulk(opportunity_rows.keys(), field_name="opp_id")
        db_papers = Paper.objects.in_bulk(paper_rows.keys(), field_name="id")

        unknown_opportunity_ids = sorted(set(opportunity_rows) - set(db_opportunities))
        unknown_paper_ids = sorted(set(paper_rows) - set(db_papers))

        # Safety rule: this importer supplements existing rows only.
        if unknown_opportunity_ids or unknown_paper_ids:
            details = []
            if unknown_opportunity_ids:
                details.append(
                    "Unknown opportunity IDs: "
                    + ", ".join(map(str, unknown_opportunity_ids[:25]))
                    + (" ..." if len(unknown_opportunity_ids) > 25 else "")
                )
            if unknown_paper_ids:
                details.append(
                    "Unknown paper IDs: "
                    + ", ".join(map(str, unknown_paper_ids[:25]))
                    + (" ..." if len(unknown_paper_ids) > 25 else "")
                )
            raise CommandError(
                "Source contains IDs that do not already exist in the database. "
                "No changes were made.\n" + "\n".join(details)
            )

        paper_updates = []
        paper_skipped_existing = []
        paper_empty_source = []

        for paper_id, row in sorted(paper_rows.items()):
            description = _clean_text(row.get("description"))
            if not description:
                paper_empty_source.append(paper_id)
                continue

            paper = db_papers[paper_id]
            current = _clean_text(paper.abstract)

            if current and not options["overwrite"]:
                paper_skipped_existing.append(paper_id)
                continue

            if current == description:
                # Already identical; do not issue a needless UPDATE.
                continue

            paper.abstract = description
            paper_updates.append(paper)

        opportunity_updates = []
        opportunity_skipped_existing = []
        opportunity_empty_source = []

        for opp_id, row in sorted(opportunity_rows.items()):
            full_announcement = _clean_text(row.get("full_announcement"))
            if not full_announcement:
                opportunity_empty_source.append(opp_id)
                continue

            opportunity = db_opportunities[opp_id]
            current = _clean_text(opportunity.full_announcement)

            if current and not options["overwrite"]:
                opportunity_skipped_existing.append(opp_id)
                continue

            if current == full_announcement:
                continue

            opportunity.full_announcement = full_announcement
            opportunity_updates.append(opportunity)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Supplemental dataset validation"))
        self.stdout.write("-" * 48)

        self.stdout.write(f"Source opportunities:                 {len(opportunity_rows)}")
        self.stdout.write(
            f"  with full announcement:             "
            f"{len(opportunity_rows) - len(opportunity_empty_source)}"
        )
        self.stdout.write(f"  empty/missing full announcement:    {len(opportunity_empty_source)}")
        self.stdout.write(f"  already populated, skipped:         {len(opportunity_skipped_existing)}")
        self.stdout.write(f"  would update:                       {len(opportunity_updates)}")

        self.stdout.write("")
        self.stdout.write(f"Source papers:                        {len(paper_rows)}")
        self.stdout.write(
            f"  with description:                   "
            f"{len(paper_rows) - len(paper_empty_source)}"
        )
        self.stdout.write(f"  empty/missing description:          {len(paper_empty_source)}")
        self.stdout.write(f"  already populated, skipped:         {len(paper_skipped_existing)}")
        self.stdout.write(f"  would update Paper.abstract:        {len(paper_updates)}")

        if opportunity_empty_source:
            self.stdout.write("")
            self.stdout.write(
                "Opportunity IDs without full announcement: "
                + ", ".join(map(str, opportunity_empty_source))
            )

        if paper_empty_source:
            self.stdout.write("")
            self.stdout.write(
                "Paper IDs without description: "
                + ", ".join(map(str, paper_empty_source))
            )

        if paper_skipped_existing:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    f"{len(paper_skipped_existing)} paper abstract(s) were already populated "
                    "and will not be overwritten."
                )
            )

        if opportunity_skipped_existing:
            self.stdout.write(
                self.style.WARNING(
                    f"{len(opportunity_skipped_existing)} opportunity announcement(s) were "
                    "already populated and will not be overwritten."
                )
            )

        if not options["apply"]:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN ONLY — no database changes made. "
                    "Re-run with --apply after reviewing the counts."
                )
            )
            return

        # Keep the write phase atomic: either all prepared updates succeed or none do.
        with transaction.atomic():
            if paper_updates:
                Paper.objects.bulk_update(
                    paper_updates,
                    ["abstract"],
                    batch_size=200,
                )

            if opportunity_updates:
                Opportunity.objects.bulk_update(
                    opportunity_updates,
                    ["full_announcement"],
                    batch_size=50,
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Import complete: "
                f"{len(paper_updates)} paper abstract(s) updated; "
                f"{len(opportunity_updates)} opportunity full announcement(s) updated."
            )
        )
