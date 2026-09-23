import re

from django.contrib.auth import authenticate, get_user_model, login as dj_login, logout as dj_logout
from django.contrib.auth.models import User
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import LabGroup, MemberProfile, OperationLog, Role
from apps.accounts.serializers import member_dict, log_dict
from apps.common.ids import member_id, next_code, parse_member_id
from apps.common.permissions import get_member, is_staff
from apps.common.rbac import require
from apps.common.response import ok, fail
from apps.common.workspace import build_workspace

USERNAME_RE = re.compile(r'^\w{3,30}$')
PASSWORD_OK = re.compile(r'^(?=.*[A-Za-z])(?=.*\d).{8,64}$')
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _log(request, member, text, private=False):
    """后端生成审计记录；不使用客户端自报的日志或身份。"""
    OperationLog.objects.create(
        actor=request.user if request.user.is_authenticated else None,
        member=member, text=str(text)[:256], private=private)


def _require_active(request):
    p = get_member(request.user)
    if p is None:
        return None, fail('账号不存在或已停用', 403)
    return p, None


# ─────────────────── 认证 ───────────────────


def _client_info(request):
    """从请求提取 IP 与 UA，用于登录日志。"""
    ip = None
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        ip = xff.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    try:
        from ipaddress import ip_address
        ip_address(ip)  # 校验合法性
    except Exception:
        ip = None
    return ip, str(request.META.get('HTTP_USER_AGENT', ''))[:256]


def _record_login(user, success, ip, ua):
    from apps.accounts.models import LoginLog
    if user is not None and user.pk:
        LoginLog.objects.create(user=user, ip=ip, user_agent=ua, success=success)


