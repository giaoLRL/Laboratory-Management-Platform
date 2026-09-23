from django.utils import timezone


def award(user, rule_key, ref_type='', ref_id='', reason='', actor=None, points=None):
    """统一积分入口：规则未启用或重复发放（同 user+rule+ref）不写。

    points=None 时取规则的 unit 分值；传入则用给定值（如“星级 × 单位分值”）。
    返回发放的 PointRecord 或 None。写操作方统一由各业务视图补 OperationLog。
    """
    from apps.points.models import PointRecord, PointRule

    rule = PointRule.objects.filter(key=rule_key).first()
    amount = rule.points if points is None else points
    if not rule or not rule.enabled or amount <= 0:
        return None
    if ref_type and ref_id and PointRecord.objects.filter(
            user=user, rule_key=rule_key, ref_type=ref_type, ref_id=ref_id).exists():
        return None
    rec = PointRecord.objects.create(
        user=user, rule_key=rule_key, points=amount,
        ref_type=ref_type, ref_id=str(ref_id)[:64], reason=str(reason)[:256])
    from apps.notify.service import create
    create(user, 'points_changed', f'积分变动 +{amount}',
           reason or f'规则 {rule_key}', ref_type='points', ref_id=str(ref_id)[:64] or rec.pk,
           link='leaderboard')
    return rec


def user_total(user_id):
    from django.db.models import Sum
    from apps.points.models import PointRecord

    row = PointRecord.objects.filter(user_id=user_id).aggregate(t=Sum('points'))
    return row['t'] or 0


def totals_map():
    """全部成员总分映射 {user_id: total}。"""
    from django.db.models import Sum
    from apps.points.models import PointRecord

    out = {}
    for row in PointRecord.objects.values('user_id').annotate(t=Sum('points')):
        if row['t']:
            out[row['user_id']] = row['t']
    return out


def now():
    return timezone.now()