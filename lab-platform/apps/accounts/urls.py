from django.urls import path

from apps.accounts import api

urlpatterns = [
    path('auth/login', api.auth_login),
    path('auth/me', api.auth_me),
    path('auth/logout', api.auth_logout),
    path('workspace', api.workspace),
    path('members', api.members_create),
    path('members/me/update', api.me_update),
    path('members/me/status', api.me_status),
    path('members/<str:mid>/update', api.members_update),
    path('members/<str:mid>/active', api.members_active),
]
