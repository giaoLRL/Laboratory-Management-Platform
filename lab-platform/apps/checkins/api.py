from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.checkins import codes
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


def _coord(raw, lo, hi):
    """可选坐标：没传返回 None；传了但不合法抛 ValueError。"""
    value = (raw or '').strip()
    if not value:
        return None
    number = float(value)
    if not lo <= number <= hi:
        raise ValueError
    return number


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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def checkins_code(request):
    """当前签到码 + 二维码（管理角色在实验室屏幕上展示用）。"""
    if (err := require(request.user, 'action:checkin.qrcode', '没有展示签到二维码的权限')):
        return err
    info = codes.current()
    url = request.build_absolute_uri('/') + f'?c={info["code"]}#checkins'
    resp = ok({**info, 'url': url, 'qr': _qr_data_uri(url)})
    resp['Cache-Control'] = 'no-store'
    return resp


def _qr_data_uri(text):
    """签到码二维码：SVG data URI，前端用 <img> 展示（不经 innerHTML）。"""
    import segno
    return segno.make(text, error='m').svg_data_uri(scale=8, border=2)


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
    if not codes.verify(request.POST.get('code')):
        return fail('签到码无效或已过期，请扫描实验室屏幕上的最新二维码')
    try:
        lat = _coord(request.POST.get('latitude'), -90, 90)
        lng = _coord(request.POST.get('longitude'), -180, 180)
    except ValueError:
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
