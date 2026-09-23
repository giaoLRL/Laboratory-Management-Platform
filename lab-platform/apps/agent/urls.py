from django.urls import path

from apps.agent import api

urlpatterns = [
    path('agent/conversations', api.conversations_list),
    path('agent/chat', api.agent_chat),
    path('agent/conversations/<str:cid>', api.conversation_detail),
]
