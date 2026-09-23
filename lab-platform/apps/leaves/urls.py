from django.urls import path

from apps.leaves import api

urlpatterns = [
    path('leaves', api.leaves_create),
    path('leaves/<str:lid>/review', api.leaves_review),
    path('leaves/<str:lid>/cancel', api.leaves_cancel),
]
