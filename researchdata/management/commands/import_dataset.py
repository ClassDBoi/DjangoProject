import json

from django.core.management.base import BaseCommand
from django.db import transaction

from researchdata.models import (
    Researcher,
    Paper,
    PaperKeyword,
    Opportunity,
    OpportunityTopic,
    OpportunityDomain,
)


class Command(BaseCommand):
    help = "Import the Senior Design JSON dataset"

    def add_arguments(self, parser):
        parser.add_argument(
            "json_file",
            type=str,
            help="Path to the JSON dataset"
        )

    @transaction.atomic
    def handle(self, *args, **options):
        file_path = options["json_file"]

        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        self.import_researchers(data["researchers"])

        self.stdout.write(
            self.style.SUCCESS("Researchers imported.")
        )

    def import_researchers(self, researchers):
        for item in researchers:
            Researcher.objects.update_or_create(
                auid=item["auid"],
                defaults={
                    "name": item["name"],
                    "title": item.get("title"),
                    "department": item.get("department"),
                    "college": item.get("college"),
                }
            )