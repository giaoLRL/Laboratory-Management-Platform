"""站内通知生成服务：业务写操作与 send_reminders 统一调用。

幂等：Notification 有 (recipient, kind, ref_type, ref_id) 唯一约束 + get_or_create，
send_reminders 每 30 分钟扫描也不会重复生成。
"""
from django.db import IntegrityError

from apps.notify.models import Notification


def create(to, kind, title, body='', ref_type='', ref_id='', link=''):
    """给单个用户生成一条通知。返回 (obj|None, created)。

    ref_type/ref_id 传空则不去重（每次都新建）。
    """
    if not to:
        return None, False
    try:
        n, created = Notification.objects.get_or_create(
            recipient=to, kind=kind, ref_type=ref_type or '', ref_id=str(ref_id or ''),
            defaults={'id': Notification.next_id(), 'title': str(title)[:128],
                      'body': str(body)[:2000], 'link': link or ''})
    except IntegrityError:
        return None, False
    return n, created


def create_many(users, kind, title, body='', ref_type='', ref_id='', link=''):
    """给一组用户逐个生成（逐个 get_or_create 保证幂等）。"""
    for u in users:
        if u:
            create(u, kind, title, body, ref_type, ref_id, link)


def managers_with(perm_key):
    """有指定权限点的在职成员 User 列表（实验室规模小，逐条 can() 可接受）。"""
    from apps.accounts.models import MemberProfile
    from apps.common.rbac import can
    return [p.user for p in MemberProfile.objects.filter(active=True).select_related('user')
            if p.user_id and can(p.user, perm_key)]


def active_members(exclude=None):
    """全部在职成员 User 列表（可排除某人）。"""
    from apps.accounts.models import MemberProfile
    exclude_ids = {getattr(exclude, 'id', None)}
    return [p.user for p in MemberProfile.objects.filter(active=True).select_related('user')
            if p.user_id and p.user_id not in exclude_ids]
