from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import OperationLog
from apps.common.ids import next_code, parse_member_id
from apps.common.permissions import get_member
from apps.common.rbac import can, can_manage, require
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
        'groupId': t.group_id or '',
        'groupName': t.group.name if t.group_id else '',
        'due': t.due, 'created': t.created, 'updated': t.updated,
        'completedAt': t.completed_at,
        'completionNote': t.completion_note,
        'score': t.score,
        'submission': t.submission,
        'submittedAt': t.submitted_at,
        'reviewerId': f'm{t.reviewer_id}' if t.reviewer_id else '',
        'reviewerName': _member_name(t.reviewer),
        'reviewedById': f'm{t.reviewed_by_id}' if t.reviewed_by_id else '',
        'reviewedByName': _member_name(t.reviewed_by),
        'reviewedAt': t.reviewed_at,
        'reviewOpinion': t.review_opinion,
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
        return None, fail('看板列不合法')
    priority = str(d.get('priority', instance.priority if instance else 'normal')).strip()
    if priority not in ('low', 'normal', 'high', 'urgent'):
        return None, fail('优先级不合法')
    from django.utils.dateparse import parse_datetime
    due_raw = d.get('due', instance.due if instance else None)
    due = None
    if due_raw:
        due = due_raw if hasattr(due_raw, 'isoformat') else parse_datetime(str(due_raw))
        if not due:
            return None, fail('截止时间格式不正确')
    if 'assigneeId' in d:
        assignee_id = parse_member_id(str(d.get('assigneeId') or ''))
        if d.get('assigneeId') and not assignee_id:
            return None, fail('负责人不合法')
    elif instance is not None:
        assignee_id = instance.assignee_id
    else:
        assignee_id = None
    if 'reviewerId' in d:
        reviewer_id = parse_member_id(str(d.get('reviewerId') or ''))
        if d.get('reviewerId') and not reviewer_id:
            return None, fail('审核人不合法')
    elif instance is not None:
        reviewer_id = instance.reviewer_id
    else:
        reviewer_id = None
    from apps.accounts.models import LabGroup
    group_id = str(d.get('groupId', instance.group_id if instance else '') or '').strip()
    group = None
    if group_id:
        group = LabGroup.objects.filter(pk=group_id).first()
        if not group:
            return None, fail('指定的小组不存在', 404)
    fields = {
        'title': title, 'status': status, 'priority': priority, 'due': due,
        'description': str(d.get('description', instance.description if instance else '')),
        'assignee_id': assignee_id, 'reviewer_id': reviewer_id, 'group': group,
    }
    return fields, None


def _can_edit_task(user, task):
    """小组任务：本组成员（含队长）可推进；其余需 task.update 权限（管理角色）。"""
    if can(user, 'action:task.update'):
        return True
    prof = get_member(user)
    return bool(prof and task.group_id and prof.group_fk_id == task.group_id)


def _can_submit(user, task):
    """提交作业：负责人本人、同小组成员，或有编辑权限者（管理角色可代提交）。"""
    if can(user, 'action:task.update'):
        return True
    if task.assignee_id and task.assignee_id == user.pk:
        return True
    prof = get_member(user)
    return bool(prof and task.group_id and prof.group_fk_id == task.group_id)


