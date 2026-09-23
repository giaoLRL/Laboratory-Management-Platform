from django.urls import path

from apps.competitions import api

urlpatterns = [
    path('competitions', api.competitions_create),
    path('competitions/<str:cid>/update', api.competitions_update),
    path('competitions/<str:cid>/archive', api.competitions_archive),
]
