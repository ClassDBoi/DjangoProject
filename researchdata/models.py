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