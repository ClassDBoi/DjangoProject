import html
import re

from django.core.paginator import Paginator
from django.db.models import Count, F, Max, Min, Q
from django.db.models.functions import ExtractYear
from django.utils import timezone
from django.utils.html import strip_tags
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import MatchRun, Opportunity, Paper, Researcher, ResearcherOpportunityMatch


# ---------------------------------------------------------------------------
# Shared helpers for the list endpoints (search, filters, sorting, paging).
#
# Every list endpoint accepts:
#   search=<text>      case-insensitive match across several fields
#   sort=<key>         one of the keys in that view's SORT_FIELDS
#   order=asc|desc     sort direction (default asc)
# Paginated endpoints also accept page=<n> and page_size=<n> (max 100).
# Unknown sort keys fall back to the default; bad numbers are ignored.
# ---------------------------------------------------------------------------

MAX_PAGE_SIZE = 100


def _apply_sort(queryset, request, sort_fields, default_key):
    """Order by a whitelisted field; empty values always sort last."""
    key = request.GET.get("sort", default_key)
    field = sort_fields.get(key, sort_fields[default_key])
    descending = request.GET.get("order", "asc").lower() == "desc"
    expression = F(field).desc(nulls_last=True) if descending else F(field).asc(nulls_last=True)
    # The primary key breaks ties so paging is stable.
    return queryset.order_by(expression, "pk")


def _int_param(request, name, default=None, minimum=None, maximum=None):
    try:
        value = int(request.GET.get(name, ""))
    except ValueError:
        return default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _float_param(request, name):
    try:
        return float(request.GET.get(name, ""))
    except ValueError:
        return None


def _paginate(queryset, request, default_size):
    page_size = _int_param(request, "page_size", default_size, 1, MAX_PAGE_SIZE)
    paginator = Paginator(queryset, page_size)
    page = paginator.get_page(request.GET.get("page", 1))
    return paginator, page


