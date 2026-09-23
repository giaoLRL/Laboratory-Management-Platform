from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.agent.models import Conversation, AgentMessage
from apps.agent.service import chat, llm_ready
from apps.common.ids import next_code
from apps.common.response import ok, fail


def _conv_dict(c, with_messages=False):
    d = {'id': c.id, 'title': c.title or '新对话', 'created': c.created, 'updated': c.updated}
    if with_messages:
        d['messages'] = [
            {'role': m.role, 'content': m.content, 'created': m.created}
            for m in c.messages.exclude(role='tool').order_by('created')
        ]
    return d


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def conversations_list(request):
    convs = Conversation.objects.filter(user=request.user)
    return ok([_conv_dict(c) for c in convs])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def conversation_detail(request, cid):
    try:
        conv = Conversation.objects.get(pk=cid, user=request.user)
    except Conversation.DoesNotExist:
        return fail('会话不存在', 404)
    return ok(_conv_dict(conv, with_messages=True))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def agent_chat(request):
    if not llm_ready():
        return fail('智能体未配置：请设置 LAB_LLM_API_KEY 环境变量', 503)
    d = request.data or {}
    message = str(d.get('message', '')).strip()
    if not message:
        return fail('请输入消息')

    cid = str(d.get('conversationId', '')).strip()
    if cid:
        conv = Conversation.objects.filter(pk=cid, user=request.user).first()
        if not conv:
            return fail('会话不存在', 404)
    else:
        conv = Conversation.objects.create(id=next_code(Conversation, 'CONV'),
                                           user=request.user, title=message[:32])
        if not conv.title:
            conv.title = '新对话'
            conv.save()

    AgentMessage.objects.create(conversation=conv, role='user', content=message)
    try:
        reply = chat(conv, message)
    except requests_exception() as e:
        return fail(f'模型调用失败：{e}', 502)
    AgentMessage.objects.create(conversation=conv, role='assistant', content=reply)
    conv.updated = timezone_now()
    conv.save()
    return ok({'conversationId': conv.id, 'reply': reply,
               'title': conv.title, 'messages': [
                   {'role': m.role, 'content': m.content}
                   for m in conv.messages.exclude(role='tool').order_by('created')]})


def requests_exception():
    import requests
    return requests.RequestException


def timezone_now():
    from django.utils import timezone
    return timezone.now()
