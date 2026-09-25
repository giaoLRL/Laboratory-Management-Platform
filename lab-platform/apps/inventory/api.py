from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import OperationLog
from apps.common.ids import create_with_code, next_code
from apps.common.permissions import get_member
from apps.common.rbac import can_manage, require
from apps.common.response import ok, fail
from apps.inventory.models import Asset, Loan, LoanItem, Maintenance

ACTIVE_LOAN_STATUSES = (Loan.STATUS_PENDING, Loan.STATUS_APPROVED,
                        Loan.STATUS_IN_USE, Loan.STATUS_RETURNING)
OPEN_ITEM_STATUSES = (Loan.STATUS_PENDING, Loan.STATUS_APPROVED,
                      Loan.STATUS_IN_USE, Loan.STATUS_RETURNING)


def _log(request, member, text):
    OperationLog.objects.create(
        actor=request.user if request.user.is_authenticated else None,
        member=member, text=str(text)[:256])


def _member_name(user):
    prof = getattr(user, 'member_profile', None)
    return prof.name if prof else (user.username if user else '')


def _loan_dict(l, viewer_id, staff):
    """普通成员看其他人的占用记录：仅返回资产编号、使用者、借还状态、预计归还时间。"""
    own = staff or l.member_id == viewer_id
    d = {
        'id': l.id,
        'memberId': f'm{l.member_id}',
        'assetIds': [li.asset_id for li in l.items.all()],
        'status': l.status,
        'created': l.created,
        'due': l.due,
    }
    if own:
        d.update({
            'purpose': l.purpose, 'project': l.project,
            'reviewer': f'm{l.reviewer_id}' if l.reviewer_id else '',
            'reviewed': l.reviewed, 'opinion': l.opinion if l.status == Loan.STATUS_REJECTED else '',
            'issued': l.issued, 'issuer': f'm{l.issuer_id}' if l.issuer_id else '',
            'received': l.received, 'note': l.note,
        })
    return d


def _asset_dict(a, loans_in_use):
    return {
        'id': a.id, 'name': a.name, 'model': a.model, 'category': a.category,
        'vendor': a.vendor, 'spec': a.spec, 'location': a.location,
        'status': a.STATUS_IN_USE if a.id in loans_in_use and a.status == a.STATUS_FREE else a.status,
        'created': a.created, 'note': a.note, 'datasheet': a.datasheet,
        'image': a.image.url if a.image else '',
    }


def _maintenance_dict(m):
    return {'id': m.id, 'assetId': m.asset_id, 'description': m.description,
            'status': m.status, 'created': m.created,
            'actor': _member_name(m.actor) if m.actor else ''}


def workspace_slice(profile, staff):
    """工作空间快照：assets / loans / maintenance（含隐私裁剪）。"""
    assets = list(Asset.objects.all())
    in_use_ids = set(
        LoanItem.objects.filter(
            loan__status__in=(Loan.STATUS_IN_USE, Loan.STATUS_RETURNING)).values_list('asset_id', flat=True))
    assets_d = [_asset_dict(a, in_use_ids) for a in assets]

    loan_qs = Loan.objects.prefetch_related('items')
    if not staff:
        loan_qs = loan_qs.filter(Q(member_id=profile.user_id) | Q(status__in=(Loan.STATUS_IN_USE, Loan.STATUS_RETURNING)))
    loans_d = [_loan_dict(l, profile.user_id, staff) for l in loan_qs]

    maint_d = [_maintenance_dict(m) for m in Maintenance.objects.all()]

    ts = [a.updated for a in assets] + [l.updated for l in loan_qs] + [m.updated for m in Maintenance.objects.all()]
    return {'assets': assets_d, 'loans': loans_d, 'maintenance': maint_d, '_ts': ts}


def has_open_items(profile):
    return Loan.objects.filter(member_id=profile.user_id, status__in=OPEN_ITEM_STATUSES).exists()


def _get_loan(lid):
    try:
        return Loan.objects.prefetch_related('items').get(id=lid)
    except Loan.DoesNotExist:
        return None


