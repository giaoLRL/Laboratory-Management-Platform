from django.urls import path

from apps.points import api

urlpatterns = [
    path('points/leaderboard', api.points_leaderboard),
    path('points/rules', api.points_rules),
    path('points/rules/save', api.points_rules_save),
    path('points/trend/<str:mid>', api.points_trend),
]