def _notify_assigned(task, request):
    """指派任务：站内信 + 指派即时邮件。异常吞掉不影响主流程（与单建行为一致）。"""
    if not (task.assignee_id and task.assignee_id != request.user.pk):
        return
    try:
        from apps.notify.service import create
        create(task.assignee, 'task_assigned', f'新任务指派 · {task.title[:30]}',
               f'{task.id}' + (f' · 截止 {timezone.localtime(task.due).strftime("%m-%d %H:%M")}' if task.due else ''),
               ref_type='task', ref_id=task.id, link='tasks')
        # 指派即时邮件（规则 task_assigned，即时发送）
        from apps.email.models import EmailRule
        from apps.email.service import _trigger_by_rule, _member_email
        erule = EmailRule.objects.filter(key='task_assigned').first()
        if erule and erule.enabled:
            prof = getattr(task.assignee, 'member_profile', None)
            ename = prof.name if prof else task.assignee.username
            _trigger_by_rule(erule, {
                'name': ename, 'title': task.title, 'id': task.id,
                'due': f' · 截止 {timezone.localtime(task.due).strftime("%m-%d %H:%M")}' if task.due else '',
            }, 'task', task.id, [_member_email(task.assignee)])
    except Exception:  # noqa: BLE001
        pass


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def tasks_create(request):
    me = get_member(request.user)
    if (err := require(request.user, 'action:task.create', '没有创建任务的权限')):
        return err
    fields, err = _validate_task(request.data or {})
    if err:
        return err
    task = Task.objects.create(id=next_code(Task, 'TASK'), creator=request.user, **fields)
    _log(request, f'创建任务 · {task.id} {task.title[:30]}')
    _notify_assigned(task, request)
    return ok({'id': task.id})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def tasks_batch(request):
    """批量布置：同一标题/描述/优先级/截止/小组，为多个成员各建一条独立任务。"""
    me = get_member(request.user)
    if (err := require(request.user, 'action:task.create', '没有创建任务的权限')):
        return err
    d = request.data or {}
    title = str(d.get('title', '')).strip()
    if not title:
        return fail('请填写任务标题')
    raw_ids = d.get('assigneeIds') or []
    if not isinstance(raw_ids, list) or not raw_ids:
        return fail('请选择至少一位成员')
    if len(raw_ids) > 50:
        return fail('单次批量布置最多 50 人')
    assignee_ids = []
    for rid in raw_ids:
        pid = parse_member_id(rid)
        if not pid:
            return fail(f'成员 {rid} 不合法')
        assignee_ids.append(pid)
    fields, err = _validate_task({**d, 'assigneeId': ''})
    if err:
        return err
    fields.pop('assignee_id', None)  # 负责人由 assigneeIds 逐个指定
    from django.db import transaction
    created = []
    with transaction.atomic():
        for pid in assignee_ids:
            task = Task.objects.create(id=next_code(Task, 'TASK'), creator=request.user,
                                       assignee_id=pid, **fields)
            created.append(task)
            _log(request, f'批量布置任务 · {task.id} {task.title[:30]}')
    for task in created:
        _notify_assigned(task, request)
    return ok({'ids': [t.id for t in created]})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def tasks_submit(request, tid):
    """提交作业：负责人/组员把任务提交为待审核，附提交内容，可选上传附件。"""
    try:
        task = Task.objects.get(pk=tid)
    except Task.DoesNotExist:
        return fail('任务不存在', 404)
    if not _can_submit(request.user, task):
        return fail('只有负责人或同小组成员可以提交', 403)
    if task.status not in (Task.STATUS_TODO, Task.STATUS_DOING):
        return fail('仅待办或进行中的任务可以提交', 409)
    task.submission = str(request.data.get('submission', ''))[:4000]
    if not task.submission.strip():
        return fail('请填写提交内容')
    f = request.FILES.get('file')
    if f:
        if f.size > 50 * 1024 * 1024:
            return fail('附件不能超过 50MB')
        import os
        ext = os.path.splitext(f.name or '')[1].lower().lstrip('.')
        if ext not in ('jpg', 'jpeg', 'png', 'gif', 'webp', 'mp4', 'mov', 'avif', 'pdf', 'zip', 'rar', '7z', 'doc', 'docx', 'txt', 'md'):
            return fail(f'不支持的文件类型 .{ext}')
        TaskAttachment.objects.create(task=task, file=f, name=f.name, uploaded_by=request.user)
    task.status = Task.STATUS_SUBMITTED
    task.submitted_at = timezone.now()
    task.save()
    _log(request, f'提交任务 · {task.id} {task.title[:30]}')
    if task.creator_id and task.creator_id != request.user.pk:
        try:
            from apps.notify.service import create
            create(task.creator, 'task_submitted', f'任务待审核 · {task.title[:30]}',
                   f'{task.id} · 已提交作业', ref_type='task', ref_id=task.id, link='tasks')
        except Exception:  # noqa: BLE001
            pass
    return ok({'status': task.status})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def tasks_review(request, tid):
    """审核：通过→已完成并打分（发积分）；退回→回到进行中并记意见。"""
    if (err := require(request.user, 'action:task.review', '没有审核任务的权限')):
        return err
    try:
        task = Task.objects.select_related('assignee').get(pk=tid)
    except Task.DoesNotExist:
        return fail('任务不存在', 404)
    if task.status != Task.STATUS_SUBMITTED:
        return fail('仅待审核的任务可以审核', 409)
    if task.assignee_id == request.user.pk:
        return fail('不能审核自己的任务', 403)
    decision = str((request.data or {}).get('decision', '')).strip()
    if decision not in ('approve', 'reject'):
        return fail('审核决策不合法')
    task.reviewed_by = request.user
    task.reviewed_at = timezone.now()
    if decision == 'reject':
        opinion = str(request.data.get('opinion', '')).strip()
        if not opinion:
            return fail('退回时请填写审核意见')
        task.review_opinion = opinion[:2000]
        task.status = Task.STATUS_DOING
        task.completed_at = None
        task.save()
        _log(request, f'任务退回 · {task.id} {task.title[:30]} · {opinion[:50]}')
        if task.assignee_id:
            try:
                from apps.notify.service import create
                create(task.assignee, 'task_rejected', f'任务被退回 · {task.title[:30]}',
                       f'{task.id} · {opinion[:60]}', ref_type='task', ref_id=task.id, link='tasks')
            except Exception:  # noqa: BLE001
                pass
        return ok({'status': task.status})
    try:
        score = int((request.data or {}).get('score'))
    except (TypeError, ValueError):
        return fail('评分须为 1-5 的整数')
    if not 1 <= score <= 5:
        return fail('评分须为 1-5 的整数')
    opinion = str(request.data.get('opinion', '')).strip()
    task.score = score
    task.review_opinion = opinion[:2000]
    task.status = Task.STATUS_DONE
    task.completed_at = timezone.now()
    task.save()
    awarded = 0
    if task.assignee_id:
        from apps.points.models import PointRule
        from apps.points.service import award
        rule = PointRule.objects.filter(key='task_complete').first()
        base = rule.points if rule and rule.enabled else 0
        amount = score * base
        if amount:
            rec = award(task.assignee, 'task_complete', ref_type='task', ref_id=task.id, points=amount,
                        reason=f'{task.id} 评分 {score}★', actor=request.user)
            awarded = rec.points if rec else 0
    _log(request, f'任务审核通过 · {task.id} {score}★' + (f' · 发放 {awarded} 分' if awarded else ''))
    if task.assignee_id:
        try:
            from apps.notify.service import create
            create(task.assignee, 'task_reviewed', f'任务已通过 · {task.title[:30]}',
                   f'{task.id} · {score}★' + (f' · 积分 +{awarded}' if awarded else ''),
                   ref_type='task', ref_id=task.id, link='tasks')
        except Exception:  # noqa: BLE001
            pass
    return ok({'status': task.status, 'score': score, 'awarded': awarded})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def tasks_update(request, tid):
    try:
        task = Task.objects.get(pk=tid)
    except Task.DoesNotExist:
        return fail('任务不存在', 404)
    if not _can_edit_task(request.user, task):
        return fail('没有编辑任务的权限', 403)
    if task.status == Task.STATUS_SUBMITTED and 'status' in (request.data or {}):
        return fail('待审核任务须由审核决定去向', 409)
    old_status, old_assignee = task.status, task.assignee_id
    fields, err = _validate_task(request.data or {}, instance=task)
    if err:
        return err
    matched = [k for k in ('title', 'description', 'status', 'priority', 'due', 'assignee_id', 'reviewer_id', 'group') if k in fields]
    for k in matched:
        setattr(task, k, fields[k])
    if 'completionNote' in request.data:
        task.completion_note = str(request.data.get('completionNote', ''))[:2000]
    from django.utils import timezone
    if task.status == Task.STATUS_DONE and not task.completed_at:
        task.completed_at = timezone.now()
    elif task.status != Task.STATUS_DONE:
        task.completed_at = None
    task.save()
    _log(request, f'更新任务 · {task.id} {task.title[:30]}')
    from apps.notify.service import create
    if task.assignee_id and task.assignee_id != old_assignee and task.assignee_id != request.user.pk:
        create(task.assignee, 'task_assigned', f'任务指派 · {task.title[:30]}',
               f'{task.id}', ref_type='task', ref_id=task.id, link='tasks')
        # 转派即时邮件（规则 task_assigned，即时发送）
        from apps.email.models import EmailRule
        from apps.email.service import _trigger_by_rule, _member_email
        erule = EmailRule.objects.filter(key='task_assigned').first()
        if erule and erule.enabled:
            prof = getattr(task.assignee, 'member_profile', None)
            ename = prof.name if prof else task.assignee.username
            _trigger_by_rule(erule, {
                'name': ename, 'title': task.title, 'id': task.id,
                'due': f' · 截止 {timezone.localtime(task.due).strftime("%m-%d %H:%M")}' if task.due else '',
            }, 'task', task.id, [_member_email(task.assignee)])
    if task.status == Task.STATUS_DONE and old_status != Task.STATUS_DONE and task.creator_id != request.user.pk:
        create(task.creator, 'task_completed', f'任务已完成 · {task.title[:30]}',
               f'{task.id}', ref_type='task', ref_id=task.id, link='tasks')
    return ok()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def tasks_score(request, tid):
    """已完成任务评分 1-5 星：星级 × 规则分值 发放给负责人。"""
    if (err := require(request.user, 'action:task.score', '没有任务评分的权限')):
        return err
    try:
        task = Task.objects.select_related('assignee').get(pk=tid)
    except Task.DoesNotExist:
        return fail('任务不存在', 404)
    if task.status != Task.STATUS_DONE:
        return fail('只能给已完成的任务评分', 409)
    if task.reviewed_at:
        return fail('该任务已审核打分', 409)
    try:
        score = int((request.data or {}).get('score'))
    except (TypeError, ValueError):
        return fail('评分须为 1-5 的整数')
    if not 1 <= score <= 5:
        return fail('评分须为 1-5 的整数')
    if task.assignee_id == request.user.pk:
        return fail('不能给自己的任务评分', 403)
    task.score = score
    task.save(update_fields=['score', 'updated'])
    awarded = 0
    if task.assignee_id:
        from apps.points.models import PointRule
        from apps.points.service import award
        rule = PointRule.objects.filter(key='task_complete').first()
        base = rule.points if rule and rule.enabled else 0
        amount = score * base
        if amount:
            rec = award(task.assignee, 'task_complete', ref_type='task', ref_id=task.id, points=amount,
                        reason=f'{task.id} 评分 {score}★', actor=request.user)
            awarded = rec.points if rec else 0
    _log(request, f'任务评分 · {task.id} {score}★' + (f' · 发放 {awarded} 分' if awarded else ''))
    if task.assignee_id:
        from apps.notify.service import create
        create(task.assignee, 'task_scored', f'任务已评分 · {task.title[:30]}',
               f'{task.id} · {score}★' + (f' · 积分 +{awarded}' if awarded else ''),
               ref_type='task', ref_id=task.id, link='tasks')
    return ok({'score': score, 'awarded': awarded})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tasks_detail(request, tid):
    """任务详情：完整字段 + 附件 + 时间线 + 当前用户可编辑标记。"""
    try:
        task = Task.objects.select_related('assignee', 'creator', 'group').prefetch_related('attachments').get(pk=tid)
    except Task.DoesNotExist:
        return fail('任务不存在', 404)
    from apps.accounts.models import OperationLog
    logs = []
    for lg in OperationLog.objects.filter(text__icontains=task.id).order_by('-at')[:30]:
        prof = getattr(lg.actor, 'member_profile', None)
        logs.append({'actor': prof.name if prof else (lg.actor.username if lg.actor else ''),
                     'text': lg.text, 'at': lg.at})
    return ok({
        'task': _task_dict(task),
        'editable': _can_edit_task(request.user, task),
        'logs': logs,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def tasks_delete(request, tid):
    if (err := require(request.user, 'action:task.delete', '没有删除任务的权限')):
        return err
    try:
        task = Task.objects.get(pk=tid)
    except Task.DoesNotExist:
        return fail('任务不存在', 404)
    if task.creator_id != request.user.pk and not can_manage(request.user):
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
    if not _can_edit_task(request.user, task):
        return fail('没有上传附件的权限', 403)
    f = request.FILES.get('file')
    if not f:
        return fail('请选择要上传的文件')
    if f.size > 50 * 1024 * 1024:
        return fail('附件不能超过 50MB')
    import os
    ext = os.path.splitext(f.name or '')[1].lower().lstrip('.')
    if ext not in ('jpg', 'jpeg', 'png', 'gif', 'webp', 'mp4', 'mov', 'avif', 'pdf', 'zip', 'rar', '7z', 'doc', 'docx', 'txt', 'md'):
        return fail(f'不支持的文件类型 .{ext}')
    att = TaskAttachment.objects.create(task=task, file=f, name=f.name, uploaded_by=request.user)
    return ok({'url': att.file.url, 'name': att.name})
