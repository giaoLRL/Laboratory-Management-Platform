from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import OperationLog
from apps.common.ids import next_code, parse_member_id
from apps.common.permissions import get_member, is_staff
from apps.common.response import ok, fail
from apps.tasksapp.models import Task, TaskAttachment


def _log(request, text):
    OperationLog.objects.create(
        actor=request.user if request.user.is_authenticated else None, text=str(text)[:256])


def _task_dict(t):
    return {
        'id': t.id, 'title': t.title, 'description': t.description,
        'status': t.status, 'priority': t.priority,
        'assigneeId': f'm{t.assignee_id}' if t.assignee_id else '',
        'assigneeName': _member_name(t.assignee),
        'creatorId': f'm{t.creator_id}' if t.creator_id else '',
        'due': t.due, 'created': t.created, 'updated': t.updated,
        'attachments': [{'url': a.file.url, 'name': a.name or a.file.name} for a in t.attachments.all()],
    }


def _member_name(user):
    prof = getattr(user, 'member_profile', None)
    return prof.name if prof else (user.username if user else '')


def workspace_slice(profile, staff):
    """全员可见任务（协作看板），隐私字段无。"""
    tasks = [_task_dict(t) for t in Task.objects.prefetch_related('attachments').all()]
    ts = [t.updated for t in Task.objects.all()]
    return {'tasks': tasks, '_ts': ts}


def _validate_task(d, instance=None):
    title = str(d.get('title', instance.title if instance else '')).strip()
    if not title:
        return None, fail('请填写任务标题')
    status = str(d.get('status', instance.status if instance else Task.STATUS_TODO)).strip()
    if status not in ('todo', 'doing', 'done'):
        return fail('看板列不合法')
    priority = str(d.get('priority', instance.priority if instance else 'normal')).strip()
    if priority not in ('low', 'normal', 'high', 'urgent'):
        return fail('优先级不合法')
    from django.utils.dateparse import parse_datetime
    due_raw = d.get('due', instance.due if instance else None)
    due = None
    if due_raw:
        due = due_raw if hasattr(due_raw, 'isoformat') else parse_datetime(str(due_raw))
        if not due:
            return fail('截止时间格式不正确')
    assignee_id = parse_member_id(d.get('assigneeId', '') or '')
    if d.get('assigneeId') and not assignee_id:
        return fail('负责人不合法')
    fields = {
        'title': title, 'status': status, 'priority': priority, 'due': due,
        'description': str(d.get('description', instance.description if instance else '')),
        'assignee_id': assignee_id,
    }
    return fields, None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def tasks_create(request):
    me = get_member(request.user)
    fields, err = _validate_task(request.data or {})
    if err:
        return err
    task = Task.objects.create(id=next_code(Task, 'TASK'), creator=request.user, **fields)
    _log(request, f'创建任务 · {task.id} {task.title[:30]}')
    return ok({'id': task.id})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def tasks_update(request, tid):
    try:
        task = Task.objects.get(pk=tid)
    except Task.DoesNotExist:
        return fail('任务不存在', 404)
    fields, err = _validate_task(request.data or {}, instance=task)
    if err:
        return err
    for k, v in fields.items():
        setattr(task, k, v)
    task.save()
    _log(request, f'更新任务 · {task.id} {task.title[:30]}')
    return ok()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def tasks_delete(request, tid):
    try:
        task = Task.objects.get(pk=tid)
    except Task.DoesNotExist:
        return fail('任务不存在', 404)
    if task.creator_id != request.user.pk and not is_staff(request.user):
        return fail('只有创建者或管理员可以删除任务', 403)
    _log(request, f'删除任务 · {task.id} {task.title[:30]}')
    task.delete()
    return ok()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def tasks_attachment(request, tid):
    try:
        task = Task.objects.get(pk=tid)
    except Task.DoesNotExist:
        return fail('任务不存在', 404)
    f = request.FILES.get('file')
    if not f:
        return fail('请选择要上传的文件')
    if f.size > 8 * 1024 * 1024:
        return fail('附件不能超过 8MB')
    att = TaskAttachment.objects.create(task=task, file=f, name=f.name, uploaded_by=request.user)
    return ok({'url': att.file.url, 'name': att.name})
