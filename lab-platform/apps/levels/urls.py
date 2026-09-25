from django.urls import path

from apps.levels import api

urlpatterns = [
    path('levels', api.levels_list),
    path('levels/mine', api.levels_mine),
    path('levels/member/<str:mid>/profile', api.levels_member_profile),
    path('levels/positions', api.levels_positions),
    path('levels/<str:lid>/connect', api.levels_connect),
    path('levels/<str:lid>/detail', api.levels_detail),
    path('levels/create', api.levels_create),
    path('levels/<str:lid>/update', api.levels_update),
    path('levels/<str:lid>/delete', api.levels_delete),
    path('levels/<str:lid>/tasks', api.levels_link_task),
    path('levels/<str:lid>/tasks/<str:tid>', api.levels_unlink_task),
    path('levels/<str:lid>/submit', api.levels_submit),
    path('levels/<str:lid>/review', api.levels_review),
    path('levels/<str:lid>/reviewers', api.levels_reviewers),
    path('levels/<str:lid>/reviewers/<str:mid>', api.levels_reviewers_remove),
]