"""积分：规则配置、排行榜、个人趋势。积分流水由业务流程经由 service.award() 发放。"""

from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone
from django.contrib.auth.models import User
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import MemberProfile
from apps.common.ids import member_id, parse_member_id
from apps.common.rbac import require
from apps.common.response import ok, fail
from apps.points.models import PointRecord, PointRule
from apps.points.service import totals_map, user_total


def workspace_slice(profile, staff):
    """快照补充：本人总分（成员总分已由 build_workspace 附在 members 上）。"""
    return {'points_total': user_total(profile.user_id)}


def _rule_dict(r):
    return {'key': r.key, 'label': r.label, 'points': r.points, 'enabled': r.enabled, 'builtin': r.builtin}


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def points_rules(request):
    """规则列表：管理角色可读全部；普通成员只读启用项。"""
    me = getattr(request.user, 'member_profile', None)
    if not me:
        return fail('账号不存在或已停用', 403)
    if require(request.user, 'action:points.rules', '') is None:
        qs = PointRule.objects.all()
    else:
        qs = PointRule.objects.filter(enabled=True)
    return ok([_rule_dict(r) for r in qs])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def points_rules_save(request):
    if (err := require(request.user, 'action:points.rules', '没有配置积分规则的权限')):
        return err
    d = request.data or {}
    for item in d.get('rules') or []:
        rule = PointRule.objects.filter(key=str(item.get('key', ''))).first()
        if not rule:
            continue
        try:
            points = min(max(int(item.get('points', rule.points)), -100), 1000)
        except (TypeError, ValueError):
            points = rule.points
        rule.points = points
        rule.enabled = bool(item.get('enabled', rule.enabled))
        rule.save(update_fields=['points', 'enabled'])
    return ok({'rules': [_rule_dict(r) for r in PointRule.objects.all()]})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def points_manual(request):
    """手动调分：教师对突出表现加分 / 违纪扣分（配审计日志）。"""
    if (err := require(request.user, 'action:points.manual', '没有手动调分的权限')):
        return err
    d = request.data or {}
    mid = parse_member_id(str(d.get('memberId', '')))
    if not mid:
        return fail('成员不合法')
    try:
        points = int(d.get('points'))
    except (TypeError, ValueError):
        return fail('请提供整数分值')
    points = min(max(points, -100), 100)
    if points == 0:
        return fail('分值不能为 0')
    reason = str(d.get('reason', '')).strip()
    if not reason:
        return fail('请填写调分原因')
    me = getattr(request.user, 'member_profile', None)
    if not me:
        return fail('账号不存在或已停用', 403)
    target_user = request.user if mid == request.user.pk else User.objects.filter(pk=mid).first()
    if not target_user:
        return fail('成员不存在', 404)
    from apps.points.service import award
    # ref_id 用时间戳+随机唯一值：允许同对象多次手动调分（不受 uniq_point_award 去重限制）
    import time as _t
    import uuid as _u
    ref_id = f'manual-{_t.time():.6f}-{_u.uuid4().hex[:8]}'
    rec = award(target_user, 'custom', ref_type='manual', ref_id=ref_id,
                points=points, reason=f'{reason}（由 {me.name} 调分）')
    if not rec:
        return fail('调分失败：规则未启用或分值异常', 409)
    from apps.accounts.models import OperationLog
    OperationLog.objects.create(
        actor=request.user, text=f'手动调分 {me.name} → {mid} {"+" if points > 0 else ""}{points} 分 · {reason}')
    return ok({'total': user_total(mid)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def points_leaderboard(request):
    """排行榜：period=week|month|all（默认 all）。"""
    # period 必须从查询串读出来：前端一直是 /points/leaderboard?period=week 这样调的，
    # 漏了这一步会直接 NameError → 500，而前端 catch 后只显示空榜单（页面看着没坏、其实一直空着）。
    period = request.GET.get('period') or 'all'
    if period not in ('week', 'month', 'all'):
        period = 'all'
    qs = PointRecord.objects.all()
    if period == 'week':
        qs = qs.filter(created__gte=timezone.now() - timedelta(days=7))
    elif period == 'month':
        qs = qs.filter(created__gte=timezone.now() - timedelta(days=30))
    rows = qs.values('user_id').annotate(points=Sum('points')).order_by('-points')[:30]
    out = []
    from apps.accounts.models import MemberProfile
    profs = {mp.user_id: mp for mp in MemberProfile.objects.filter(active=True)}
    for row in rows:
        mp = profs.get(row['user_id'])
        if not mp:
            continue
        out.append({
            'memberId': member_id(row['user_id']),
            'name': mp.name,
            'group': mp.group or '',
            'points': row['points'] or 0,
        })
    return ok({'period': period, 'ranking': out})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def points_trend(request, mid):
    """近 30 天每日积分趋势（本人或团队管理可视角色可查他人）。"""
    me = getattr(request.user, 'member_profile', None)
    target_id = parse_member_id(mid)
    if not target_id or not me:
        return fail('成员不存在', 404)
    if target_id != request.user.pk and not any(k in _effective(request.user) for k in ('page:members', 'page:member.detail', '*')):
        return fail('没有查看该成员积分的权限', 403)
    start = (timezone.now() - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
    days = {}
    for pr in PointRecord.objects.filter(user_id=target_id, created__gte=start).order_by('created'):
        key = pr.created.date()
        days[key] = days.get(key, 0) + pr.points
    out = []
    for i in range(30):
        day = start.date() + timedelta(days=i)
        out.append({'day': str(day), 'points': days.get(day, 0)})
    return ok({'memberId': mid, 'total': user_total(target_id), 'days': out})


def _effective(user):
    from apps.common.rbac import effective_permissions
    me = getattr(user, 'member_profile', None)
    return effective_permissions(me) if me else frozenset()