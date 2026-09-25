from django.urls import path

from apps.checkins import api

urlpatterns = [
    path('checkins', api.checkins_create),
    path('checkins/signout', api.checkins_signout),
]
