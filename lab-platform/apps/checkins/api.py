from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.checkins.models import CheckInRecord
from apps.common.rbac import require
from apps.common.response import ok, fail


def _checkin_dict(c, with_photo=True):
    d = {'id': c.pk, 'memberId': f'm{c.user_id}', 'created': c.created,
         'latitude': c.latitude, 'longitude': c.longitude}
    if with_photo:
        d['photo'] = c.photo.url
    return d


def workspace_slice(profile, staff):
    """成员看自己的打卡记录；管理角色可看全部。"""
    qs = CheckInRecord.objects.all() if staff else CheckInRecord.objects.filter(user=profile.user)
    out, ts = [], []
    for c in qs[:200]:
        out.append(_checkin_dict(c, with_photo=(staff or c.user_id == profile.user_id)))
        ts.append(c.created)
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
