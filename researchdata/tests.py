"""API tests for the list endpoints (search, filters, sorting, paging).

Run without touching the shared MySQL database:

    python manage.py test researchdata --settings=SeniorDesign_AUSME.settings_test
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from .models import Opportunity, Paper, PaperKeyword, Researcher


class ListEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ada = Researcher.objects.create(auid="ABC0001", name="Ada Lane", title="Professor",
                                            department="Chemistry", college="College of Sciences")
        cls.ben = Researcher.objects.create(auid="XYZ0002", name="Ben Cole", title="Assistant Professor",
                                            department="Civil Engineering", college="College of Engineering")
        p1 = Paper.objects.create(id=1, title="Biosensors for water", authors_display="Ada Lane, Kim Roe",
                                  publication_date=date(2020, 5, 1), published_in="Sensors", total_citations=40)
        p2 = Paper.objects.create(id=2, title="Bridge deck corrosion", authors_display="Ben Cole",
                                  publication_date=date(2015, 1, 1), published_in="Structures", total_citations=5)
        p3 = Paper.objects.create(id=3, title="Asphalt mixes", authors_display="Ben Cole, Ada Lane",
                                  publication_date=None, published_in=None, total_citations=12)
        p1.researchers.add(cls.ada)
        p2.researchers.add(cls.ben)
        p3.researchers.add(cls.ada, cls.ben)
        PaperKeyword.objects.create(paper=p2, keyword="Chloride Ingress", score=0.9)
        now = timezone.now()
        Opportunity.objects.create(opp_id=10, title="Open sensors call", agency="NSF", category="Discretionary",
                                   estimated_funding=Decimal("500000"), due_date=now + timedelta(days=30))
        Opportunity.objects.create(opp_id=11, title="Closed bridge call", agency="DOT", category="Discretionary",
                                   estimated_funding=Decimal("2000000"), due_date=now - timedelta(days=30))
        Opportunity.objects.create(opp_id=12, title="Unknown funding", agency="NSF", category="Other",
                                   estimated_funding=None, due_date=None)

    def get(self, url, **params):
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    # Researchers ----------------------------------------------------------
    def test_researcher_search_covers_department_college_and_auid(self):
        self.assertEqual([r["auid"] for r in self.get("/api/researchers/", search="civil")], ["XYZ0002"])
        self.assertEqual([r["auid"] for r in self.get("/api/researchers/", search="abc0")], ["ABC0001"])
        self.assertEqual(len(self.get("/api/researchers/", search="college of")), 2)

    def test_researcher_filters_and_paper_count_sort(self):
        rows = self.get("/api/researchers/", college="College of Engineering")
        self.assertEqual([r["name"] for r in rows], ["Ben Cole"])
        rows = self.get("/api/researchers/", sort="papers", order="desc")
        self.assertEqual([r["paper_count"] for r in rows], [2, 2])
        rows = self.get("/api/researchers/", sort="name", order="desc")
        self.assertEqual([r["name"] for r in rows], ["Ben Cole", "Ada Lane"])

    # Papers ---------------------------------------------------------------
    def test_paper_search_matches_authors_and_keywords_once(self):
        data = self.get("/api/papers/", search="Ada Lane")
        self.assertEqual(sorted(p["id"] for p in data["results"]), [1, 3])
        data = self.get("/api/papers/", search="chloride")
        self.assertEqual([p["id"] for p in data["results"]], [2])

    def test_paper_sort_by_citations_and_date_puts_missing_last(self):
        data = self.get("/api/papers/", sort="citations", order="desc")
        self.assertEqual([p["id"] for p in data["results"]], [1, 3, 2])
        data = self.get("/api/papers/", sort="date", order="desc")
        self.assertEqual([p["id"] for p in data["results"]], [1, 2, 3])
        data = self.get("/api/papers/", sort="date", order="asc")
        self.assertEqual([p["id"] for p in data["results"]], [2, 1, 3])

    def test_paper_year_citation_and_researcher_filters(self):
        self.assertEqual(self.get("/api/papers/", year_from=2018)["count"], 1)
        self.assertEqual(self.get("/api/papers/", min_citations=10)["count"], 2)
        self.assertEqual(self.get("/api/papers/", researcher="XYZ0002")["count"], 2)

    def test_paging_and_bad_parameters(self):
        data = self.get("/api/papers/", page_size=1, page=2, sort="title")
        self.assertEqual((data["count"], data["total_pages"], data["current_page"]), (3, 3, 2))
        data = self.get("/api/papers/", sort="nonsense", year_from="abc", page_size="x")
        self.assertEqual(data["count"], 3)

    # Opportunities ---------------------------------------------------------
    def test_opportunity_status_and_funding_filters(self):
        self.assertEqual([o["opp_id"] for o in self.get("/api/opportunities/", status="open")["results"]], [10])
        self.assertEqual([o["opp_id"] for o in self.get("/api/opportunities/", status="closed")["results"]], [11])
        self.assertEqual([o["opp_id"] for o in self.get("/api/opportunities/", min_funding=1000000)["results"]], [11])

    def test_opportunity_sort_by_funding_and_agency_filter(self):
        data = self.get("/api/opportunities/", sort="funding", order="desc")
        self.assertEqual([o["opp_id"] for o in data["results"]], [11, 10, 12])
        data = self.get("/api/opportunities/", agency="NSF", sort="title")
        self.assertEqual([o["opp_id"] for o in data["results"]], [10, 12])

    # Filter options ---------------------------------------------------------
    def test_filter_options(self):
        data = self.get("/api/filters/")
        self.assertEqual(data["researchers"]["colleges"], ["College of Engineering", "College of Sciences"])
        self.assertEqual(data["papers"]["first_year"], 2015)
        self.assertEqual(data["papers"]["last_year"], 2020)
        self.assertEqual(data["opportunities"]["agencies"], ["DOT", "NSF"])


class MatchTests(TestCase):
    """import_matches command and the /matches/ endpoints."""

    @classmethod
    def setUpTestData(cls):
        Researcher.objects.create(auid="R1", name="Ada Lane", department="Chemistry", college="Sciences")
        Researcher.objects.create(auid="R2", name="Ben Cole", department="Music", college="Liberal Arts")
        paper = Paper.objects.create(id=7, title="Biosensors for water")
        paper.researchers.add(Researcher.objects.get(auid="R1"))
        Opportunity.objects.create(opp_id=10, title="Sensors call", agency="NSF")
        Opportunity.objects.create(opp_id=11, title="Career award", agency="NIH")
        Opportunity.objects.create(opp_id=12, title="Title only", agency="CDC")

    def write_file(self, mock=False):
        import json
        import tempfile
        from pathlib import Path

        def row(auid, opp, sim, rank_r, rank_o):
            return {
                "auid": auid, "opp_id": str(opp), "strongest_links_similarity": sim, "ranking_score": sim,
                "rank_for_researcher": rank_r, "rank_for_opportunity": rank_o,
                "evidence": [{"opportunity_topic": "Biosensors", "researcher_term": "Water Biosensor",
                              "paper_ids": [7], "semantic_similarity": sim}],
            }

        data = {
            "mock": mock, "embedding_model": "sentence-transformers/all-mpnet-base-v2", "scoring": "v2",
            "opportunities_not_matched": ["11"],
            "matches": [row("R1", 10, 0.71, 1, 1), row("R2", 10, 0.31, 1, 2)],
        }
        folder = Path(tempfile.mkdtemp()) / "match_v2"
        folder.mkdir()
        path = folder / "matches.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return str(path)

    def run_import(self, *args):
        from io import StringIO

        from django.core.management import call_command
        out = StringIO()
        call_command("import_matches", *args, stdout=out)
        return out.getvalue()

    def test_dry_run_writes_nothing(self):
        from .models import MatchRun
        output = self.run_import(self.write_file())
        self.assertIn("Dry run", output)
        self.assertFalse(MatchRun.objects.exists())

    def test_mock_file_is_refused(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            self.run_import(self.write_file(mock=True), "--apply")

    def test_import_and_endpoints(self):
        from .models import MatchRun
        self.run_import(self.write_file(), "--apply")
        run = MatchRun.objects.get()
        self.assertEqual((run.name, run.is_active, run.similarity_cutoff), ("match_v2", True, 0.5))
        self.assertEqual(run.unmatched_opportunities, {"11": "no_research_topics", "12": "insufficient_text"})

        data = self.client.get("/api/researchers/R1/matches/").json()
        self.assertEqual([m["opp_id"] for m in data["matches"]], [10])
        self.assertEqual(data["matches"][0]["evidence"][0]["paper_title"], "Biosensors for water")

        # Below the cutoff: no close match.
        data = self.client.get("/api/researchers/R2/matches/").json()
        self.assertEqual((data["matches"], data["no_close_match"]), ([], True))

        data = self.client.get("/api/opportunities/10/matches/").json()
        self.assertEqual([m["auid"] for m in data["matches"]], ["R1"])
        data = self.client.get("/api/opportunities/11/matches/").json()
        self.assertIn("career-stage", data["unmatched_reason"])
        data = self.client.get("/api/opportunities/12/matches/").json()
        self.assertIn("not enough announcement text", data["unmatched_reason"])

        # Re-importing the same name replaces the run.
        self.run_import(self.write_file(), "--apply", "--cutoff", "0.8")
        self.assertEqual(MatchRun.objects.get().similarity_cutoff, 0.8)
        self.assertEqual(self.client.get("/api/researchers/R1/matches/").json()["matches"], [])

    def test_no_run_yet(self):
        data = self.client.get("/api/researchers/R1/matches/").json()
        self.assertIsNone(data["run"])
        self.assertEqual(self.client.get("/api/researchers/NOPE/matches/").status_code, 404)