def _clean_text(value):
    """Normalize database text for dashboard word-count diagnostics."""
    if not value:
        return ""

    text = str(value)

    # Strip HTML tags and entities without adding a BeautifulSoup dependency.
    text = re.sub(
        r"<(script|style)\b[^>]*>.*?</\1>",
        " ",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    text = strip_tags(text)
    text = html.unescape(text)
    return " ".join(text.split())


def _word_count(value):
    return len(_clean_text(value).split())


def _bin_counts(values, edges):
    rows = []

    for index, start in enumerate(edges):
        end = edges[index + 1] if index + 1 < len(edges) else None
        label = f"{start}+" if end is None else f"{start}-{end - 1}"
        count = sum(
            value >= start and (end is None or value < end)
            for value in values
        )
        rows.append({"range": label, "count": count})

    return rows


@api_view(['GET'])
def dashboard_stats(request):
    papers = list(
        Paper.objects.values(
            'title',
            'abstract',
        )
    )
    opportunities = list(
        Opportunity.objects.values(
            'description',
            'clean_description',
            'full_announcement',
        )
    )

    paper_title_words = [
        _word_count(paper['title'])
        for paper in papers
    ]
    paper_abstract_words = [
        _word_count(paper['abstract'])
        for paper in papers
    ]

    opportunity_description_words = []
    opportunity_full_announcement_words = []

    for opportunity in opportunities:
        description = (
            opportunity['clean_description']
            or opportunity['description']
            or ""
        )
        full_announcement = opportunity['full_announcement'] or ""

        opportunity_description_words.append(_word_count(description))
        opportunity_full_announcement_words.append(_word_count(full_announcement))

    return Response({
        "researchers": Researcher.objects.count(),
        "papers": len(papers),
        "opportunities": len(opportunities),

        # Word-count distributions for the dashboard charts.
        "paper_title_lengths": _bin_counts(
            paper_title_words,
            [0, 5, 10, 15, 20, 30],
        ),
        "paper_abstract_lengths": _bin_counts(
            paper_abstract_words,
            [0, 1, 100, 200, 400, 800],
        ),
        "funding_description_lengths": _bin_counts(
            opportunity_description_words,
            [0, 50, 100, 200, 400],
        ),
        "funding_full_announcement_lengths": _bin_counts(
            opportunity_full_announcement_words,
            [0, 1, 2500, 5000, 10000, 20000, 30000],
        ),
    })


RESEARCHER_SORT_FIELDS = {
    "name": "name",
    "auid": "auid",
    "department": "department",
    "college": "college",
    "papers": "paper_count",
}


@api_view(['GET'])
def researcher_list(request):
    """All researchers (not paginated: the list is small and used for dropdowns).

    Query parameters:
        search      matches name, AUID, title, department or college
        college     exact college name
        department  exact department name
        sort        name (default), auid, department, college, papers
        order       asc (default) or desc
    """
    search = request.GET.get('search', '').strip()
    college = request.GET.get('college', '').strip()
    department = request.GET.get('department', '').strip()

    researchers = Researcher.objects.annotate(
        paper_count=Count('papers', distinct=True)
    )

    if search:
        researchers = researchers.filter(
            Q(name__icontains=search)
            | Q(auid__icontains=search)
            | Q(title__icontains=search)
            | Q(department__icontains=search)
            | Q(college__icontains=search)
        )

    if college:
        researchers = researchers.filter(college=college)

    if department:
        researchers = researchers.filter(department=department)

    researchers = _apply_sort(researchers, request, RESEARCHER_SORT_FIELDS, "name")

    data = []

    for researcher in researchers:
        data.append({
            "auid": researcher.auid,
            "name": researcher.name,
            "title": researcher.title,
            "department": researcher.department,
            "college": researcher.college,
            "paper_count": researcher.paper_count,
        })

    return Response(data)


@api_view(['GET'])
def researcher_detail(request, auid):
    try:
        researcher = Researcher.objects.get(auid=auid)
    except Researcher.DoesNotExist:
        return Response(
            {"error": "Researcher not found"},
            status=404
        )

    papers = researcher.papers.prefetch_related(
        'keywords'
    ).all()

    paper_data = []

    for paper in papers:
        paper_data.append({
            "id": paper.id,
            "title": paper.title,
            "publication_date": paper.publication_date,
            "published_in": paper.published_in,
            "total_citations": paper.total_citations,
            "abstract": paper.abstract or "Not available",
            "keywords": [
                {
                    "keyword": keyword.keyword,
                    "score": keyword.score
                }
                for keyword in paper.keywords.all()
            ]
        })

    return Response({
        "auid": researcher.auid,
        "name": researcher.name,
        "title": researcher.title,
        "department": researcher.department,
        "college": researcher.college,
        "papers": paper_data
    })


PAPER_SORT_FIELDS = {
    "title": "title",
    "date": "publication_date",
    "citations": "total_citations",
    "journal": "published_in",
}


@api_view(['GET'])
def paper_list(request):
    """Paginated papers.

    Query parameters:
        search         matches title, authors, journal or a keyword
        researcher     AUID of an associated researcher
        year_from      earliest publication year (inclusive)
        year_to        latest publication year (inclusive)
        min_citations  minimum total citations
        sort           title (default), date, citations, journal
        order          asc (default) or desc
        page, page_size  (default 20 per page, max 100)
    """
    search = request.GET.get('search', '').strip()
    researcher = request.GET.get('researcher', '').strip()
    year_from = _int_param(request, 'year_from')
    year_to = _int_param(request, 'year_to')
    min_citations = _int_param(request, 'min_citations')

    papers = Paper.objects.all()

    if search:
        papers = papers.filter(
            Q(title__icontains=search)
            | Q(authors_display__icontains=search)
            | Q(published_in__icontains=search)
            | Q(keywords__keyword__icontains=search)
        ).distinct()

    if researcher:
        papers = papers.filter(researchers__auid=researcher)

    if year_from is not None:
        papers = papers.filter(publication_date__year__gte=year_from)

    if year_to is not None:
        papers = papers.filter(publication_date__year__lte=year_to)

    if min_citations is not None:
        papers = papers.filter(total_citations__gte=min_citations)

    papers = _apply_sort(papers, request, PAPER_SORT_FIELDS, "title")
    paginator, page = _paginate(papers, request, 20)

    data = []

    for paper in page:
        data.append({
            "id": paper.id,
            "title": paper.title,
            "authors_display": paper.authors_display,
            "publication_date": paper.publication_date,
            "published_in": paper.published_in,
            "total_citations": paper.total_citations,
        })

    return Response({
        "count": paginator.count,
        "total_pages": paginator.num_pages,
        "current_page": page.number,
        "results": data
    })


@api_view(['GET'])
def paper_detail(request, paper_id):
    try:
        paper = Paper.objects.prefetch_related(
            'researchers',
            'keywords'
        ).get(id=paper_id)
    except Paper.DoesNotExist:
        return Response(
            {"error": "Paper not found"},
            status=404
        )

    return Response({
        "id": paper.id,
        "title": paper.title,
        "authors_display": paper.authors_display,
        "researchers": [
            {
                "auid": researcher.auid,
                "name": researcher.name
            }
            for researcher in paper.researchers.all()
        ],
        "publication_date": paper.publication_date,
        "published_in": paper.published_in,
        "total_citations": paper.total_citations,
        "abstract": paper.abstract or "Not available",
        "keywords": [
            {
                "keyword": keyword.keyword,
                "score": keyword.score
            }
            for keyword in paper.keywords.all()
        ]
    })


# Funding opportunity API

OPPORTUNITY_SORT_FIELDS = {
    "title": "title",
    "due_date": "due_date",
    "funding": "estimated_funding",
    "ceiling": "award_ceiling",
    "agency": "agency",
}


@api_view(['GET'])
def opportunity_list(request):
    """Paginated funding opportunities.

    Query parameters:
        search        matches title, agency, category or description
        agency        exact agency value
        category      exact category value
        status        open (due date today or later) or closed
        min_funding   minimum estimated total funding (USD)
        max_funding   maximum estimated total funding (USD)
        sort          title (default), due_date, funding, ceiling, agency
        order         asc (default) or desc
        page, page_size  (default 10 per page, max 100)
    """
    search = request.GET.get('search', '').strip()
    agency = request.GET.get('agency', '').strip()
    category = request.GET.get('category', '').strip()
    status = request.GET.get('status', '').strip().lower()
    min_funding = _float_param(request, 'min_funding')
    max_funding = _float_param(request, 'max_funding')

    opportunities = Opportunity.objects.all()

    if search:
        opportunities = opportunities.filter(
            Q(title__icontains=search)
            | Q(agency__icontains=search)
            | Q(category__icontains=search)
            | Q(description__icontains=search)
        )

    if agency:
        opportunities = opportunities.filter(agency=agency)

    if category:
        opportunities = opportunities.filter(category=category)

    if status == 'open':
        opportunities = opportunities.filter(due_date__gte=timezone.now())
    elif status == 'closed':
        opportunities = opportunities.filter(due_date__lt=timezone.now())

    if min_funding is not None:
        opportunities = opportunities.filter(estimated_funding__gte=min_funding)

    if max_funding is not None:
        opportunities = opportunities.filter(estimated_funding__lte=max_funding)

    opportunities = _apply_sort(opportunities, request, OPPORTUNITY_SORT_FIELDS, "title")
    paginator, page = _paginate(opportunities, request, 10)

    data = []

    for opportunity in page:
        data.append({
            "opp_id": opportunity.opp_id,
            "title": opportunity.title,
            "agency": opportunity.agency,
            "category": opportunity.category,
            "estimated_funding": opportunity.estimated_funding,
            "award_floor": opportunity.award_floor,
            "award_ceiling": opportunity.award_ceiling,
            "due_date": opportunity.due_date,
        })

    return Response({
        "count": paginator.count,
        "total_pages": paginator.num_pages,
        "current_page": page.number,
        "results": data
    })


@api_view(['GET'])
def opportunity_detail(request, opp_id):
    try:
        opportunity = Opportunity.objects.prefetch_related(
            'topics',
            'domains'
        ).get(opp_id=opp_id)

    except Opportunity.DoesNotExist:
        return Response(
            {"error": "Opportunity not found"},
            status=404
        )

    description = (
        opportunity.clean_description
        or strip_tags(opportunity.description or "")
    )

    return Response({
        "opp_id": opportunity.opp_id,
        "title": opportunity.title,
        "agency": opportunity.agency,
        "category": opportunity.category,
        "estimated_funding": opportunity.estimated_funding,
        "award_floor": opportunity.award_floor,
        "award_ceiling": opportunity.award_ceiling,
        "due_date": opportunity.due_date,
        "description": description or "Not available",
        "full_announcement": opportunity.full_announcement or "Not available",

        "topics": [
            {
                "topic": topic.topic,
                "score": topic.score,
                "source": topic.source
            }
            for topic in opportunity.topics.all()
        ],

        "domains": [
            {
                "domain_name": domain.domain_name,
                "confidence_score": domain.confidence_score,
                "rationale": domain.rationale,
                "is_primary": domain.is_primary
            }
            for domain in opportunity.domains.all()
        ]
    })


@api_view(['GET'])
def filter_options(request):
    """Values for the frontend filter dropdowns, read from the live data."""

    def distinct_values(queryset, field):
        return list(
            queryset.exclude(**{f"{field}__isnull": True})
            .exclude(**{field: ""})
            .order_by(field)
            .values_list(field, flat=True)
            .distinct()
        )

    years = Paper.objects.exclude(publication_date__isnull=True).aggregate(
        first=Min(ExtractYear('publication_date')),
        last=Max(ExtractYear('publication_date')),
    )
    funding = Opportunity.objects.aggregate(
        low=Min('estimated_funding'),
        high=Max('estimated_funding'),
    )

    departments = (
        Researcher.objects.exclude(department__isnull=True)
        .exclude(department="")
        .order_by('department')
        .values('department', 'college')
        .distinct()
    )

    return Response({
        "researchers": {
            "colleges": distinct_values(Researcher.objects, 'college'),
            "departments": list(departments),
        },
        "papers": {
            "first_year": years["first"],
            "last_year": years["last"],
        },
        "opportunities": {
            "agencies": distinct_values(Opportunity.objects, 'agency'),
            "categories": distinct_values(Opportunity.objects, 'category'),
            "min_funding": funding["low"],
            "max_funding": funding["high"],
        },
    })


# ---------------------------------------------------------------------------
# Researcher-opportunity matches (project-created data, ausme_* tables).
#
# Served from the active MatchRun (see `manage.py import_matches`). Only matches
# at or above the run's semantic similarity cutoff are returned. Semantic
# similarity is not a probability or likelihood of funding, and eligibility
# and deadlines are not part of it.
# ---------------------------------------------------------------------------

UNMATCHED_MESSAGES = {
    "no_research_topics": "Not matched: the announcement text only yielded administrative "
                          "or career-stage topics, not research topics.",
    "insufficient_text": "Not matched: there is not enough announcement text to extract research topics.",
}


def _run_info(run):
    return {
        "name": run.name,
        "semantic_model": run.embedding_model,
        "similarity_cutoff": run.similarity_cutoff,
        "imported_at": run.imported_at,
    }


def _evidence(match):
    return [
        {
            "opportunity_topic": link.opportunity_topic,
            "researcher_term": link.researcher_term,
            "paper_id": link.paper_id,
            "paper_title": link.paper.title if link.paper else None,
            "other_paper_count": link.other_paper_count,
            "semantic_similarity": round(link.semantic_similarity, 4),
        }
        for link in match.evidence.all()
    ]


@api_view(['GET'])
def researcher_matches(request, auid):
    """Closest funding opportunities for one researcher (default 3, max 10)."""
    if not Researcher.objects.filter(auid=auid).exists():
        return Response({"error": "Researcher not found"}, status=404)

    run = MatchRun.objects.filter(is_active=True).first()
    if run is None:
        return Response({"run": None, "matches": [], "no_close_match": False})

    limit = _int_param(request, "limit", 3, 1, 10)
    rows = (
        ResearcherOpportunityMatch.objects
        .filter(run=run, researcher_id=auid, semantic_similarity__gte=run.similarity_cutoff)
        .select_related("opportunity")
        .prefetch_related("evidence__paper")
        .order_by("rank_for_researcher")[:limit]
    )

    matches = [
        {
            "opp_id": match.opportunity.opp_id,
            "title": match.opportunity.title,
            "agency": match.opportunity.agency,
            "estimated_funding": match.opportunity.estimated_funding,
            "due_date": match.opportunity.due_date,
            "rank": match.rank_for_researcher,
            "semantic_similarity": round(match.semantic_similarity, 4),
            "evidence": _evidence(match),
        }
        for match in rows
    ]

    has_any = ResearcherOpportunityMatch.objects.filter(run=run, researcher_id=auid).exists()
    return Response({
        "run": _run_info(run),
        "matches": matches,
        "no_close_match": has_any and not matches,
    })


@api_view(['GET'])
def opportunity_matches(request, opp_id):
    """Closest researchers for one funding opportunity (default 5, max 25)."""
    if not Opportunity.objects.filter(opp_id=opp_id).exists():
        return Response({"error": "Opportunity not found"}, status=404)

    run = MatchRun.objects.filter(is_active=True).first()
    if run is None:
        return Response({"run": None, "matches": [], "no_close_match": False, "unmatched_reason": None})

    reason = run.unmatched_opportunities.get(str(opp_id))
    limit = _int_param(request, "limit", 5, 1, 25)
    rows = (
        ResearcherOpportunityMatch.objects
        .filter(run=run, opportunity_id=opp_id, semantic_similarity__gte=run.similarity_cutoff)
        .select_related("researcher")
        .prefetch_related("evidence__paper")
        .order_by("rank_for_opportunity")[:limit]
    )

    matches = [
        {
            "auid": match.researcher.auid,
            "name": match.researcher.name,
            "title": match.researcher.title,
            "department": match.researcher.department,
            "college": match.researcher.college,
            "rank": match.rank_for_opportunity,
            "semantic_similarity": round(match.semantic_similarity, 4),
            "evidence": _evidence(match),
        }
        for match in rows
    ]

    return Response({
        "run": _run_info(run),
        "matches": matches,
        "no_close_match": reason is None and not matches,
        "unmatched_reason": UNMATCHED_MESSAGES.get(reason) if reason else None,
    })
