from django.db import IntegrityError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import MemberProfile
from apps.common.ids import parse_member_id
from apps.common.response import ok, fail
from apps.notify.models import Announcement, AnnouncementRead

MAX_CONTENT = 20000


def _announcement_dict(a, viewer_id=None):
    read = bool(viewer_id and AnnouncementRead.objects.filter(announcement=a, user_id=viewer_id).exists())
    return {
        'id': a.id,
        'title': a.title,
        'content': a.content,
        'author': a.author.member_profile.name if a.author and hasattr(a.author, 'member_profile') else (a.author.username if a.author else '系统'),
        'pinned': a.pinned,
        'scope': a.scope,
        'active': a.active,
        'created': a.created,
        'updated': a.updated,
        'read': read,
    }


def workspace_slice(profile, staff):
    """当前用户可见公告 + 未读数 + 最近通知/未读数。"""
    from apps.notify.models import visible_announcements, Notification
    items = visible_announcements(profile, staff)
    unread = sum(1 for a in items if not AnnouncementRead.objects.filter(announcement=a, user=profile.user).exists())
    recent = Notification.objects.filter(recipient=profile.user)[:10]
    unread_n = Notification.objects.filter(recipient=profile.user, read=False).count()
    ts = [a.updated for a in items[:50]] + [n.created for n in recent]
    return {
        'announcements': [_announcement_dict(a, profile.user_id) for a in items[:50]],
        'unread_announcements': unread,
        'notifications': [_notification_dict(n) for n in recent],
        'unread_notifications': unread_n,
        '_ts': ts,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def announcements_list(request):
    from apps.accounts.models import MemberProfile
    profile = MemberProfile.objects.filter(user=request.user).first()
    staff = profile.role in ('teacher', 'manager') if profile else False
    slice_data = workspace_slice(profile, staff)
    return ok({'announcements': slice_data['announcements'], 'unread': slice_data['unread_announcements']})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def announcements_create(request):
    from apps.common.rbac import require
    if (err := require(request.user, 'action:announcement.create', '没有发布公告的权限')):
        return err
    d = request.data or {}
    title = str(d.get('title', '')).strip()
    content = str(d.get('content', '')).strip()
    if not title:
        return fail('请填写公告标题')
    if not content:
        return fail('请填写公告内容')
    if len(content) > MAX_CONTENT:
        return fail(f'公告内容过长（最多 {MAX_CONTENT} 字）')
    scope = str(d.get('scope', 'all'))
    if scope not in ('all', 'group', 'members'):
        return fail('范围不合法')
    group_id = str(d.get('groupId', '')).strip() if scope == 'group' else None
    member_mids = d.get('memberIds') or [] if scope == 'members' else []
    from apps.accounts.models import LabGroup
    from apps.common.ids import parse_member_id
    group = None
    if scope == 'group':
        group = LabGroup.objects.filter(pk=group_id).first()
        if not group:
            return fail('指定的小组不存在', 404)
    member_ids = []
    if scope == 'members':
        for mid in member_mids:
            uid = parse_member_id(mid)
            if not uid:
                return fail(f'成员 {mid} 不存在')
            member_ids.append(uid)
    a = Announcement.objects.create(
        id=Announcement.next_id(), title=title, content=content,
        author=request.user, pinned=bool(d.get('pinned')), scope=scope,
        group=group, member_ids=member_ids, active=True)
    _log_announcement(request, f'发布公告 · {a.title}')
    from apps.notify.service import create_many
    targets = _notification_targets(a)
    create_many(targets, 'announcement_published', f'新公告 · {a.title}',
                content[:200], ref_type='announcement', ref_id=a.id, link='announcements')
    return ok({'id': a.id})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def announcements_update(request, aid):
    from apps.common.rbac import require
    if (err := require(request.user, 'action:announcement.update', '没有编辑公告的权限')):
        return err
    a = Announcement.objects.filter(pk=aid).first()
    if not a:
        return fail('公告不存在', 404)
    d = request.data or {}
    if 'title' in d:
        a.title = str(d.get('title', '')).strip() or a.title
    if 'content' in d:
        a.content = str(d.get('content', '')).strip()
        if len(a.content) > MAX_CONTENT:
            return fail('公告内容过长')
    if 'pinned' in d:
        a.pinned = bool(d.get('pinned'))
    if 'active' in d:
        a.active = bool(d.get('active'))
    a.save()
    _log_announcement(request, f'更新公告 · {a.title}')
    return ok()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def announcements_read(request, aid):
    a = Announcement.objects.filter(pk=aid).first()
    if not a:
        return fail('公告不存在', 404)
    AnnouncementRead.objects.get_or_create(announcement=a, user=request.user)
    return ok()


def _log_announcement(request, text):
    from apps.accounts.models import OperationLog
    prof = getattr(request.user, 'member_profile', None)
    OperationLog.objects.create(
        actor=request.user if request.user.is_authenticated else None,
        member=prof, text=str(text)[:256])


# ─────────────────── 实时动态（NewsItem）───────────────────


def _news_dict(n):
    return {'id': n.id, 'title': n.title, 'source': n.source, 'url': n.url,
            'summary': n.summary, 'publishedAt': n.published_at,
            'fetchSource': n.fetch_source}


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def news_list(request):
    """动态列表（快照外单独分页，最多 100 条）。"""
    from apps.notify.models import NewsItem
    return ok([_news_dict(n) for n in NewsItem.objects.all()[:100]])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def news_create(request):
    from apps.common.rbac import require
    if (err := require(request.user, 'action:news.manage', '没有录入动态的权限')):
        return err
    from django.utils.dateparse import parse_datetime
    from apps.notify.models import NewsItem

    d = request.data or {}
    title = str(d.get('title', '')).strip()
    if not title:
        return fail('请填写标题')
    published = parse_datetime(str(d.get('publishedAt', ''))) if d.get('publishedAt') else None
    if published is None:
        from django.utils import timezone
        published = timezone.now()
    item = NewsItem.objects.create(
        id=NewsItem.next_id(), title=title[:256],
        source=str(d.get('source', '')).strip()[:128],
        url=str(d.get('url', '')).strip()[:512],
        summary=str(d.get('summary', '')).strip()[:2000],
        published_at=published, fetch_source=NewsItem.FETCH_MANUAL)
    return ok({'id': item.id})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def news_delete(request, nid):
    from apps.common.rbac import require
    if (err := require(request.user, 'action:news.manage', '没有删除动态的权限')):
        return err
    from apps.notify.models import NewsItem
    item = NewsItem.objects.filter(pk=nid).first()
    if not item:
        return fail('动态不存在', 404)
    item.delete()
    return ok()


# ─────────────────── 站内通知（Notification）───────────────────


def _notification_dict(n):
    return {'id': n.id, 'kind': n.kind, 'title': n.title, 'body': n.body,
            'refType': n.ref_type, 'refId': n.ref_id, 'link': n.link,
            'read': n.read, 'created': n.created}


def _notification_targets(a):
    """公告发布通知的接收者（按 scope 展开，排除发布人）。"""
    from apps.accounts.models import MemberProfile, LabGroup
    from apps.common.ids import parse_member_id
    from apps.notify.service import active_members
    if a.scope == Announcement.SCOPE_ALL:
        return active_members(exclude=a.author)
    if a.scope == Announcement.SCOPE_GROUP and a.group:
        mids = list(a.group.members.values_list('user_id', flat=True))
        return [u for u in MemberProfile.objects.filter(user_id__in=mids, active=True).select_related('user')]
    if a.scope == Announcement.SCOPE_MEMBERS:
        ids = [parse_member_id(m) for m in (a.member_ids or [])]
        ids = [i for i in ids if i]
        return [p.user for p in MemberProfile.objects.filter(user_id__in=ids, active=True).select_related('user')]
    return []


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notifications_list(request):
    """本人通知列表：分页 + 类型筛选（type 按 kind 前缀匹配）。"""
    from apps.notify.models import Notification
    qs = Notification.objects.filter(recipient=request.user)
    ntype = str(request.query_params.get('type', '')).strip()
    if ntype and ntype != 'all':
        qs = qs.filter(kind__startswith=ntype)
    total = qs.count()
    try:
        page = max(1, int(request.query_params.get('page', 1)))
        size = min(50, max(1, int(request.query_params.get('pageSize', 20))))
    except (TypeError, ValueError):
        page, size = 1, 20
    items = list(qs.order_by('-created', '-read')[ (page - 1) * size : page * size ])
    unread = qs.filter(read=False).count()
    return ok({'items': [_notification_dict(n) for n in items], 'total': total,
               'page': page, 'pageSize': size, 'unread': unread})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def notifications_read(request, nid):
    from apps.notify.models import Notification
    n = Notification.objects.filter(pk=nid, recipient=request.user).first()
    if not n:
        return fail('通知不存在', 404)
    if not n.read:
        n.read = True
        from django.utils import timezone
        n.read_at = timezone.now()
        n.save(update_fields=['read', 'read_at'])
    return ok()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def notifications_read_all(request):
    from apps.notify.models import Notification
    from django.utils import timezone
    Notification.objects.filter(recipient=request.user, read=False).update(read=True, read_at=timezone.now())
    return ok()