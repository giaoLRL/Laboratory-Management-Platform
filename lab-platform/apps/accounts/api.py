import re

from django.contrib.auth import authenticate, login as dj_login, logout as dj_logout
from django.contrib.auth.models import User
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import MemberProfile, OperationLog
from apps.accounts.serializers import member_dict, log_dict
from apps.common.ids import member_id, parse_member_id
from apps.common.permissions import get_member, is_staff
from apps.common.response import ok, fail
from apps.common.workspace import build_workspace

USERNAME_RE = re.compile(r'^\w{3,30}$')
PASSWORD_OK = re.compile(r'^(?=.*[A-Za-z])(?=.*\d).{8,64}$')


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


@api_view(['POST'])
@permission_classes([])
def auth_login(request):
    d = request.data or {}
    username = str(d.get('username', '')).strip()
    password = str(d.get('password', ''))
    user = authenticate(request, username=username, password=password)
    if user is None:
        return fail('账号或密码不正确', 401)
    prof = getattr(user, 'member_profile', None)
    if prof is None:
        return fail('账号未关联成员档案', 403)
    if not prof.active:
        return fail('账号已停用，请联系负责人', 403)
    dj_login(request, user)
    _log(request, prof, f'{prof.name} 登录系统')
    return ok({'id': member_id(user.pk)})


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
    if not is_staff(request.user):
        return fail('只有指导老师或负责人可以创建成员账号', 403)

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

    user = User.objects.create_user(username=username, password=password)
    prof = MemberProfile.objects.create(
        user=user, name=name, number=number, role=role,
        group=group, direction=direction, contact=contact)
    _log(request, prof, f'创建成员账号 · {name}')
    return ok({'id': member_id(user.pk)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def members_update(request, mid):
    me, e = _require_active(request)
    if e:
        return e
    if not is_staff(request.user):
        return fail('只有指导老师或负责人可以修改成员资料', 403)

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
    role = str(d.get('role', target.role)).strip()

    if role not in ('teacher', 'manager', 'member'):
        return fail('角色不合法')
    if me.role == 'manager':
        role = 'member'  # 负责人不能修改角色
    if target.user_id == request.user.pk and role != me.role:
        return fail('不能修改自己的角色')
    if number != target.number and MemberProfile.objects.filter(number=number).exclude(pk=target.pk).exists():
        return fail('学号/工号已存在')
    if username.lower() != target.user.username.lower() and \
            User.objects.filter(username__iexact=username).exclude(pk=target.user_id).exists():
        return fail('登录账号已存在（不区分大小写）')

    target.name, target.number = name, number
    target.group, target.direction, target.contact = group, direction, contact
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
    direction = str(d.get('direction', p.direction)).strip()
    contact = str(d.get('contact', p.contact)).strip()
    if name:
        p.name = name
    p.direction = direction
    p.contact = contact
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
def members_active(request, mid):
    me, e = _require_active(request)
    if e:
        return e
    if not is_staff(request.user):
        return fail('只有指导老师或负责人可以停用/启用成员', 403)

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
