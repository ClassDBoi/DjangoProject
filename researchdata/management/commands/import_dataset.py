import json

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.dateparse import parse_date, parse_datetime

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

        self.import_papers(data["papers"])

        self.stdout.write(
            self.style.SUCCESS("Papers imported.")
        )

        self.import_opportunities(data["opportunities"])

        self.stdout.write(
            self.style.SUCCESS("Opportunities imported.")
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

    def import_papers(self, papers):
        missing_auids = set()

        for item in papers:
            publication_date = None

            if item.get("publication_date"):
                publication_date = parse_date(item["publication_date"])

            paper, created = Paper.objects.update_or_create(
                id=item["id"],
                defaults={
                    "title": item["title"],
                    "authors_display": item.get("authors_display"),
                    "publication_date": publication_date,
                    "published_in": item.get("published_in"),
                    "total_citations": item.get("total_citations") or 0,
                    "abstract": item.get("abstract"),
                    "summary": item.get("summary"),
                }
            )

            # Importing Paper Keywords
            paper.keywords.all().delete()

            keyword_objects = []

            for keyword in item.get("keywords", []):
                keyword_objects.append(PaperKeyword(
                    paper=paper,
                    keyword=keyword["keyword"],
                    score=keyword["score"]
                ))

            PaperKeyword.objects.bulk_create(keyword_objects)

            #Connect Auids from researchers to papers

            auids = item.get("researcher_auids", [])

            researchers = list(
                Researcher.objects.filter(auid__in=auids)
            )

            paper.researchers.set(researchers)

            #Some papers have auids not associated with researchers, track these just in case
            found_auids = {
                researcher.auid for researcher in researchers
            }

            missing_auids.update(
                set(auids) - found_auids
            )

        if missing_auids:
           self.stdout.write(
               self.style.WARNING(
                   f"Skipped {len(missing_auids)} researcher AUIDs "
                   f"that are not part of the researcher dataset."
               )
           )

    def import_opportunities(self, opportunities):
        for item in opportunities:

            #Due date parsing

            due_date = None

            if item.get("due_date"):
                due_date = parse_datetime(
                    item["due_date"]
                )

            #Create and/or update Opportunity

            opportunity, created = Opportunity.objects.update_or_create(
                opp_id=item["opp_id"],
                defaults={
                    "title": item["title"],
                    "agency": item.get("agency"),
                    "category": item.get("category"),
                    "estimated_funding": item.get("estimated_funding"),
                    "award_floor": item.get("award_floor"),
                    "award_ceiling": item.get("award_ceiling"),
                    "due_date": due_date,
                    "summary": item.get("summary"),
                    "description": item.get("description"),

                    # Don't clean the description yet.
                    # Do that during NLP data preprocessing.
                    "clean_description": None,
                }
            )

            #Importing Opportunity Topics (if provided)

            opportunity.topics.filter(
                source="provided"
            ).delete()

            topic_objects = []

            for topic_item in item.get("topics", []):
                topic_objects.append(
                    OpportunityTopic(
                        opportunity=opportunity,
                        topic=topic_item["topic"],
                        score=topic_item["score"],
                        source="provided",
                    )
                )

            OpportunityTopic.objects.bulk_create(
                topic_objects
            )

            #Importing Opportunity Domains (if provided)

            opportunity.domains.all().delete()

            domain_objects = []

            for domain_item in item.get("domains", []):
                domain_objects.append(
                    OpportunityDomain(
                        opportunity=opportunity,
                        domain_name=domain_item["domain_name"],
                        confidence_score=domain_item[
                            "confidence_score"
                        ],
                        rationale=domain_item.get("rationale"),
                        is_primary=domain_item.get(
                            "is_primary",
                            False
                        ),
                    )
                )

            OpportunityDomain.objects.bulk_create(
                domain_objects
            )
