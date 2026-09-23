from django.urls import path

from apps.agent import api

urlpatterns = [
    path('agent/chat', api.agent_chat),
    path('agent/confirm', api.agent_confirm),
    path('agent/cancel', api.agent_cancel),
    path('agent/memory', api.agent_memory),
    path('agent/memory/set', api.agent_memory_set),
    path('agent/memory/delete', api.agent_memory_delete),
    path('agent/conversations', api.conversations_list),
    path('agent/conversations/<str:cid>', api.conversation_detail),
]
