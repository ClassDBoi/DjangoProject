from django.core.paginator import Paginator
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils.html import strip_tags

from .models import Researcher, Paper, Opportunity
from html import unescape

import json
from pathlib import Path
from django.conf import settings

def word_count(text):
    cleaned = strip_tags(unescape(text or ""))
    return len(cleaned.split())


def make_histogram(lengths, bins):
    return [
        {
            "range": label,
            "count": sum(
                1
                for length in lengths
                if length >= lower
                and (upper is None or length <= upper)
            ),
        }
        for label, lower, upper in bins
    ]

# 仪表板Dashboard
@api_view(["GET"])
def dashboard_stats(request):
    paper_rows = list(
        Paper.objects.values_list("title", "abstract")
    )
    opportunity_rows = list(
        Opportunity.objects.values_list(
            "clean_description", "description"
        )
    )

    title_lengths = [
        word_count(title)
        for title, abstract in paper_rows
    ]

    abstract_lengths = [
        word_count(abstract)
        for title, abstract in paper_rows
    ]

    description_lengths = [
        word_count(
            clean_description
            if clean_description and clean_description.strip()
            else description
        )
        for clean_description, description in opportunity_rows
    ]

    announcement_path = (
        Path(settings.BASE_DIR)
        / "data"
        / "senior_design_full_announcements.json"
    )

    with announcement_path.open(encoding="utf-8") as file:
        announcement_data = json.load(file)

    announcements_by_id = {
        str(row["opp_id"]): row.get("full_announcement")
        for row in announcement_data["opportunities"]
    }

    opportunity_ids = list(
        Opportunity.objects.values_list("opp_id", flat=True)
    )

    announcement_lengths = [
        word_count(announcements_by_id.get(str(opp_id)))
        for opp_id in opportunity_ids
    ]

    chunk_size = 500
    chunk_overlap = 100
    chunk_step = chunk_size - chunk_overlap

    chunk_counts = [
        0 if length == 0 else (
            1
            + (
                max(0, length - chunk_size)
                + chunk_step - 1
            ) // chunk_step
        )
        for length in announcement_lengths
    ]

    return Response({
        "researchers": Researcher.objects.count(),
        "papers": len(paper_rows),
        "opportunities": len(opportunity_rows),

        "paper_title_lengths": make_histogram(
            title_lengths,
            [
                ("0-4", 0, 4),
                ("5-9", 5, 9),
                ("10-14", 10, 14),
                ("15-19", 15, 19),
                ("20-29", 20, 29),
                ("30+", 30, None),
            ],
        ),

        "paper_abstract_lengths": make_histogram(
            abstract_lengths,
            [
                ("0", 0, 0),
                ("1-99", 1, 99),
                ("100-199", 100, 199),
                ("200-399", 200, 399),
                ("400-799", 400, 799),
                ("800+", 800, None),
            ],
        ),

        "funding_description_lengths": make_histogram(
            description_lengths,
            [
                ("0", 0, 0),
                ("1-49", 1, 49),
                ("50-99", 50, 99),
                ("100-199", 100, 199),
                ("200-399", 200, 399),
                ("400+", 400, None),
            ],
        ),

        "funding_full_announcement_lengths": make_histogram(
            announcement_lengths,
            [
                ("0", 0, 0),
                ("1-2499", 1, 2499),
                ("2500-4999", 2500, 4999),
                ("5000-9999", 5000, 9999),
                ("10000-19999", 10000, 19999),
                ("20000-29999", 20000, 29999),
                ("30000+", 30000, None),
            ],
        ),

        "funding_rag_chunk_counts": make_histogram(
            chunk_counts,
            [
                ("0", 0, 0),
                ("1-5", 1, 5),
                ("6-10", 6, 10),
                ("11-20", 11, 20),
                ("21-40", 21, 40),
                ("41-60", 41, 60),
                ("61+", 61, None),
            ],
        ),

        "rag_chunk_settings": {
            "size_words": chunk_size,
            "overlap_words": chunk_overlap,
        },

        "missing_full_announcements": announcement_lengths.count(0),

        "missingness": {
            "paper_abstract": abstract_lengths.count(0),
            "funding_description": description_lengths.count(0),
        },
    })

#学者researchers
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

#融资API

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