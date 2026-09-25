from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.checkins.models import CheckInRecord
from apps.common.rbac import require
from apps.common.response import ok, fail


def _checkin_dict(c, with_photo=True):
    d = {'id': c.pk, 'memberId': f'm{c.user_id}', 'created': c.created,
         'latitude': c.latitude, 'longitude': c.longitude,
         'signoutAt': c.signout_at, 'onDuty': c.signout_at is None}
    if with_photo:
        d['photo'] = c.photo.url
    return d


def today_record(user):
    """今日打卡记录（没有则 None）。"""
    now = timezone.localtime()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return CheckInRecord.objects.filter(user=user, created__gte=day_start).order_by('-created').first()


def workspace_slice(profile, staff):
    """成员看自己的打卡记录；管理角色可看全部。"""
    qs = CheckInRecord.objects.all() if staff else CheckInRecord.objects.filter(user=profile.user)
    out, ts = [], []
    for c in qs.order_by('-created')[:200]:
        out.append(_checkin_dict(c, with_photo=(staff or c.user_id == profile.user_id)))
        ts.append(c.updated)
    return {'checkins': out, '_ts': ts}


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def checkins_create(request):
    if (err := require(request.user, 'action:checkin.create', '没有打卡的权限')):
        return err
    photo = request.FILES.get('photo')
    if not photo:
        return fail('打卡必须上传现场照片')
    if photo.size > 8 * 1024 * 1024:
        return fail('照片不能超过 8MB')
    try:
        lat = float(request.POST.get('latitude', ''))
        lng = float(request.POST.get('longitude', ''))
    except ValueError:
        return fail('请提供 GPS 定位信息')
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return fail('GPS 坐标不合法')

    now = timezone.localtime()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if CheckInRecord.objects.filter(user=request.user, created__gte=day_start).exists():
        return fail('今天已经打卡过了，明天再来', 409)

    rec = CheckInRecord.objects.create(user=request.user, photo=photo, latitude=lat, longitude=lng)
    # 每日打卡积分（重复打卡已被上面拦截，流水防重兜底）
    from apps.points.service import award
    awarded = award(request.user, 'checkin_daily', ref_type='checkin', ref_id=str(rec.pk), reason='实验室打卡')
    if awarded:
        from apps.accounts.models import OperationLog
        OperationLog.objects.create(actor=request.user, text=f'打卡发放积分 +{awarded.points}')
    return ok({'id': rec.pk, 'created': rec.created, 'photo': rec.photo.url})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def checkins_signout(request):
    """签退：座位上的人消失（同时清掉挪位记录，下次打卡回到默认座位）。"""
    if (err := require(request.user, 'action:checkin.create', '没有签退的权限')):
        return err
    rec = today_record(request.user)
    if not rec:
        return fail('今天还没有打卡，无需签退', 409)
    if rec.signout_at:
        return fail('今天已经签退过了', 409)

    rec.signout_at = timezone.now()
    rec.save(update_fields=['signout_at', 'updated'])
    from apps.seats.models import SeatPresence
    SeatPresence.objects.filter(member=request.user).delete()
    from apps.accounts.models import OperationLog
    OperationLog.objects.create(actor=request.user, text='打卡签退，离开实验室')
    return ok({'id': rec.pk, 'signoutAt': rec.signout_at})
