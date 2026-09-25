from django.urls import path

from apps.seats import api

urlpatterns = [
    path('seats/layout', api.seats_layout),
    path('seats/layout/save', api.seats_layout_save),
    path('seats/move', api.seats_move),
    path('seats/status', api.seats_status),
    path('seats/bubble', api.seats_bubble),
    path('seats/character', api.seats_character),
    path('seats/chat', api.seats_chat),
    path('seats/chat/send', api.seats_chat_send),
    path('seats/chat/read', api.seats_chat_read),
    path('seats/chat/<str:cid>/delete', api.seats_chat_delete),
]