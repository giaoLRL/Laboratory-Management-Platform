from django.urls import path

from apps.inventory import api

urlpatterns = [
    path('assets', api.assets_create),
    path('assets/<str:aid>/update', api.assets_update),
    path('assets/<str:aid>/maintenance', api.assets_maintenance),
    path('assets/<str:aid>/repair-complete', api.assets_repair_complete),
    path('assets/<str:aid>/retire', api.assets_retire),
    path('loans', api.loans_create),
    path('loans/<str:lid>/review', api.loans_review),
    path('loans/<str:lid>/issue', api.loans_issue),
    path('loans/<str:lid>/cancel', api.loans_cancel),
    path('loans/<str:lid>/request-return', api.loans_request_return),
    path('loans/<str:lid>/receive', api.loans_receive),
]
