from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.agent.models import Conversation, AgentMessage
from apps.agent.service import chat, llm_ready
from apps.common.ids import create_with_code, next_code
from apps.common.rbac import require
from apps.common.response import ok, fail


def _conv_dict(c, with_messages=False):
    d = {'id': c.id, 'title': c.title or '新对话', 'created': c.created, 'updated': c.updated}
    if with_messages:
        d['messages'] = [
            {'role': m.role, 'content': m.content, 'created': m.created}
            for m in c.messages.exclude(role='tool').order_by('created')
        ]
    if c.pending_op:
        d['pendingOp'] = {'name': c.pending_op.get('name'),
                          'summary': c.pending_op.get('summary', '')}
    return d


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def conversations_list(request):
    if (err := require(request.user, 'action:agent.history', '没有查看会话历史的权限')):
        return err
    convs = Conversation.objects.filter(user=request.user)
    return ok([_conv_dict(c) for c in convs])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def conversation_detail(request, cid):
    if (err := require(request.user, 'action:agent.history', '没有查看会话历史的权限')):
        return err
    try:
        conv = Conversation.objects.get(pk=cid, user=request.user)
    except Conversation.DoesNotExist:
        return fail('会话不存在', 404)
    return ok(_conv_dict(conv, with_messages=True))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def agent_chat(request):
    if (err := require(request.user, 'action:agent.chat', '没有发起对话的权限')):
        return err
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
        conv = create_with_code(Conversation, 'CONV',
                                user=request.user, title=message[:32])
        if not conv.title:
            conv.title = '新对话'
            conv.save()

    AgentMessage.objects.create(conversation=conv, role='user', content=message)
    try:
        reply, pending = chat(conv, message, request.user)
    except requests_exception() as e:
        return fail(f'模型调用失败：{e}', 502)
    AgentMessage.objects.create(conversation=conv, role='assistant', content=reply)
    conv.updated = timezone_now()
    conv.save()
    return ok({'conversationId': conv.id, 'reply': reply,
               'title': conv.title,
               'pendingOp': pending,
               'messages': [
                   {'role': m.role, 'content': m.content}
                   for m in conv.messages.exclude(role='tool').order_by('created')]})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def agent_confirm(request):
    """确认执行暂存写操作（智能体代操作，二次确认后落库）。"""
    from apps.agent.models import Conversation
    from apps.agent.service import execute_pending_op
    cid = str((request.data or {}).get('conversationId', '')).strip()
    conv = Conversation.objects.filter(pk=cid, user=request.user).first()
    if not conv:
        return fail('会话不存在', 404)
    op, result, error = execute_pending_op(request.user, conv)
    if error:
        return fail(error, 403 if '权限' in error else 400)
    # 追加一条 assistant 说明消息，前端可读取
    from apps.agent.models import AgentMessage
    AgentMessage.objects.create(conversation=conv, role='assistant', content=result)
    conv.updated = timezone_now()
    conv.save()
    return ok({'message': result, 'messages': [
        {'role': m.role, 'content': m.content}
        for m in conv.messages.exclude(role='tool').order_by('created')]})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def agent_cancel(request):
    from apps.agent.models import Conversation
    cid = str((request.data or {}).get('conversationId', '')).strip()
    conv = Conversation.objects.filter(pk=cid, user=request.user).first()
    if not conv:
        return fail('会话不存在', 404)
    conv.pending_op = None
    conv.save(update_fields=['pending_op'])
    return ok({'ok': True, 'messages': [
        {'role': m.role, 'content': m.content}
        for m in conv.messages.exclude(role='tool').order_by('created')]})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agent_memory(request):
    from apps.agent.models import UserMemory
    return ok([{'key': m.key, 'value': m.value, 'updated': m.updated}
               for m in UserMemory.objects.filter(user=request.user)])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def agent_memory_set(request):
    from apps.accounts.models import OperationLog
    from apps.agent.models import UserMemory
    d = request.data or {}
    key = str(d.get('key', '')).strip()[:64]
    value = str(d.get('value', '')).strip()[:2000]
    if not key:
        return fail('请填写记忆标签')
    UserMemory.objects.update_or_create(user=request.user, key=key, defaults={'value': value})
    OperationLog.objects.create(actor=request.user, text=f'维护个人记忆 · {key}')
    return ok({'key': key})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def agent_memory_delete(request):
    from apps.agent.models import UserMemory
    key = str((request.data or {}).get('key', '')).strip()[:64]
    deleted, _ = UserMemory.objects.filter(user=request.user, key=key).delete()
    return ok({'deleted': bool(deleted)})


def requests_exception():
    import requests
    return requests.RequestException


def timezone_now():
    from django.utils import timezone
    return timezone.now()
