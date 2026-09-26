from django.urls import path

from apps.checkins import api

urlpatterns = [
    path('checkins', api.checkins_create),
    path('checkins/code', api.checkins_code),
    path('checkins/signout', api.checkins_signout),
]
