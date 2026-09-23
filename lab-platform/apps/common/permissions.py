from rest_framework.permissions import BasePermission


def get_member(user):
    """返回活跃成员档案；未登录 / 未建档 / 已停用返回 None。"""
    if not user or not user.is_authenticated:
        return None
    prof = getattr(user, 'member_profile', None)
    if prof is None or not prof.active:
        return None
    return prof


def is_staff(user):
    """管理能力：指导老师或负责人，或 superadmin。委托 RBAC can_manage（懒加载避免循环导入）。"""
    from apps.common.rbac import can_manage
    return can_manage(user)


class IsAuthenticatedMember(BasePermission):
    message = '需要实验室成员身份'

    def has_permission(self, request, view):
        return get_member(request.user) is not None


class IsTeacherOrManager(BasePermission):
    message = '需要指导老师或负责人权限'

    def has_permission(self, request, view):
        return is_staff(request.user)


class IsTeacher(BasePermission):
    message = '需要指导老师权限'

    def has_permission(self, request, view):
        m = get_member(request.user)
        return bool(m and m.role == 'teacher')
