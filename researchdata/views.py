import html
import math
import re

from django.core.paginator import Paginator
from django.utils.html import strip_tags
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Researcher, Paper, Opportunity


RAG_CHUNK_WORDS = 500
RAG_CHUNK_OVERLAP_WORDS = 75


def _clean_text(value):
    """Normalize database text for dashboard word-count diagnostics."""
    if not value:
        return ""

    text = str(value)

    # Match the intent of Scripts/analyze_dataset.py without adding a runtime
    # BeautifulSoup dependency to the Django API.
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


def _estimated_chunk_count(
    words,
    chunk_words=RAG_CHUNK_WORDS,
    overlap_words=RAG_CHUNK_OVERLAP_WORDS,
):
    """Mirror the fixed-size planning estimate in analyze_dataset.py."""
    if words <= 0:
        return 0

    if words <= chunk_words:
        return 1

    stride = chunk_words - overlap_words
    return 1 + math.ceil((words - chunk_words) / stride)


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
    opportunity_estimated_rag_chunks = []

    for opportunity in opportunities:
        description = (
            opportunity['clean_description']
            or opportunity['description']
            or ""
        )
        full_announcement = opportunity['full_announcement'] or ""
        full_words = _word_count(full_announcement)

        opportunity_description_words.append(_word_count(description))
        opportunity_full_announcement_words.append(full_words)
        opportunity_estimated_rag_chunks.append(
            _estimated_chunk_count(full_words)
        )

    return Response({
        "researchers": Researcher.objects.count(),
        "papers": len(papers),
        "opportunities": len(opportunities),
        "papers_with_abstracts": sum(
            words > 0 for words in paper_abstract_words
        ),
        "opportunities_with_full_announcements": sum(
            words > 0 for words in opportunity_full_announcement_words
        ),

        # These bins mirror the current Scripts/analyze_dataset.py output.
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
        "funding_rag_chunk_estimates": _bin_counts(
            opportunity_estimated_rag_chunks,
            [0, 1, 6, 11, 21, 41, 61],
        ),
        "rag_chunk_assumptions": {
            "chunk_words": RAG_CHUNK_WORDS,
            "overlap_words": RAG_CHUNK_OVERLAP_WORDS,
        },
    })


@api_view(['GET'])
def researcher_list(request):
    search = request.GET.get('search', '').strip()

    researchers = Researcher.objects.all().order_by('name')

    if search:
        researchers = researchers.filter(name__icontains=search)

    data = []

    for researcher in researchers:
        data.append({
            "auid": researcher.auid,
            "name": researcher.name,
            "title": researcher.title,
            "department": researcher.department,
            "college": researcher.college,
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


@api_view(['GET'])
def paper_list(request):
    search = request.GET.get('search', '').strip()
    researcher = request.GET.get('researcher', '').strip()

    papers = Paper.objects.all().order_by('title')

    if search:
        papers = papers.filter(title__icontains=search)

    if researcher:
        papers = papers.filter(researchers__auid=researcher)

    paginator = Paginator(papers, 20)
    page_number = request.GET.get('page', 1)
    page = paginator.get_page(page_number)

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

@api_view(['GET'])
def opportunity_list(request):
    search = request.GET.get('search', '').strip()

    opportunities = Opportunity.objects.all().order_by('title')

    if search:
        opportunities = opportunities.filter(title__icontains=search)

    paginator = Paginator(opportunities, 10)
    page_number = request.GET.get('page', 1)
    page = paginator.get_page(page_number)

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
