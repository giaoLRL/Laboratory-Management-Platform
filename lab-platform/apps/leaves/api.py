from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import OperationLog
from apps.common.ids import next_code
from apps.common.permissions import get_member, is_staff
from apps.common.response import ok, fail
from apps.leaves.models import Leave


def _log(request, text):
    OperationLog.objects.create(
        actor=request.user if request.user.is_authenticated else None, text=str(text)[:256])


def _leave_dict(l, viewer_id, staff):
    """原因与意见按角色隐藏：普通成员只能看到自己的完整记录。"""
    own = staff or l.member_id == viewer_id
    d = {'id': l.id, 'memberId': f'm{l.member_id}', 'start': l.start, 'end': l.end, 'status': l.status}
    if own:
        d.update({'reason': l.reason, 'created': l.created,
                  'reviewer': f'm{l.reviewer_id}' if l.reviewer_id else '',
                  'reviewed': l.reviewed, 'opinion': l.opinion})
    return d


def workspace_slice(profile, staff):
    """普通成员：自己的完整记录 + 其他人的有效已批准请假（仅 memberId/start/end/status）。"""
    now = timezone.now()
    out, ts = [], []
    qs = Leave.objects.select_related('member').order_by('-created')
    for l in qs:
        own = staff or l.member_id == profile.user_id
        if own:
            out.append(_leave_dict(l, profile.user_id, staff))
            ts.append(l.created)
        elif l.status == Leave.STATUS_APPROVED and l.start <= now <= l.end:
            out.append({'id': l.id, 'memberId': f'm{l.member_id}', 'start': l.start,
                        'end': l.end, 'status': l.status})
    return {'leaves': out, '_ts': ts}


def has_pending_leave(profile):
    return Leave.objects.filter(member_id=profile.user_id, status=Leave.STATUS_PENDING).exists()


def _can_review(leave, viewer):
    if leave.member_id == viewer.pk:
        return '不能审批自己的请假'
    prof = getattr(viewer, 'member_profile', None)
    if prof and prof.role == 'manager':
        target = getattr(leave.member, 'member_profile', None)
        if not target or target.role != 'member':
            return '负责人只能审批普通成员的请假'
    return None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def leaves_create(request):
    me = get_member(request.user)
    d = request.data or {}
    try:
        from django.utils.dateparse import parse_datetime
        start = parse_datetime(str(d.get('start', '')))
        end = parse_datetime(str(d.get('end', '')))
    except (ValueError, TypeError):
        return fail('时间格式不正确')
    if not start or not end:
        return fail('请填写开始和结束时间')
    reason = str(d.get('reason', '')).strip()
    now = timezone.now()
    if start >= end:
        return fail('开始时间必须早于结束时间')
    if end <= now:
        return fail('不能提交已结束的请假')
    overlap = Leave.objects.filter(
        member=request.user, status__in=(Leave.STATUS_PENDING, Leave.STATUS_APPROVED),
        start__lt=end, end__gt=start).exists()
    if overlap:
        return fail('与已有的待审批/已批准请假时间重叠', 409)

    leave = Leave.objects.create(id=next_code(Leave, 'LV'), member=request.user,
                                 start=start, end=end, reason=reason)
    _log(request, f'{me.name} 提交请假 · {leave.id}')
    return ok({'id': leave.id})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def leaves_review(request, lid):
    if not is_staff(request.user):
        return fail('只有指导老师或负责人可以审批请假', 403)
    try:
        leave = Leave.objects.get(pk=lid)
    except Leave.DoesNotExist:
        return fail('请假单不存在', 404)
    err = _can_review(leave, request.user)
    if err:
        return fail(err, 403)
    if leave.status != Leave.STATUS_PENDING:
        return fail('该请假单不在待审批状态', 409)

    d = request.data or {}
    decision = str(d.get('decision', '')).strip()
    opinion = str(d.get('opinion', '')).strip()
    if decision not in ('approve', 'reject'):
        return fail('decision 须为 approve 或 reject')
    if decision == 'reject' and not opinion:
        return fail('拒绝时必须填写原因')

    leave.status = Leave.STATUS_APPROVED if decision == 'approve' else Leave.STATUS_REJECTED
    leave.reviewer = request.user
    leave.reviewed = timezone.now()
    leave.opinion = opinion
    leave.save()
    _log(request, f"审批请假 {leave.id} · {'批准' if decision == 'approve' else '拒绝'}")
    return ok()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def leaves_cancel(request, lid):
    try:
        leave = Leave.objects.get(pk=lid)
    except Leave.DoesNotExist:
        return fail('请假单不存在', 404)
    if leave.member_id != request.user.pk:
        return fail('只能撤销自己的请假', 403)
    if leave.status != Leave.STATUS_PENDING:
        return fail('只有待审批的请假可以撤销', 409)
    leave.status = Leave.STATUS_CANCELLED
    leave.save()
    _log(request, f'撤销请假 · {leave.id}')
    return ok()