@api_view(['POST'])
@permission_classes([])
def auth_login(request):
    d = request.data or {}
    username = str(d.get('username', '')).strip()
    password = str(d.get('password', ''))
    ip, ua = _client_info(request)
    user = authenticate(request, username=username, password=password)
    if user is None:
        _record_login(get_user_model().objects.filter(username__iexact=username).first(), False, ip, ua)
        return fail('账号或密码不正确', 401)
    prof = getattr(user, 'member_profile', None)
    if prof is None:
        _record_login(user, False, ip, ua)
        return fail('账号未关联成员档案', 403)
    if not prof.active:
        _record_login(user, False, ip, ua)
        return fail('账号已停用，请联系负责人', 403)
    _record_login(user, True, ip, ua)
    dj_login(request, user)
    _log(request, prof, f'{prof.name} 登录系统')
    return ok({'id': member_id(user.pk), 'mustChangePassword': prof.must_change_password,
               'mustCompleteProfile': prof.must_complete_profile})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def auth_me(request):
    p, e = _require_active(request)
    if e:
        return e
    return ok({'id': member_id(request.user.pk)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def auth_logout(request):
    dj_logout(request)
    return ok()


# ─────────────────── 工作空间快照 ───────────────────


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def workspace(request):
    p, e = _require_active(request)
    if e:
        return e
    return ok(build_workspace(p, is_staff(request.user)))


# ─────────────────── 成员管理 ───────────────────


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def members_create(request):
    me, e = _require_active(request)
    if e:
        return e
    if (err := require(request.user, 'action:member.create', '没有创建成员账号的权限')):
        return err

    d = request.data or {}
    name = str(d.get('name', '')).strip()
    number = str(d.get('number', '')).strip()
    username = str(d.get('username', '')).strip()
    role = str(d.get('role', 'member')).strip() or 'member'
    password = str(d.get('password', ''))
    confirm = str(d.get('passwordConfirm', password))
    group = str(d.get('group', '')).strip()
    direction = str(d.get('direction', '')).strip()
    contact = str(d.get('contact', '')).strip()
    email = str(d.get('email', '')).strip()

    if not name:
        return fail('请填写姓名')
    if not number:
        return fail('请填写学号/工号')
    if not USERNAME_RE.match(username):
        return fail('登录账号须为 3-30 位字母、数字或下划线')
    if User.objects.filter(username__iexact=username).exists():
        return fail('登录账号已存在（不区分大小写）')
    if MemberProfile.objects.filter(number=number).exists():
        return fail('学号/工号已存在')
    if role not in ('teacher', 'manager', 'member'):
        return fail('角色不合法')
    if me.role == 'manager' and role != 'member':
        return fail('负责人只能创建普通成员账号', 403)
    if not PASSWORD_OK.match(password):
        return fail('密码须为 8-64 位，且至少包含一个英文字母和一个数字')
    if password != confirm:
        return fail('两次输入的密码不一致')
    if email and not EMAIL_RE.match(email):
        return fail('邮箱格式不正确')

    user = User.objects.create_user(username=username, password=password)
    prof = MemberProfile.objects.create(
        user=user, name=name, number=number, role=role,
        group=group, direction=direction, contact=contact, email=email,
        must_complete_profile=True)
    _log(request, prof, f'创建成员账号 · {name}')
    from apps.notify.service import create_many, active_members
    create_many(active_members(exclude=request.user), 'member_joined',
                f'新成员加入 · {name}', '', ref_type='member', ref_id=user.pk, link='members')
    return ok({'id': member_id(user.pk)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def members_update(request, mid):
    me, e = _require_active(request)
    if e:
        return e
    if (err := require(request.user, 'action:member.update', '没有修改成员资料的权限')):
        return err

    target_id = parse_member_id(mid)
    if not target_id:
        return fail('成员不存在', 404)
    try:
        target = MemberProfile.objects.select_related('user').get(user_id=target_id)
    except MemberProfile.DoesNotExist:
        return fail('成员不存在', 404)
    if me.role == 'manager' and target.role != 'member':
        return fail('负责人只能管理普通成员', 403)

    d = request.data or {}
    name = str(d.get('name', '')).strip() or target.name
    number = str(d.get('number', '')).strip() or target.number
    username = str(d.get('username', '')).strip() or target.user.username
    group = str(d.get('group', target.group)).strip()
    direction = str(d.get('direction', target.direction)).strip()
    contact = str(d.get('contact', target.contact)).strip()
    email = str(d.get('email', target.email)).strip()
    role = str(d.get('role', target.role)).strip()

    if role not in ('teacher', 'manager', 'member'):
        return fail('角色不合法')
    if me.role == 'manager':
        role = 'member'  # 负责人不能修改角色
    if email and not EMAIL_RE.match(email):
        return fail('邮箱格式不正确')
    if target.user_id == request.user.pk and role != me.role:
        return fail('不能修改自己的角色')
    if number != target.number and MemberProfile.objects.filter(number=number).exclude(pk=target.pk).exists():
        return fail('学号/工号已存在')
    if username.lower() != target.user.username.lower() and \
            User.objects.filter(username__iexact=username).exclude(pk=target.user_id).exists():
        return fail('登录账号已存在（不区分大小写）')

    target.name, target.number = name, number
    target.group, target.direction, target.contact, target.email = group, direction, contact, email
    target.role = role
    target.save()
    target.user.username = username
    target.user.save()
    _log(request, target, f'更新成员资料 · {name}')
    return ok()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def me_update(request):
    p, e = _require_active(request)
    if e:
        return e
    d = request.data or {}
    name = str(d.get('name', '')).strip()
    number = str(d.get('number', '')).strip()
    direction = str(d.get('direction', p.direction)).strip()
    contact = str(d.get('contact', p.contact)).strip()
    email = str(d.get('email', p.email)).strip()
    if email and not EMAIL_RE.match(email):
        return fail('邮箱格式不正确')
    if number:
        if len(number) > 30:
            return fail('学号 / 工号不能超过 30 个字符')
        from apps.accounts.models import MemberProfile
        if MemberProfile.objects.exclude(pk=p.pk).filter(number=number).exists():
            return fail('该学号 / 工号已存在')
        p.number = number
    if name:
        p.name = name
    if p.must_complete_profile and (not number or not contact or not email):
        return fail('请完善个人资料：学号、联系方式、邮箱不能为空')
    p.direction = direction
    p.contact = contact
    p.email = email
    p.must_complete_profile = False
    p.save()
    _log(request, p, f'{p.name} 更新个人资料')
    return ok()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def me_status(request):
    p, e = _require_active(request)
    if e:
        return e
    d = request.data or {}
    status = str(d.get('status', '')).strip()
    note = str(d.get('note', p.note)).strip()
    if status not in ('空闲', '忙碌', '模拟离线'):
        return fail('状态不合法')
    p.base_status = status
    p.note = note[:256]
    p.save()
    _log(request, p, f'{p.name} 更新状态 · {status}')
    return ok()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def me_password(request):
    """修改自己的密码：需验证旧密码，新密码遵守规则。"""
    p, e = _require_active(request)
    if e:
        return e
    d = request.data or {}
    old = str(d.get('oldPassword', ''))
    new = str(d.get('newPassword', ''))
    confirm = str(d.get('confirmPassword', new))
    if not request.user.check_password(old):
        return fail('旧密码不正确', 403)
    if not PASSWORD_OK.match(new):
        return fail('新密码须为 8-64 位，且至少包含一个英文字母和一个数字')
    if new != confirm:
        return fail('两次输入的新密码不一致')
    if old == new:
        return fail('新密码不能与旧密码相同')
    request.user.set_password(new)
    request.user.save()
    p.must_change_password = False
    p.save(update_fields=['must_change_password', 'updated'])
    _log(request, p, f'{p.name} 修改了登录密码')
    return ok()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def members_reset_password(request, mid):
    """管理员重置他人密码：生成随机密码一次性返回，并标记强制改密。"""
    me, e = _require_active(request)
    if e:
        return e
    if (err := require(request.user, 'action:member.reset_password', '没有重置密码的权限')):
        return err
    target_id = parse_member_id(mid)
    if not target_id:
        return fail('成员不存在', 404)
    try:
        target = MemberProfile.objects.select_related('user').get(user_id=target_id)
    except MemberProfile.DoesNotExist:
        return fail('成员不存在', 404)
    if target.role != 'member' and me.role != 'teacher':
        return fail('负责人只能重置普通成员的密码', 403)
    # 随机强密码：不包含易混字符
    import secrets
    alphabet = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789'
    new_pw = ''.join(secrets.choice(alphabet) for _ in range(12))
    while not (any(c.islower() for c in new_pw) and any(c.isupper() for c in new_pw) and any(c.isdigit() for c in new_pw)):
        new_pw = ''.join(secrets.choice(alphabet) for _ in range(12))
    target.user.set_password(new_pw)
    target.user.save()
    target.must_change_password = True
    target.save(update_fields=['must_change_password', 'updated'])
    target.user.is_active = True
    target.user.save()
    _log(request, target, f'重置成员密码 · {target.name}')
    return ok({'password': new_pw})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def login_logs(request):
    """登录日志（仅管理角色）：按成员/成功筛选，最近 200 条。"""
    me, e = _require_active(request)
    if e:
        return e
    if not is_staff(request.user):
        return fail('仅管理角色可查看登录日志', 403)
    from apps.accounts.models import LoginLog
    qs = LoginLog.objects.select_related('user').order_by('-at')[:200]
    out = []
    for lg in qs:
        prof = getattr(lg.user, 'member_profile', None)
        out.append({
            'id': lg.pk,
            'memberId': member_id(lg.user_id) if prof else '',
            'name': prof.name if prof else lg.user.username,
            'ip': lg.ip or '',
            'ua': lg.user_agent,
            'success': lg.success,
            'at': lg.at,
        })
    return ok(out)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_csv(request, kind):
    """数据导出 CSV：members/loans/tasks/checkins/logs。仅管理角色。"""
    me, e = _require_active(request)
    if e:
        return e
    if (err := require(request.user, 'action:export.csv', '没有导出数据权限')):
        return err
    import csv
    from django.http import HttpResponse
    from django.utils import timezone
    from apps.inventory.models import Loan
    from apps.tasksapp.models import Task
    from apps.checkins.models import CheckInRecord
    from apps.accounts.models import LoginLog

    resp = HttpResponse(content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename="{kind}_{timezone.now():%Y%m%d_%H%M}.csv"'
    w = csv.writer(resp)

    def member_name(uid):
        u = User.objects.filter(pk=uid).first()
        return getattr(getattr(u, 'member_profile', None), 'name', u.username if u else '')

    if kind == 'members':
        w.writerow(['姓名', '学号/工号', '角色', '小组', '邮箱', '联系方式', '状态', '加入时间'])
        for mp in MemberProfile.objects.select_related('user').all():
            w.writerow([mp.name, mp.number, mp.role, mp.group, mp.email, mp.contact,
                        '在籍' if mp.active else '停用', mp.joined])
    elif kind == 'loans':
        w.writerow(['借用单号', '借用人', '模块', '用途', '状态', '借出时间', '应还时间', '归还时间'])
        for l in Loan.objects.prefetch_related('items').all():
            w.writerow([l.id, member_name(l.member_id),
                        ' / '.join(l.items.values_list('asset_id', flat=True)),
                        l.purpose, l.status, l.issued, l.due, l.received])
    elif kind == 'tasks':
        w.writerow(['任务编号', '标题', '状态', '优先级', '负责人', '截止时间', '创建时间'])
        for t in Task.objects.all():
            w.writerow([t.id, t.title, t.status, t.priority, member_name(t.assignee_id), t.due, t.created])
    elif kind == 'checkins':
        w.writerow(['姓名', '打卡时间', '纬度', '经度'])
        for c in CheckInRecord.objects.select_related('user').all():
            w.writerow([member_name(c.user_id), c.created, c.latitude, c.longitude])
    elif kind == 'logs':
        w.writerow(['操作人', '对象', '内容', '时间'])
        for lg in OperationLog.objects.select_related('actor', 'member').order_by('-at')[:1000]:
            w.writerow([lg.actor.username if lg.actor else '', lg.member.name if lg.member else '', lg.text, lg.at])
    else:
        return fail('不支持的导出类型', 404)
    return resp


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def members_active(request, mid):
    me, e = _require_active(request)
    if e:
        return e
    if (err := require(request.user, 'action:member.active', '没有停用/启用成员的权限')):
        return err

    target_id = parse_member_id(mid)
    if not target_id:
        return fail('成员不存在', 404)
    try:
        target = MemberProfile.objects.select_related('user').get(user_id=target_id)
    except MemberProfile.DoesNotExist:
        return fail('成员不存在', 404)
    if target.user_id == request.user.pk:
        return fail('不能停用/启用自己的账号')

    d = request.data or {}
    active = bool(d.get('active'))
    if target.role != 'member' and me.role != 'teacher':
        return fail('负责人只能停用/启用普通成员', 403)

    if not active:
        from apps.inventory.api import has_open_items
        from apps.leaves.api import has_pending_leave
        if has_open_items(target):
            return fail('该成员尚有未完成借用，不能停用', 409)
        if has_pending_leave(target):
            return fail('该成员有待审批请假，请先处理', 409)

    target.active = active
    target.save()
    target.user.is_active = active
    target.user.save()
    action = '启用' if active else '停用'
    _log(request, target, f'{action}成员账号 · {target.name}')
    return ok()


# ─────────────────── 权限管理（RBAC）───────────────────


def _superadmin_required(request):
    """仅系统管理员可操作。返回 error 或 None。"""
    from apps.common.rbac import is_superadmin_user
    if not is_superadmin_user(request.user):
        return fail('仅系统管理员可执行此操作', 403)
    return None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def permissions_meta(request):
    """权限矩阵元数据：权限点(分组) + 全部角色 + 当前用户权限维护可用性。"""
    from apps.common.rbac import can as rbac_can, is_superadmin_user
    from apps.accounts.rbac_defs import PERMISSION_POINTS, PERMISSION_GROUPS

    def point_label(key):
        for (k, label, _) in PERMISSION_POINTS:
            if k == key:
                return label
        return key

    groups = []
    for (gname, keys) in PERMISSION_GROUPS:
        groups.append({
            'name': gname,
            'points': [{'key': k, 'label': point_label(k)} for k in keys],
        })

    roles = []
    for r in Role.objects.all():
        roles.append({
            'code': r.code, 'name': r.name,
            'builtin': r.builtin, 'superadmin': r.superadmin,
            # superadmin 角色不落权限数组，返回全量示意
            'permissions': sorted(r.permissions) if r.superadmin else sorted(r.permissions),
        })

    return ok({
        'groups': groups,
        'roles': roles,
        'isSuperadmin': is_superadmin_user(request.user),
        'canEditRoles': rbac_can(request.user, 'action:manage.roles'),
        'canEditMatrix': rbac_can(request.user, 'action:manage.permissions'),
        'canOverride': rbac_can(request.user, 'action:manage.override'),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def roles_create(request):
    err = _superadmin_required(request) or require(request.user, 'action:manage.roles', '仅系统管理员可创建角色')
    if err:
        return err
    d = request.data or {}
    code = str(d.get('code', '')).strip().lower()
    name = str(d.get('name', '')).strip()
    if not code or not name:
        return fail('请填写角色编码和名称')
    if not re.match(r'^[a-z][a-z0-9_]{1,30}$', code):
        return fail('编码须为小写字母开头，2-31 位字母/数字/下划线')
    if Role.objects.filter(code=code).exists():
        return fail('角色编码已存在')
    Role.objects.create(code=code, name=name, builtin=False, superadmin=False, permissions=[])
    return ok({'code': code})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def roles_rename(request, code):
    err = _superadmin_required(request) or require(request.user, 'action:manage.roles')
    if err:
        return err
    role = Role.objects.filter(code=code).first()
    if not role:
        return fail('角色不存在', 404)
    if role.builtin:
        return fail('内置角色不可重命名', 400)
    name = str((request.data or {}).get('name', '')).strip()
    if not name:
        return fail('请填写角色名称')
    role.name = name
    role.save()
    return ok({'code': role.code, 'name': role.name})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def roles_delete(request, code):
    err = _superadmin_required(request) or require(request.user, 'action:manage.roles')
    if err:
        return err
    if code in ('teacher', 'manager', 'member', 'superadmin'):
        return fail('内置角色不可删除', 400)
    role = Role.objects.filter(code=code).first()
    if not role:
        return fail('角色不存在', 404)
    member_count = role.members.count()
    if member_count:
        return fail(f'仍有 {member_count} 位成员使用该角色，请先改派', 409)
    role.delete()
    return ok()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def roles_grant(request, code):
    err = _superadmin_required(request) or require(request.user, 'action:manage.permissions')
    if err:
        return err
    role = Role.objects.filter(code=code).first()
    if not role:
        return fail('角色不存在', 404)
    if role.superadmin:
        return fail('系统管理员无需配置权限，默认为全量', 400)
    keys = list(dict.fromkeys(str(k) for k in (request.data or {}).get('permissions') or []))
    from apps.accounts.rbac_defs import ALL_KEYS
    invalid = [k for k in keys if k not in ALL_KEYS]
    if invalid:
        return fail(f'包含未知权限点: {invalid[:3]}')
    role.permissions = sorted(keys)
    role.save()
    return ok({'code': role.code, 'count': len(keys)})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def member_override_get(request, mid):
    err = _superadmin_required(request) or require(request.user, 'action:manage.override')
    if err:
        return err
    target_id = parse_member_id(mid)
    if not target_id:
        return fail('成员不存在', 404)
    try:
        target = MemberProfile.objects.select_related('user').get(user_id=target_id)
    except MemberProfile.DoesNotExist:
        return fail('成员不存在', 404)
    return ok({
        'mid': mid,
        'allowed': target.permission_overrides.get('allow') or [],
        'denied': target.permission_overrides.get('deny') or [],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def member_override_set(request, mid):
    err = _superadmin_required(request) or require(request.user, 'action:manage.override')
    if err:
        return err
    target_id = parse_member_id(mid)
    if not target_id:
        return fail('成员不存在', 404)
    try:
        target = MemberProfile.objects.select_related('user').get(user_id=target_id)
    except MemberProfile.DoesNotExist:
        return fail('成员不存在', 404)
    from apps.accounts.rbac_defs import ALL_KEYS
    d = request.data or {}
    allowed = list(dict.fromkeys(str(k) for k in d.get('allowed') or []))
    denied = list(dict.fromkeys(str(k) for k in d.get('denied') or []))
    if any(k not in ALL_KEYS for k in allowed + denied):
        return fail('包含未知权限点')
    target.permission_overrides = {'allow': sorted(allowed), 'deny': sorted(denied)}
    target.save(update_fields=['permission_overrides', 'updated'])
    return ok()


# ─────────────────── 小组管理 ───────────────────


def _group_dict(g):
    leader = g.leader.member_profile.name if g.leader and hasattr(g.leader, 'member_profile') else (g.leader.username if g.leader else '')
    members = [member_id(m.user_id) for m in g.members.all()]
    return {
        'id': g.id, 'name': g.name,
        'leaderId': member_id(g.leader_id) if g.leader_id else '',
        'leaderName': leader,
        'capacity': g.capacity,
        'note': g.note,
        'members': members,
        'memberCount': len(members),
        'created': g.created,
    }


def workspace_groups(profile, staff):
    groups = [_group_dict(g) for g in LabGroup.objects.prefetch_related('members').all()]
    return {'groups': groups}


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def groups_list(request):
    return ok(workspace_groups(None, False)['groups'])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def groups_create(request):
    me, e = _require_active(request)
    if e:
        return e
    if (err := require(request.user, 'action:group.manage', '没有创建小组的权限')):
        return err
    d = request.data or {}
    name = str(d.get('name', '')).strip()
    if not name:
        return fail('请填写小组名称')
    if LabGroup.objects.filter(name__iexact=name).exists():
        return fail('小组名称已存在')
    capacity = d.get('capacity', 20)
    try:
        capacity = max(1, min(int(capacity), 200))
    except (TypeError, ValueError):
        capacity = 20
    leader_id = parse_member_id(str(d.get('leaderId', '')) or '')
    leader = None
    if leader_id:
        leader = User.objects.filter(pk=leader_id).first()
        if not leader:
            return fail('队长不存在', 404)
    g = LabGroup.objects.create(
        id=next_code(LabGroup, 'G'), name=name, leader=leader,
        capacity=capacity, note=str(d.get('note', '')).strip()[:256])
    _log(request, me, f'创建小组 · {g.name}')
    return ok({'id': g.id})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def groups_update(request, gid):
    me, e = _require_active(request)
    if e:
        return e
    if (err := require(request.user, 'action:group.manage', '没有管理小组的权限')):
        return err
    g = LabGroup.objects.filter(pk=gid).first()
    if not g:
        return fail('小组不存在', 404)
    d = request.data or {}
    if 'name' in d and str(d.get('name', '')).strip():
        new_name = str(d.get('name')).strip()
        if LabGroup.objects.filter(name__iexact=new_name).exclude(pk=gid).exists():
            return fail('小组名称已存在')
        g.name = new_name
    if 'leaderId' in d:
        leader_id = parse_member_id(str(d.get('leaderId', '')) or '')
        g.leader = User.objects.filter(pk=leader_id).first() if leader_id else None
    if 'capacity' in d:
        try:
            g.capacity = max(1, min(int(d.get('capacity')), 200))
        except (TypeError, ValueError):
            pass
    if 'note' in d:
        g.note = str(d.get('note', '')).strip()[:256]
    g.save()
    _log(request, me, f'更新小组 · {g.name}')
    return ok({'id': g.id})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def groups_delete(request, gid):
    me, e = _require_active(request)
    if e:
        return e
    if (err := require(request.user, 'action:group.manage', '没有删除小组的权限')):
        return err
    g = LabGroup.objects.filter(pk=gid).first()
    if not g:
        return fail('小组不存在', 404)
    # 解除成员归属后再删组
    g.members.update(group_fk=None)
    g.delete()
    _log(request, me, f'删除小组 · {g.name}')
    return ok()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def groups_members(request, gid):
    """成员调配：{memberIds:[m1,...]} 替换归属（同一成员只能在一个小组）。"""
    me, e = _require_active(request)
    if e:
        return e
    if (err := require(request.user, 'action:group.members', '没有调配小组成员的权限')):
        return err
    g = LabGroup.objects.filter(pk=gid).first()
    if not g:
        return fail('小组不存在', 404)
    mids = (request.data or {}).get('memberIds') or []
    ids = [parse_member_id(str(m)) for m in mids]
    if any(i is None for i in ids):
        return fail('包含非法成员')
    if len(ids) > g.capacity:
        return fail(f'超出小组人数上限（{g.capacity} 人）', 409)
    MemberProfile.objects.filter(group_fk=g).update(group_fk=None)
    MemberProfile.objects.filter(user_id__in=ids).update(group_fk=g)
    # 同步文本字段 group
    for prof in MemberProfile.objects.filter(group_fk=g):
        if prof.group != g.name:
            prof.group = g.name
            prof.save(update_fields=['group'])
    _log(request, me, f'调整小组「{g.name}」成员')
    return ok({'id': g.id})


# ─────────────────── 动态导航（NavItem）───────────────────


def nav_items(profile):
    """按当前用户权限过滤后的导航/路由列表（后端动态下发）。"""
    from apps.accounts.models import NavItem
    from apps.common.rbac import effective_permissions

    perms = effective_permissions(profile)
    out = []
    for item in NavItem.objects.filter(enabled=True).order_by('order', 'id'):
        if item.permission and item.permission not in perms:
            continue
        out.append({'id': item.id, 'label': item.label, 'icon': item.icon,
                    'permission': item.permission, 'param': item.param})
    return out


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def nav_admin_get(request):
    """导航全量（superadmin：含禁用与排序，供管理配置）。"""
    me, e = _require_active(request)
    if e:
        return e
    if not _is_superadmin(request.user):
        return fail('仅系统管理员可配置导航', 403)
    from apps.accounts.models import NavItem
    return ok([{'id': i.id, 'label': i.label, 'icon': i.icon, 'permission': i.permission,
                'param': i.param, 'enabled': i.enabled, 'order': i.order}
               for i in NavItem.objects.all().order_by('order', 'id')])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def nav_admin_save(request):
    """全量保存：upsert 列表中的项，未列出的保持原样；enabled=False 即隐藏。"""
    me, e = _require_active(request)
    if e:
        return e
    if not _is_superadmin(request.user):
        return fail('仅系统管理员可配置导航', 403)
    from apps.accounts.models import NavItem

    items = (request.data or {}).get('items') or []
    seen = set()
    for i, d in enumerate(items, start=1):
        rid = str(d.get('id', '')).strip()[:32]
        if not rid or rid in seen:
            continue
        seen.add(rid)
        item, created = NavItem.objects.get_or_create(pk=rid)
        item.label = str(d.get('label', item.label)).strip()[:32] or item.id
        item.icon = str(d.get('icon', item.icon)).strip()[:32]
        item.permission = str(d.get('permission', item.permission)).strip()[:64]
        item.param = str(d.get('param', item.param)).strip()[:32]
        item.enabled = bool(d.get('enabled', item.enabled))
        item.order = i
        item.save()
    _log(request, me, '更新导航菜单配置')
    return ok({'count': len(seen)})


def _is_superadmin(user):
    from apps.common.rbac import is_superadmin_user
    return is_superadmin_user(user)


# ─────────────────── 跨平台只读 API Token（/openapi）───────────────────


def _require_token_scope(request, scope):
    """openapi 只读端点：必须用令牌认证且令牌带对应 scope。"""
    tok = getattr(request, 'auth', None)
    from apps.accounts.models import ApiToken
    if not isinstance(tok, ApiToken):
        return fail('需要 API 令牌访问', 403)
    if scope not in (tok.scopes or []):
        return fail('令牌无权访问该接口', 403)
    return None


def _token_log(token, text):
    OperationLog.objects.create(
        actor=token.user, text=f'[令牌 {token.name}] {text}')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tokens_list(request):
    if (err := require(request.user, 'action:token.manage', '没有管理令牌的权限')):
        return err
    from apps.accounts.models import ApiToken
    return ok([{'id': t.pk, 'name': t.name, 'scopes': t.scopes, 'active': t.active,
                'expiresAt': t.expires_at, 'lastUsedAt': t.last_used_at, 'created': t.created}
               for t in ApiToken.objects.filter(user=request.user)])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def tokens_create(request):
    if (err := require(request.user, 'action:token.manage', '没有创建令牌的权限')):
        return err
    import secrets
    from datetime import timedelta
    from hashlib import sha256

    from django.utils import timezone
    from apps.accounts.models import ApiToken

    d = request.data or {}
    name = str(d.get('name', '')).strip()[:64]
    if not name:
        return fail('请填写令牌名称')
    scopes = d.get('scopes') or ['read:assets', 'read:loans']
    if not isinstance(scopes, list) or any(s not in ('read:assets', 'read:loans', 'read:tasks') for s in scopes):
        return fail('范围不合法')
    raw = 'lab_' + secrets.token_urlsafe(24)
    token = ApiToken.objects.create(
        name=name, user=request.user,
        token_hash=sha256(raw.encode()).hexdigest(),
        scopes=scopes,
        expires_at=timezone.now() + timedelta(days=90))
    _log(request, get_member(request.user), f'创建 API 令牌 · {name}')
    # 生成一段可直接粘贴给 AI 的指令（内含令牌与调用方式），AI 读到即可查询实验室只读数据。
    from django.conf import settings
    base = request.build_absolute_uri('/api/') if settings.DEBUG else 'https://' + request.get_host() + '/api/'
    scope_map = {
        'read:assets': ('openapi/assets', '实验室硬件/模块清单（编号、名称、型号、类别、位置、状态、备注）'),
        'read:loans': ('openapi/loans', '借用记录清单'),
        'read:tasks': ('openapi/tasks', '任务清单'),
    }
    lines = [
        '你是「具身智能实验室」管理平台的只读数据助手。',
        '下面是一条 API 令牌，用它查询实验室的只读数据。',
        f'认证方式：请求头携带  Authorization: Bearer {raw}',
        f'令牌说明：{name} · 只读 · 默认 90 天内有效 · 请勿泄露，也不要用于任何写操作。',
        '',
        '可用接口（按授权范围）：',
    ]
    for s in scopes:
        path, desc = scope_map.get(s, ('', ''))
        if path:
            lines.append(f'- GET {base}{path}  →  {desc}')
    lines += [
        '',
        '示例：',
        f'curl -s -H "Authorization: Bearer {raw}" "{base}openapi/assets"',
        '',
        '当用户询问「实验室有什么硬件 / 有哪些设备 / 调取硬件清单」时，',
        '调用硬件接口并把返回结果整理成简洁的中文回答。',
    ]
    ai_instruction = '\n'.join(lines)
    return ok({'id': token.pk, 'token': raw, 'expiresAt': token.expires_at,
               'note': '令牌明文仅此一次展示，请立即保存',
               'aiInstruction': ai_instruction})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def tokens_revoke(request, tid):
    if (err := require(request.user, 'action:token.manage', '没有吊销令牌的权限')):
        return err
    from apps.accounts.models import ApiToken
    token = ApiToken.objects.filter(pk=tid, user=request.user).first()
    if not token:
        return fail('令牌不存在', 404)
    token.active = False
    token.save(update_fields=['active'])
    _log(request, get_member(request.user), f'吊销 API 令牌 · {token.name}')
    return ok()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def openapi_assets(request):
    if (err := _require_token_scope(request, 'read:assets')):
        return err
    from apps.inventory.models import Asset
    out = []
    for a in Asset.objects.all():
        status = '使用中' if a.status == Asset.STATUS_IN_USE else a.status
        out.append({'编号': a.id, '名称': a.name, '型号': a.model, '类别': a.category,
                    '位置': a.location, '状态': status, '备注': a.note})
    _token_log(request.auth, f'只读查询模块清单 {len(out)} 条')
    return ok(out)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def openapi_loans(request):
    if (err := _require_token_scope(request, 'read:loans')):
        return err
    from apps.inventory.models import Loan
    out = []
    for l in Loan.objects.prefetch_related('items'):
        out.append({'单号': l.id, '借用人': l.member.member_profile.name if l.member and hasattr(l.member, 'member_profile') else '',
                    '状态': l.status, '预计归还': l.due,
                    '模块': [li.asset_id for li in l.items.all()]})
    _token_log(request.auth, f'只读查询借用清单 {len(out)} 条')
    return ok(out)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def openapi_tasks(request):
    if (err := _require_token_scope(request, 'read:tasks')):
        return err
    from apps.tasksapp.models import Task
    out = [{'编号': t.id, '标题': t.title, '状态': t.status, '优先级': t.priority,
            '负责人': t.assignee.member_profile.name if t.assignee and hasattr(t.assignee, 'member_profile') else ''}
           for t in Task.objects.all()[:100]]
    _token_log(request.auth, f'只读查询任务清单 {len(out)} 条')
    return ok(out)
