from django.contrib import admin
from django.urls import path

from researchdata.views import (
    dashboard_stats,
    researcher_list,
    researcher_detail,
    paper_list,
    paper_detail,
    opportunity_list,
    opportunity_detail,
    filter_options,
    researcher_matches,
    opportunity_matches,
)

urlpatterns = [
    path('admin/', admin.site.urls),

    path('api/dashboard/', dashboard_stats, name='dashboard-stats'),
    path('api/filters/', filter_options, name='filter-options'),

    path('api/researchers/', researcher_list, name='researcher-list'),
    path('api/researchers/<str:auid>/', researcher_detail, name='researcher-detail'),
    path('api/researchers/<str:auid>/matches/', researcher_matches, name='researcher-matches'),

    path('api/papers/', paper_list, name='paper-list'),
    path('api/papers/<int:paper_id>/', paper_detail, name='paper-detail'),

    path('api/opportunities/', opportunity_list, name='opportunity-list'),

    path('api/opportunities/<int:opp_id>/', opportunity_detail, name='opportunity-detail'),
    path('api/opportunities/<int:opp_id>/matches/', opportunity_matches, name='opportunity-matches'),
]