# ─────────────────── 资产 ───────────────────


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assets_create(request):
    me = get_member(request.user)
    if (err := require(request.user, 'action:asset.create', '没有录入模块的权限')):
        return err
    d = request.data or {}
    aid = str(d.get('id', '')).strip().upper()
    name = str(d.get('name', '')).strip()
    if not aid or not name:
        return fail('请填写资产编号和名称')
    if Asset.objects.filter(pk=aid).exists():
        return fail(f'资产编号 {aid} 已存在')
    asset = Asset.objects.create(
        id=aid, name=name, model=str(d.get('model', '')).strip(),
        category=str(d.get('category', '')).strip(), vendor=str(d.get('vendor', '')).strip(),
        spec=str(d.get('spec', '')).strip(), location=str(d.get('location', '')).strip(),
        note=str(d.get('note', '')).strip(), datasheet=str(d.get('datasheet', '')).strip())
    _log(request, me, f'录入模块 · {asset.id} {asset.name}')
    return ok({'id': asset.id})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assets_update(request, aid):
    if (err := require(request.user, 'action:asset.update', '没有编辑模块的权限')):
        return err
    try:
        asset = Asset.objects.get(pk=aid)
    except Asset.DoesNotExist:
        return fail('模块不存在', 404)
    d = request.data or {}
    if str(d.get('id', asset.id)).strip().upper() != asset.id:
        return fail('资产编号不可修改')
    for f in ('name', 'model', 'category', 'vendor', 'spec', 'location', 'note', 'datasheet'):
        if f in d:
            setattr(asset, f, str(d.get(f, '')).strip())
    asset.save()
    _log(request, get_member(request.user), f'更新模块 · {asset.id} {asset.name}')
    return ok()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assets_image(request, aid):
    if (err := require(request.user, 'action:asset.update', '没有编辑模块的权限')):
        return err
    try:
        asset = Asset.objects.get(pk=aid)
    except Asset.DoesNotExist:
        return fail('模块不存在', 404)
    photo = request.FILES.get('image')
    if not photo:
        return fail('请选择图片文件')
    if photo.size > 10 * 1024 * 1024:
        return fail('图片不能超过 10MB')
    from PIL import Image
    try:
        Image.open(photo).verify()
    except Exception:
        return fail('仅支持有效图片文件（jpg/png/webp 等）')
    if asset.image:
        asset.image.delete(save=False)
    asset.image = photo
    asset.save()
    _log(request, get_member(request.user), f'更新模块图片 · {asset.id} {asset.name}')
    return ok({'image': asset.image.url})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assets_maintenance(request, aid):
    if (err := require(request.user, 'action:asset.repair', '没有登记维修的权限')):
        return err
    try:
        asset = Asset.objects.get(pk=aid)
    except Asset.DoesNotExist:
        return fail('模块不存在', 404)
    description = str((request.data or {}).get('description', '')).strip()
    if not description:
        return fail('请填写问题描述')
    if asset.status in (Asset.STATUS_IN_USE, Asset.STATUS_RETIRED):
        return fail('使用中或已报废的模块不能送修', 409)
    create_with_code(Maintenance, 'MT', asset=asset,
                     description=description, status='维修中', actor=request.user)
    asset.status = Asset.STATUS_REPAIR
    asset.save()
    _log(request, get_member(request.user), f'登记维修 · {asset.id} {asset.name} · {description[:40]}')
    return ok()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assets_repair_complete(request, aid):
    if (err := require(request.user, 'action:asset.repair_complete', '没有完成维修的权限')):
        return err
    try:
        asset = Asset.objects.get(pk=aid)
    except Asset.DoesNotExist:
        return fail('模块不存在', 404)
    m = Maintenance.objects.filter(asset=asset, status='维修中').order_by('-created').first()
    if m:
        m.status = '已完成'
        m.save()
    asset.status = Asset.STATUS_FREE
    asset.save()
    _log(request, get_member(request.user), f'维修完成 · {asset.id} {asset.name}')
    from apps.notify.service import create_many, managers_with
    create_many(
        [u for u in managers_with('action:asset.update') if u.id != request.user.id and u.id != (m.actor_id or -1)],
        'asset_repaired', f'模块维修完成 · {asset.name}',
        f'{asset.id} 已恢复可借用', ref_type='asset', ref_id=asset.id, link='assets')
    from apps.email.models import EmailRule
    from apps.email.service import _trigger_by_rule, _member_email
    erule = EmailRule.objects.filter(key='asset_repaired').first()
    if erule and erule.enabled:
        # 收件人 = 送修登记人（申请人），而非执行"维修完成"的操作者自己
        email = _member_email(m.actor if m and m.actor else None)
        _trigger_by_rule(erule, {'title': asset.name, 'id': asset.id}, 'asset', asset.id, [email] if email else [])
    return ok()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assets_retire(request, aid):
    if (err := require(request.user, 'action:asset.retire', '没有报废模块的权限')):
        return err
    try:
        asset = Asset.objects.get(pk=aid)
    except Asset.DoesNotExist:
        return fail('模块不存在', 404)
    if LoanItem.objects.filter(asset=asset, loan__status__in=ACTIVE_LOAN_STATUSES).exists():
        return fail('该模块存在未完成借用，不能报废', 409)
    asset.status = Asset.STATUS_RETIRED
    asset.save()
    _log(request, get_member(request.user), f'报废模块 · {asset.id} {asset.name}')
    return ok()


