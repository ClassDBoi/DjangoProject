from django.db import models


class Researcher(models.Model):
    auid = models.CharField(
        max_length=20,
        primary_key=True
    )

    name = models.CharField(max_length=255)
    title = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )
    department = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )
    college = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    def __str__(self):
        return self.name


class Paper(models.Model):
    id = models.BigIntegerField(primary_key=True)

    title = models.TextField()

    authors_display = models.TextField(
        blank=True,
        null=True
    )

    publication_date = models.DateField(
        blank=True,
        null=True
    )

    published_in = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    total_citations = models.IntegerField(
        default=0
    )

    abstract = models.TextField(
        blank=True,
        null=True
    )

    summary = models.TextField(
        blank=True,
        null=True
    )

    researchers = models.ManyToManyField(
        Researcher,
        related_name="papers"
    )

    def __str__(self):
        return self.title


class PaperKeyword(models.Model):
    paper = models.ForeignKey(
        Paper,
        on_delete=models.CASCADE,
        related_name="keywords"
    )

    keyword = models.CharField(max_length=255)
    score = models.FloatField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["paper", "keyword"],
                name="unique_paper_keyword"
            )
        ]

    def __str__(self):
        return self.keyword


class Opportunity(models.Model):
    opp_id = models.BigIntegerField(primary_key=True)

    title = models.TextField()

    full_announcement = models.TextField(
        null=True,
        blank=True,
    )

    agency = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    category = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    estimated_funding = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        blank=True,
        null=True
    )

    award_floor = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        blank=True,
        null=True
    )

    award_ceiling = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        blank=True,
        null=True
    )

    due_date = models.DateTimeField(
        blank=True,
        null=True
    )

    summary = models.TextField(
        blank=True,
        null=True
    )

    description = models.TextField(
        blank=True,
        null=True
    )

    # We can populate this later before sending text
    # through the NLP pipeline.
    clean_description = models.TextField(
        blank=True,
        null=True
    )

    def __str__(self):
        return self.title


class OpportunityTopic(models.Model):
    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.CASCADE,
        related_name="topics"
    )

    topic = models.CharField(max_length=255)
    score = models.FloatField()

    # Later lets you distinguish supplied topics
    # from your own model's topics.
    source = models.CharField(
        max_length=50,
        default="provided"
    )


class OpportunityDomain(models.Model):
    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.CASCADE,
        related_name="domains"
    )

    domain_name = models.CharField(max_length=255)
    confidence_score = models.FloatField()

    rationale = models.TextField(
        blank=True,
        null=True
    )

    is_primary = models.BooleanField(default=False)


class ResearcherExpertise(models.Model):
    researcher = models.ForeignKey(
        Researcher,
        on_delete=models.CASCADE,
        related_name="expertise"
    )

    topic = models.CharField(max_length=255)
    score = models.FloatField()

    source = models.CharField(
        max_length=50,
        default="our_model"
    )

# ---------------------------------------------------------------------------
# Project-created data (tables prefixed "ausme_").
#
# Everything above holds the client's original data and is never changed by
# this project's pipelines. The models below store results this project
# produced, so they can be replaced or removed without touching client data.
# ---------------------------------------------------------------------------

class MatchRun(models.Model):
    """One imported set of researcher-opportunity matches (see `import_matches`)."""

    name = models.CharField(max_length=100, unique=True)
    imported_at = models.DateTimeField(auto_now_add=True)

    embedding_model = models.CharField(max_length=255)
    embedding_revision = models.CharField(max_length=64, blank=True)
    generator = models.CharField(
        max_length=100,
        blank=True,
        help_text="Language model that extracted the keywords and topics.",
    )
    scoring = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)

    # Matches whose semantic similarity is below this value are not shown
    # ("no close match"). Set from the team's blind review of matches.
    similarity_cutoff = models.FloatField(default=0.5)

    # The API serves the active run; importing a new run activates it.
    is_active = models.BooleanField(default=False)

    # {opp_id: reason} for opportunities that could not be matched.
    unmatched_opportunities = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "ausme_match_run"

    def __str__(self):
        return self.name


class ResearcherOpportunityMatch(models.Model):
    """How closely one researcher's work matches one opportunity's research topics."""

    run = models.ForeignKey(MatchRun, on_delete=models.CASCADE, related_name="matches")
    researcher = models.ForeignKey(Researcher, on_delete=models.CASCADE, related_name="ausme_matches")
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name="ausme_matches")

    rank_for_researcher = models.PositiveIntegerField()
    rank_for_opportunity = models.PositiveIntegerField()

    # Mean MPNet cosine similarity of the evidence links. A semantic similarity,
    # not a probability, confidence or likelihood of funding.
    semantic_similarity = models.FloatField()

    # The value the ranks are based on (generic topics count less).
    ranking_score = models.FloatField()

    class Meta:
        db_table = "ausme_researcher_opportunity_match"
        constraints = [
            models.UniqueConstraint(
                fields=["run", "researcher", "opportunity"],
                name="unique_match_per_run",
            )
        ]
        indexes = [
            models.Index(fields=["run", "researcher", "rank_for_researcher"]),
            models.Index(fields=["run", "opportunity", "rank_for_opportunity"]),
        ]


class MatchEvidence(models.Model):
    """One link behind a match: an opportunity topic and the researcher's closest keyword."""

    match = models.ForeignKey(
        ResearcherOpportunityMatch,
        on_delete=models.CASCADE,
        related_name="evidence",
    )
    position = models.PositiveSmallIntegerField()

    opportunity_topic = models.CharField(max_length=255)
    researcher_term = models.CharField(max_length=255)

    # The paper the keyword came from (the first one, if several share it).
    paper = models.ForeignKey(Paper, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    other_paper_count = models.PositiveIntegerField(default=0)

    semantic_similarity = models.FloatField()

    class Meta:
        db_table = "ausme_match_evidence"
        ordering = ["position"]
