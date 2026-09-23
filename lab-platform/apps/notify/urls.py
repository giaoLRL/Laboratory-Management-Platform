from django.urls import path

from apps.notify import api

urlpatterns = [
    path('announcements', api.announcements_list),
    path('announcements/create', api.announcements_create),
    path('announcements/<str:aid>/update', api.announcements_update),
    path('announcements/<str:aid>/read', api.announcements_read),
    path('news', api.news_list),
    path('news/create', api.news_create),
    path('news/<str:nid>/delete', api.news_delete),
    path('notifications', api.notifications_list),
    path('notifications/<str:nid>/read', api.notifications_read),
    path('notifications/read-all', api.notifications_read_all),
]