# ─────────────────── 借用 ───────────────────


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def loans_create(request):
    me = get_member(request.user)
    if (err := require(request.user, 'action:loan.create', '没有申请借用的权限')):
        return err
    d = request.data or {}
    asset_ids = d.get('assetIds') or []
    if not isinstance(asset_ids, list) or not asset_ids:
        return fail('请选择要借用的模块')
    purpose = str(d.get('purpose', '')).strip()
    project = str(d.get('project', '')).strip()
    due = d.get('due')
    if not purpose:
        return fail('请填写借用用途')
    if not due:
        return fail('请填写预计归还时间')
    # 逾期治理：有逾期未归还的模块时禁止发起新借用，先归还再申请
    if Loan.objects.filter(member=request.user,
                           status__in=(Loan.STATUS_IN_USE, Loan.STATUS_RETURNING),
                           due__lt=timezone.now()).exists():
        return fail('你有逾期未归还的模块，请先归还后再申请', 409)

    with transaction.atomic():
        assets = Asset.objects.select_for_update().filter(id__in=asset_ids)
        found = {a.id for a in assets}
        missing = [a for a in asset_ids if a not in found]
        if missing:
            return fail(f'模块不存在：{", ".join(missing)}', 404)
        bad = [a.id for a in assets
               if a.status != Asset.STATUS_FREE
               or LoanItem.objects.filter(asset=a, loan__status__in=ACTIVE_LOAN_STATUSES).exists()]
        if bad:
            return fail(f'以下模块当前不可借用：{", ".join(bad)}', 409)

        loan = create_with_code(Loan, 'BR', member=request.user,
                                purpose=purpose, project=project, due=due,
                                status=Loan.STATUS_PENDING)
        LoanItem.objects.bulk_create([LoanItem(loan=loan, asset_id=a) for a in asset_ids])

    names = ' / '.join(a.name for a in assets)
    _log(request, me, f'申请借用 · {loan.id} · {names}')
    from apps.notify.service import create_many, managers_with
    create_many(
        [u for u in managers_with('action:loan.review') if u.id != request.user.id],
        'loan_apply', f'{me.name} 提交借用申请',
        f'{loan.id} · {names} · 预计归还 {due}', ref_type='loan', ref_id=loan.id, link='loans')
    return ok({'id': loan.id})


