"""RBAC 授权解析器。

提供统一的"当前用户对某个权限点是否有权"判断，供各业务视图与 workspace 快照使用。
权限来源优先级：
  superadmin 角色 → 全量（不受权限矩阵限制）
  生效角色(roles) 的 permissions 并集（roles 为空时回退到 role 字段的内置角色）
  再叠加用户级 permission_overrides：deny 减、allow 加
"""

from apps.accounts.rbac_defs import ALL_KEYS, MANAGE_KEYS
from apps.common.permissions import get_member
from apps.common.response import fail


def is_superadmin(profile):
    if not profile:
        return False
    return any(getattr(r, 'superadmin', False) for r in profile.effective_roles())


def effective_permissions(profile):
    """返回当前档案的有效权限点 frozenset。superadmin 返回全量。"""
    if profile is None:
        return frozenset()
    if is_superadmin(profile):
        return frozenset(ALL_KEYS | {'*'})
    perms = set()
    for r in profile.effective_roles():
        perms.update(r.permissions or [])
    ov = profile.permission_overrides or {}
    perms.difference_update(ov.get('deny') or [])
    perms.update(ov.get('allow') or [])
    # 系统管理权限点不允许通过普通角色/覆盖获得，只在 superadmin 出现
    perms.difference_update(MANAGE_KEYS)
    return frozenset(perms)


def can(user, key):
    return bool(get_member(user) and key in effective_permissions(get_member(user)))


def require(user, key, msg='没有此操作权限'):
    """视图内用法：err = require(request.user, 'action:asset.create'); if err: return err"""
    if not can(user, key):
        return fail(msg, 403)
    return None


# 粗粒度"管理可见/越所有权"判定用到的 staff 级权限点集合
STAFF_TIER_KEYS = frozenset({
    'page:members', 'page:assets', 'page:permissions',
    'action:member.create', 'action:member.update', 'action:member.active',
    'action:asset.create', 'action:asset.update', 'action:asset.repair',
    'action:asset.repair_complete', 'action:asset.retire',
    'action:loan.review', 'action:loan.issue', 'action:loan.receive',
    'action:leave.review',
    'action:competition.create', 'action:competition.update', 'action:competition.archive',
    'action:manage.roles', 'action:manage.permissions', 'action:manage.override',
})


def can_manage(user):
    """粗粒度管理能力：superadmin、内置 teacher/manager，或持有任一 staff 级权限点。
    充当原 is_staff，用于数据可见性裁剪与"跳过所有权限制"。"""
    m = get_member(user)
    if not m:
        return False
    perms = effective_permissions(m)
    if '*' in perms:
        return True
    if m.role in ('teacher', 'manager'):
        return True
    return bool(STAFF_TIER_KEYS & perms)


def is_superadmin_user(user):
    return bool(get_member(user) and is_superadmin(get_member(user)))