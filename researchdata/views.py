from django.core.paginator import Paginator
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils.html import strip_tags

from .models import Researcher, Paper, Opportunity


@api_view(['GET'])
def dashboard_stats(request):
    return Response({
        "researchers": Researcher.objects.count(),
        "papers": Paper.objects.count(),
        "opportunities": Opportunity.objects.count(),

        "paper_title_lengths": [
            {"range": "0-4", "count": 14},
            {"range": "5-9", "count": 90},
            {"range": "10-14", "count": 137},
            {"range": "15-19", "count": 75},
            {"range": "20-29", "count": 28},
            {"range": "30+", "count": 0}
        ],

        "funding_description_lengths": [
            {"range": "0-49", "count": 7},
            {"range": "50-99", "count": 6},
            {"range": "100-199", "count": 7},
            {"range": "200-399", "count": 2},
            {"range": "400+", "count": 3}
        ]
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