def _can_review(loan, viewer):
    """不能审批自己的申请；负责人只能审批普通成员申请。"""
    if loan.member_id == viewer.pk:
        return '不能审批自己的申请'
    prof = getattr(viewer, 'member_profile', None)
    if prof and prof.role == 'manager':
        target = getattr(loan.member, 'member_profile', None)
        if not target or target.role != 'member':
            return '负责人只能审批普通成员的申请'
    return None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def loans_review(request, lid):
    me = get_member(request.user)
    if (err := require(request.user, 'action:loan.review', '没有审批借用的权限')):
        return err
    loan = _get_loan(lid)
    if loan is None:
        return fail('借用单不存在', 404)
    err = _can_review(loan, request.user)
    if err:
        return fail(err, 403)
    if loan.status != Loan.STATUS_PENDING:
        return fail('该借用单不在待审批状态', 409)

    d = request.data or {}
    decision = str(d.get('decision', '')).strip()
    opinion = str(d.get('opinion', '')).strip()
    if decision not in ('approve', 'reject'):
        return fail('decision 须为 approve 或 reject')
    if decision == 'reject' and not opinion:
        return fail('拒绝时必须填写原因')

    loan.status = Loan.STATUS_APPROVED if decision == 'approve' else Loan.STATUS_REJECTED
    loan.reviewer = request.user
    loan.reviewed = timezone.now()
    loan.opinion = opinion
    loan.save()
    action = '批准' if decision == 'approve' else f'拒绝 · {opinion[:40]}'
    _log(request, me, f'审批借用 {loan.id} · {action}')
    from apps.notify.service import create
    create(loan.member, 'loan_reviewed', f'借用申请已{"批准" if decision == "approve" else "拒绝"}',
           f'{loan.id} · {("审批意见：" + opinion) if opinion else ""}', ref_type='loan', ref_id=loan.id, link='loans')
    from apps.email.models import EmailRule
    from apps.email.service import _trigger_by_rule, _member_email
    erule = EmailRule.objects.filter(key='loan_reviewed').first()
    if erule and erule.enabled:
        prof = getattr(loan.member, 'member_profile', None)
        ename = prof.name if prof else loan.member.username
        _trigger_by_rule(erule, {
            'name': ename, 'id': loan.id,
            'result': '已通过' if decision == 'approve' else '未通过',
            'reason': opinion or '无',
        }, 'loan', loan.id, [_member_email(loan.member)])
    return ok()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def loans_issue(request, lid):
    me = get_member(request.user)
    if (err := require(request.user, 'action:loan.issue', '没有确认发放的权限')):
        return err
    loan = _get_loan(lid)
    if loan is None:
        return fail('借用单不存在', 404)
    if loan.status != Loan.STATUS_APPROVED:
        return fail('该借用单不在待发放状态', 409)
    if loan.due and loan.due < timezone.now():
        return fail('预计归还时间已过期，请让成员重新申请', 409)

    # 发放在一个事务中锁定全部资产，再次检查空闲状态，全部成功才发放
    with transaction.atomic():
        items = list(loan.items.select_related('asset').select_for_update())
        if not items:
            return fail('借用单没有关联模块', 409)
        bad = [li.asset_id for li in items
               if li.asset.status not in (Asset.STATUS_FREE, Asset.STATUS_IN_USE)
               or LoanItem.objects.filter(asset=li.asset, loan__status__in=ACTIVE_LOAN_STATUSES)
               .exclude(loan_id=loan.id).exists()]
        if bad:
            return fail(f'以下模块当前不可发放：{", ".join(bad)}', 409)
        for li in items:
            li.asset.status = Asset.STATUS_IN_USE
            li.asset.save()
        loan.status = Loan.STATUS_IN_USE
        loan.issued = timezone.now()
        loan.issuer = request.user
        loan.save()

    names = ' / '.join(li.asset.name for li in loan.items.all())
    _log(request, me, f'确认发放 · {loan.id} · {names}')
    from apps.notify.service import create
    create(loan.member, 'loan_issued', f'借用已发放 · {loan.id}',
           f'{names} · 请于 {loan.due} 前归还', ref_type='loan', ref_id=loan.id, link='loans')
    from apps.email.models import EmailRule
    from apps.email.service import _trigger_by_rule, _member_email
    erule = EmailRule.objects.filter(key='loan_issued').first()
    if erule and erule.enabled:
        prof = getattr(loan.member, 'member_profile', None)
        ename = prof.name if prof else loan.member.username
        _trigger_by_rule(erule, {
            'name': ename, 'id': loan.id,
            'due': timezone.localtime(loan.due).strftime('%m-%d %H:%M') if loan.due else '',
        }, 'loan', loan.id, [_member_email(loan.member)])
    return ok()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def loans_cancel(request, lid):
    if (err := require(request.user, 'action:loan.cancel', '没有取消借用的权限')):
        return err
    loan = _get_loan(lid)
    if loan is None:
        return fail('借用单不存在', 404)
    if loan.member_id != request.user.pk and not can_manage(request.user):
        return fail('只能取消自己的借用单', 403)
    if loan.status != Loan.STATUS_PENDING:
        return fail('只有待审批的借用单可以取消', 409)
    loan.status = Loan.STATUS_CANCELLED
    loan.save()
    _log(request, get_member(request.user), f'取消借用 · {loan.id}')
    return ok()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def loans_request_return(request, lid):
    if (err := require(request.user, 'action:loan.request_return', '没有申请归还的权限')):
        return err
    loan = _get_loan(lid)
    if loan is None:
        return fail('借用单不存在', 404)
    if loan.member_id != request.user.pk:
        return fail('只能对自己的借用单申请归还', 403)
    if loan.status != Loan.STATUS_IN_USE:
        return fail('只有使用中的借用单可以申请归还', 409)
    loan.status = Loan.STATUS_RETURNING
    loan.return_requested = timezone.now()
    loan.save()
    _log(request, get_member(request.user), f'申请归还 · {loan.id}')
    from apps.notify.service import create_many, managers_with
    create_many(
        [u for u in managers_with('action:loan.receive') if u.id != request.user.id],
        'loan_return_requested', f'{get_member(request.user).name} 申请归还模块',
        f'{loan.id} · 请验收归还', ref_type='loan', ref_id=loan.id, link='loans')
    return ok()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def loans_receive(request, lid):
    me = get_member(request.user)
    if (err := require(request.user, 'action:loan.receive', '没有验收归还的权限')):
        return err
    loan = _get_loan(lid)
    if loan is None:
        return fail('借用单不存在', 404)
    if loan.status != Loan.STATUS_RETURNING:
        return fail('该借用单没有待验收的归还申请', 409)

    d = request.data or {}
    damaged_ids = d.get('damagedIds') or []
    note = str(d.get('note', '')).strip()
    if not isinstance(damaged_ids, list):
        return fail('damagedIds 须为数组（完好传 []）')

    with transaction.atomic():
        for li in loan.items.select_related('asset').select_for_update():
            if li.asset_id in damaged_ids:
                li.asset.status = Asset.STATUS_REPAIR
                li.asset.save()
                create_with_code(Maintenance, 'MT', asset=li.asset,
                                 description=note or '归还验收发现损坏',
                                 status='维修中', actor=request.user)
            else:
                li.asset.status = Asset.STATUS_FREE
                li.asset.save()
        # 记录损坏标记（CSV 导出/审计用）
        if damaged_ids:
            LoanItem.objects.filter(loan=loan, asset_id__in=damaged_ids).update(damaged=True)
        loan.status = Loan.STATUS_DONE
        loan.received = timezone.now()
        loan.receiver = request.user
        loan.note = note
        loan.save()

    damaged = ' / '.join(damaged_ids) if damaged_ids else '全部完好'
    _log(request, me, f'验收归还 · {loan.id} · {damaged}')
    from apps.notify.service import create
    create(loan.member, 'loan_returned', f'借用已归还验收 · {loan.id}',
           f'{damaged}', ref_type='loan', ref_id=loan.id, link='loans')
    # 按时归还且无损坏 → 发放积分（每条借用单仅一次）
    if not damaged_ids and loan.due and loan.received and loan.received <= loan.due and loan.member_id:
        from apps.points.service import award
        awarded = award(loan.member, 'loan_on_time', ref_type='loan', ref_id=loan.id,
                        reason=f'{loan.id} 按时归还', actor=request.user)
        if awarded:
            from apps.accounts.models import OperationLog
            OperationLog.objects.create(actor=request.user, text=f'按时归还发放积分 +{awarded.points} · {loan.id}')
    return ok()
