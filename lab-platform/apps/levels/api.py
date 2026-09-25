"""关卡系统 API：关卡 CRUD、任务挂接、成员提交/审核、审核人管理。

统一走 apps.common.response.ok()/fail()，权限用 apps.common.rbac.require。
"""

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import OperationLog
from apps.common.ids import create_with_code, next_code, parse_member_id
from apps.common.permissions import get_member
from apps.common.rbac import require
from apps.common.response import ok, fail
from apps.levels.models import Level, LevelTask, PassRecord, LevelReviewer


def _log(request, text):
    OperationLog.objects.create(
        actor=request.user if request.user.is_authenticated else None, text=str(text)[:256])


def _reward_pass(rec, lv, stars, is_first):
    """通关结算：发放积分/首通加成，累计 EXP，生成站内通知。返回本次发放积分合计数。"""
    from apps.notify.service import create as notify_create
    from apps.points.models import PointRule
    from apps.points.service import award as award_points
    mult = 2 if lv.activity else 1
    total = 0
    rule = PointRule.objects.filter(key='level_pass').first()
    base = rule.points if rule and rule.enabled else 0
    amount = stars * base * mult  # 每星 × 规则分值，活动双倍
    if amount > 0:
        rec_points = award_points(rec.member, 'level_pass', ref_type='level', ref_id=rec.id,
                                  points=amount, reason=f'通关 {lv.title}', actor=None)
        total += rec_points.points if rec_points else 0
    # 首通加成（双倍期也翻倍，鼓励抓紧冲）
    if is_first:
        fr = PointRule.objects.filter(key='level_first_bonus').first()
        fb = fr.points if fr and fr.enabled else 0
        bonus = award_points(rec.member, 'level_first_bonus', ref_type='level', ref_id=rec.id,
                             points=fb * mult, reason=f'首通 {lv.title}')
        total += bonus.points if bonus else 0
    # EXP：星级×20（活动双倍）—— 原子累加，避免并发审核丢更新
    from django.db.models import F
    from apps.accounts.models import MemberProfile
    updated = MemberProfile.objects.filter(user_id=rec.member_id).update(
        level_exp=F('level_exp') + stars * 20 * mult)
    try:
        notify_create(rec.member, 'level_passed', f'关卡通过 · {lv.title[:30]}',
                      f'{["", "一档", "二档", "三档"][max(1, min(3, stars))]} · {rec.score} 分' + (f' · 积分+{total}' if total else '') + (' · 冲刺活动积分双倍' if lv.activity else ''),
                      ref_type='level', ref_id=rec.id, link='levels')
    except Exception:  # noqa: BLE001
        pass
    return total


def _member_name(user):
    prof = getattr(user, 'member_profile', None)
    return prof.name if prof else (user.username if user else '')


def _pass_dict(p):
    return {
        'id': p.id, 'levelId': p.level_id, 'memberId': f'm{p.member_id}',
        'memberName': _member_name(p.member),
        'status': p.status, 'score': p.score, 'stars': p.stars,
        'featured': p.featured, 'firstPass': p.first_pass,
        'bestScore': p.best_score,
        'media': p.media,
        'note': p.note, 'opinion': p.opinion,
        'reviewerName': _member_name(p.reviewer) if p.reviewer_id else '',
        'submittedAt': p.submitted_at, 'reviewedAt': p.reviewed_at,
    }


def _level_dict(lv, profile=None):
    records = lv.pass_records.select_related('member', 'member__member_profile', 'reviewer').all()
    passed = [r for r in records if r.status in (PassRecord.STATUS_PASSED, PassRecord.STATUS_DONE)]
    mine = None
    if profile is not None:
        me = next((r for r in records if r.member_id == profile.user_id), None)
        mine = _pass_dict(me) if me else None
    reviewers = lv.reviewers.filter(active=True).select_related('member', 'member__member_profile')
    unlockable = not lv.require_pass_id
    if lv.require_pass_id:
        my_prev = PassRecord.objects.filter(level=lv.require_pass, member=profile.user_id,
                                            status__in=[PassRecord.STATUS_PASSED, PassRecord.STATUS_DONE]).exists() if profile else False
        unlockable = my_prev
    return {
        'id': lv.id, 'title': lv.title, 'chain': lv.chain, 'chapter': lv.chapter,
        'order': lv.order, 'scoreLimit': lv.score_limit, 'starsRule': lv.stars_rule,
        'requirePassId': lv.require_pass_id, 'description': lv.description,
        'status': lv.status, 'activity': lv.activity, 'cover': lv.cover.url if lv.cover else '',
        'passedCount': len(passed), 'firstPassName': _member_name(passed[0].member) if passed and passed[0].first_pass else '',
        'my': mine,
        'unlocked': unlockable,
        'reviewers': [{'memberId': f'm{r.member_id}', 'name': _member_name(r.member)} for r in reviewers],
        'created': lv.created, 'updated': lv.updated,
    }


# ── 画布布局：坐标 + 依赖（require_pass → flowNextId），数据量小每次请求直算 ──


def _flow_snapshot():
    """全部关卡的坐标与下级映射（未定位关卡先按层级自动摆放）。"""
    levels = list(Level.objects.all())
    pos = {}
    next_map = {}
    for lv in levels:
        if lv.require_pass_id:
            next_map[lv.id] = lv.require_pass_id
    placed = []
    by_chain = {}
    for lv in levels:
        by_chain.setdefault(lv.chain or '其他', []).append(lv)
    for lvs in by_chain.values():
        lvs.sort(key=lambda x: x.order)
        pre = {lv.id: lv for lv in lvs}
        depth = {}

        def dep(lv, seen):
            if lv.id in depth:
                return depth[lv.id]
            if lv.id in seen or not lv.require_pass_id or lv.require_pass_id not in pre:
                depth[lv.id] = 0
                return 0
            depth[lv.id] = dep(pre[lv.require_pass_id], seen | {lv.id}) + 1
            return depth[lv.id]

        for lv in lvs:
            dep(lv, set())
        rows = {}
        for lv in sorted(lvs, key=lambda v: (depth[v.id], v.order)):
            d = depth[lv.id]
            if not lv.pos_x and not lv.pos_y:
                idx = len(rows.get(d, []))
                rows.setdefault(d, []).append(lv)
                pos[lv.id] = (40 + d * 212, 30 + idx * 132)
                placed.append(lv)
        for lv in lvs:
            if lv.id not in pos:
                pos[lv.id] = (lv.pos_x, lv.pos_y)
    return pos, next_map, placed


def _place_and_save():
    """将未定位关卡坐标落库（保留下一次布局）。"""
    from django.utils import timezone as tz
    _, _, placed = _flow_snapshot()
    if placed:
        now = tz.now()
        for lv in placed:
            lv.updated = now
        Level.objects.bulk_update(placed, ['pos_x', 'pos_y', 'updated'])


def _flow_next_id():
    """id → 下一关（按 require_pass 反查；同一前置有多条后续时取 order 最小者）。"""
    nxt = {}
    for lv in Level.objects.exclude(require_pass=None).order_by('order', 'id'):
        nxt.setdefault(lv.require_pass_id, lv.id)
    return nxt


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def levels_list(request):
    me = get_member(request.user)
    _place_and_save()
    _next = _flow_next_id()
    pos, _, _ = _flow_snapshot()
    levels = []
    for lv in Level.objects.prefetch_related('pass_records', 'reviewers'):
        d = _level_dict(lv, me)
        p = pos.get(lv.id, (lv.pos_x, lv.pos_y))
        d['posX'], d['posY'] = p
        d['flowNextId'] = _next.get(lv.id, '')
        levels.append(d)
    return ok({'levels': levels})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def levels_mine(request):
    """我的进阶档案：水平 / 经验条 / 荣誉标章 / 战绩（成员详情成长区与本人主页同源）。"""
    me = get_member(request.user)
    if not me:
        return fail('账号异常', 403)
    from apps.levels.gaming import my_payload
    payload = my_payload(request.user)
    chain_counts = {}
    for ch in Level.objects.values_list('chain', flat=True):
        chain_counts[ch] = chain_counts.get(ch, 0) + 1
    payload['chainsProgress'] = {c: {'total': n} for c, n in chain_counts.items()}
    payload['recent'] = []
    for pr in PassRecord.objects.filter(member=request.user, status__in=[PassRecord.STATUS_PASSED, PassRecord.STATUS_DONE]
                                        ).select_related('level').order_by('-reviewed_at')[:6]:
        payload['recent'].append({
            'levelId': pr.level_id, 'title': pr.level.title, 'chain': pr.level.chain,
            'chapter': pr.level.chapter, 'score': pr.score, 'stars': pr.stars,
            'firstPass': pr.first_pass, 'featured': pr.featured, 'reviewedAt': pr.reviewed_at,
        })
    return ok(payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def levels_member_profile(request, mid):
    """某成员的进阶档案（头像/详情页成长区用）：全员可见水平与标章，不暴露隐私字段。"""
    from apps.accounts.models import MemberProfile
    from apps.levels.gaming import my_payload
    pid = parse_member_id(str(mid))
    mp = MemberProfile.objects.select_related('user').filter(user_id=pid, active=True).first() if pid else None
    if not mp:
        return fail('成员不存在', 404)
    prev = PassRecord.STATUS_PASSED
    recs = PassRecord.objects.filter(member_id=pid, status__in=[prev, PassRecord.STATUS_DONE]
                                     ).select_related('level').order_by('-reviewed_at')
    payload = my_payload(mp.user)
    chain_counts = {}
    for ch in Level.objects.values_list('chain', flat=True):
        chain_counts[ch] = chain_counts.get(ch, 0) + 1
    payload['chainsProgress'] = {c: {'total': n} for c, n in chain_counts.items()}
    payload['recent'] = [{
        'levelId': pr.level_id, 'title': pr.level.title, 'chain': pr.level.chain,
        'chapter': pr.level.chapter, 'score': pr.score, 'stars': pr.stars,
        'firstPass': pr.first_pass, 'featured': pr.featured, 'reviewedAt': pr.reviewed_at,
    } for pr in recs[:6]]
    return ok(payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def levels_detail(request, lid):
    try:
        lv = Level.objects.get(pk=lid)
    except Level.DoesNotExist:
        return fail('关卡不存在', 404)
    me = get_member(request.user)
    wall = []
    for p in lv.pass_records.select_related('member', 'member__member_profile', 'reviewer').filter(
            status__in=[PassRecord.STATUS_PASSED, PassRecord.STATUS_DONE]).order_by('-best_score'):
        wall.append(_pass_dict(p))
    tasks = []
    for link in lv.tasks_link.select_related('task').all():
        t = link.task
        tasks.append({
            'id': t.id, 'title': t.title, 'status': t.status, 'priority': t.priority,
            'assigneeId': f'm{t.assignee_id}' if t.assignee_id else '',
            'assigneeName': _member_name(t.assignee),
            'due': t.due, 'score': t.score,
            'media': t.media, 'submission': t.submission[:300] if t.submission else '',
            'kind': link.kind,
        })
    return ok({'level': _level_dict(lv, me), 'wall': wall, 'tasks': tasks})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def levels_create(request):
    if (err := require(request.user, 'action:level.manage', '没有管理关卡的权限')):
        return err
    d = request.data or {}
    title = str(d.get('title', '')).strip()
    if not title:
        return fail('请填写关卡名称')
    lv = create_with_code(Level, 'LV', title=title, chain=str(d.get('chain') or '其他')[:32],
                          description=str(d.get('description') or '')[:2000], creator=request.user)
    # 画布创建：落坐标 + 连接前置（新关的 require_pass = 源头关卡）
    pos = d.get('pos')
    if isinstance(pos, dict):
        try:
            lv.pos_x, lv.pos_y = float(pos.get('x', 0)), float(pos.get('y', 0))
        except (TypeError, ValueError):
            pass
    pre = str(d.get('linkTo') or '').strip()
    if pre and pre != lv.id:
        lv.require_pass = Level.objects.filter(pk=pre).first()
    lv.save(update_fields=['pos_x', 'pos_y', 'require_pass'])
    _log(request, f'创建关卡 · {lv.id} {lv.title[:30]}')
    return ok({'id': lv.id})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def levels_update(request, lid):
    if (err := require(request.user, 'action:level.manage', '没有管理关卡的权限')):
        return err
    try:
        lv = Level.objects.get(pk=lid)
    except Level.DoesNotExist:
        return fail('关卡不存在', 404)
    d = request.data or {}
    if 'title' in d and str(d.get('title', '')).strip():
        lv.title = str(d.get('title', '')).strip()
    for f in ('chain', 'chapter', 'description', 'stars_rule'):
        if f in d:
            setattr(lv, f, str(d.get(f, '')).strip())
    if 'order' in d:
        try:
            lv.order = max(0, int(d.get('order')))
        except (TypeError, ValueError):
            pass
    if 'scoreLimit' in d:
        try:
            lv.score_limit = max(1, int(d.get('scoreLimit')))
        except (TypeError, ValueError):
            pass
    if 'status' in d and d.get('status') in ('open', 'closed'):
        lv.status = d.get('status')
    if 'activity' in d:
        lv.activity = bool(d.get('activity'))
    if 'requirePassId' in d:
        rid = str(d.get('requirePassId') or '').strip()
        lv.require_pass = Level.objects.filter(pk=rid).first() if rid and rid != lv.id else None
    lv.save()
    _log(request, f'更新关卡 · {lv.id} {lv.title[:30]}')
    return ok()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def levels_delete(request, lid):
    if (err := require(request.user, 'action:level.manage', '没有管理关卡的权限')):
        return err
    try:
        lv = Level.objects.get(pk=lid)
    except Level.DoesNotExist:
        return fail('关卡不存在', 404)
    _log(request, f'删除关卡 · {lv.id} {lv.title[:30]}')
    lv.delete()
    return ok()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def levels_link_task(request, lid):
    if (err := require(request.user, 'action:level.manage', '没有管理关卡的权限')):
        return err
    try:
        lv = Level.objects.get(pk=lid)
    except Level.DoesNotExist:
        return fail('关卡不存在', 404)
    from apps.tasksapp.models import Task
    tid = str((request.data or {}).get('taskId', '')).strip()
    task = Task.objects.filter(pk=tid).first()
    if not task:
        return fail('任务不存在', 404)
    LevelTask.objects.get_or_create(level=lv, task=task, defaults={'kind': str((request.data or {}).get('kind', 'main'))[:16]})
    _log(request, f'关卡挂任务 · {lv.id} + {tid}')
    return ok()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def levels_unlink_task(request, lid, tid):
    if (err := require(request.user, 'action:level.manage', '没有管理关卡的权限')):
        return err
    LevelTask.objects.filter(level_id=lid, task_id=tid).delete()
    return ok()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def levels_submit(request, lid):
    """成员提交通过：附带一张完成图/视频 + 备注。同一成员已通过则拒绝。"""
    try:
        lv = Level.objects.get(pk=lid)
    except Level.DoesNotExist:
        return fail('关卡不存在', 404)
    me = get_member(request.user)
    if not me:
        return fail('账号异常', 403)
    if lv.status != Level.STATUS_OPEN:
        return fail('该关卡已关闭，无法提交')
    prev = PassRecord.objects.filter(level=lv, member=request.user).first()
    if prev and prev.status in (PassRecord.STATUS_PASSED, PassRecord.STATUS_DONE):
        return fail('该关卡已通过，可在详情页刷新成绩', 409)
    if prev is None:
        prev = create_with_code(PassRecord, 'PR', level=lv, member=request.user)
    note = str(request.data.get('note', ''))[:512]
    f = request.FILES.get('file')
    media = list(prev.media or [])
    if f:
        import os
        if f.size > 40 * 1024 * 1024:
            return fail('文件不能超过 40MB')
        ext = os.path.splitext(f.name or '')[1].lower().lstrip('.')
        if ext not in ('jpg', 'jpeg', 'png', 'gif', 'webp', 'mp4', 'mov', 'pdf', 'zip'):
            return fail(f'不支持的文件类型 .{ext}')
        from django.core.files.storage import default_storage
        from django.utils import timezone as tz
        pname = default_storage.save(f'levels/{tz.now():%Y%m}/{prev.id}_{len(media)}.{ext}', f)
        media.append({'url': default_storage.url(pname), 'name': f.name})
    if not media and not note:
        return fail('请上传完成图片/视频或填写备注')
    prev.media = media
    prev.note = note
    prev.status = PassRecord.STATUS_PENDING
    prev.submitted_at = timezone.now()
    prev.save()
    _log(request, f'关卡提交 · {lv.id} {me.name} · 待审核')
    return ok({'id': prev.id, 'status': prev.status})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def levels_review(request, lid):
    """审核：通过（打分+星+可选精选）/ 不通过。打分会成为该成员此关成绩。"""
    if (err := require(request.user, 'action:level.review', '没有审核关卡的权限')):
        return err
    try:
        lv = Level.objects.get(pk=lid)
    except Level.DoesNotExist:
        return fail('关卡不存在', 404)
    # 关卡指定了审核人时，仅指定审核人可审（LevelReviewer 强制生效）
    reviewers = lv.reviewers.filter(active=True)
    if reviewers.exists() and request.user.pk not in set(reviewers.values_list('member_id', flat=True)):
        return fail('你不是该关卡的指定审核人', 403)
    d = request.data or {}
    mid = parse_member_id(str(d.get('memberId', '')))
    if not mid:
        return fail('成员不合法')
    try:
        rec = PassRecord.objects.select_related('member').get(level=lv, member_id=mid)
    except PassRecord.DoesNotExist:
        return fail('该成员还没有提交此关卡', 404)
    decision = str(d.get('decision', '')).strip()
    if decision == 'pass':
        try:
            score = int(d.get('score'))
        except (TypeError, ValueError):
            return fail('请提供有效分数')
        score = min(max(score, 0), lv.score_limit)
        # 星级换算：默认规则 满分三等分；starsRule 支持 "60,80" 阈值
        thresholds = [60, 80]
        rule = lv.stars_rule.strip()
        if rule:
            parts = [p.strip() for p in rule.split(',') if p.strip().isdigit()]
            if len(parts) >= 2:
                thresholds = [int(x) for x in parts[:2]]
        if score >= lv.score_limit * thresholds[1] / 100:
            stars = 3
        elif score >= lv.score_limit * thresholds[0] / 100:
            stars = 2
        else:
            stars = 1
        is_first = not PassRecord.objects.filter(level=lv, member_id=mid,
                                                 status__in=[PassRecord.STATUS_PASSED, PassRecord.STATUS_DONE]).exists()
        rec.status = PassRecord.STATUS_PASSED
        rec.score, rec.stars = score, stars
        rec.reviewer, rec.reviewed_at = request.user, timezone.now()
        rec.opinion = str(d.get('opinion', ''))[:2000]
        rec.first_pass = is_first or rec.first_pass
        rec.featured = bool(d.get('featured'))
        if score > rec.best_score:
            rec.best_score = score
            rec.best_at = timezone.now()
        rec.save()
        # 通关结算：积分 + EXP（冲刺活动翻倍）+ 首通加成 + 通知
        awarded = _reward_pass(rec, lv, stars, is_first)
        _log(request, f'关卡审核通过 · {lv.id} {_member_name(rec.member)} {score}分 · {["", "一档", "二档", "三档"][max(1, min(3, stars))]}' + (f' · 积分+{awarded}' if awarded else ''))
        return ok({'status': rec.status, 'score': score, 'stars': stars, 'firstPass': is_first})
    if decision == 'reject':
        rec.status = PassRecord.STATUS_REJECTED
        rec.reviewer, rec.reviewed_at = request.user, timezone.now()
        rec.opinion = str(d.get('opinion', ''))[:2000]
        rec.save()
        _log(request, f'关卡未通过 · {lv.id} {_member_name(rec.member)}')
        return ok({'status': rec.status})
    return fail('decision 须为 pass 或 reject')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def levels_connect(request, lid):
    """连线（画布拖拽）：将 lid 的下级设为 targetId（posY 同层由上到下），断开传 targetId=''。"""
    if (err := require(request.user, 'action:level.manage', '没有管理关卡的权限')):
        return err
    try:
        lv = Level.objects.get(pk=lid)
    except Level.DoesNotExist:
        return fail('关卡不存在', 404)
    target = str((request.data or {}).get('targetId', '')).strip()
    if target:
        if target == lid:
            return fail('不能连接自身')
        try:
            nxt = Level.objects.get(pk=target)
        except Level.DoesNotExist:
            return fail('目标关卡不存在', 404)
        # 环路防护：target 的依赖链上若出现 lid 则拒绝
        seen = set()
        cur = nxt
        while cur.require_pass_id and cur.require_pass_id not in seen:
            seen.add(cur.require_pass_id)
            if cur.require_pass_id == lid:
                return fail('连线将形成循环依赖，请先调整其它连线')
            cur = Level.objects.filter(pk=cur.require_pass_id).first() or None
            if cur is None:
                break
        lv.require_pass = nxt
    else:
        lv.require_pass = None
    lv.save(update_fields=['require_pass', 'updated'])
    _log(request, f'关卡连线 · {lv.id} → {"无" if not target else target}')
    return ok()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def levels_positions(request):
    """批量保存画布坐标 `{"positions": [{"id","x","y"}, ...]}`。"""
    if (err := require(request.user, 'action:level.manage', '没有管理关卡的权限')):
        return err
    rows = (request.data or {}).get('positions') or []
    ids = {}
    for r in rows:
        try:
            ids[str(r.get('id'))] = (float(r.get('x')), float(r.get('y')))
        except (TypeError, ValueError):
            continue
    if not ids:
        return fail('没有可保存的坐标')
    dirty = []
    from django.utils import timezone as tz
    now = tz.now()
    for lv in Level.objects.filter(id__in=ids.keys()):
        x, y = ids[lv.id]
        lv.pos_x, lv.pos_y = x, y
        lv.updated = now
        dirty.append(lv)
    Level.objects.bulk_update(dirty, ['pos_x', 'pos_y', 'updated'])
    return ok({'count': len(dirty)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def levels_reviewers(request, lid):
    if (err := require(request.user, 'action:level.manage', '没有管理关卡的权限')):
        return err
    try:
        lv = Level.objects.get(pk=lid)
    except Level.DoesNotExist:
        return fail('关卡不存在', 404)
    mid = parse_member_id(str((request.data or {}).get('memberId', '')))
    if not mid:
        return fail('成员不合法')
    from django.contrib.auth import get_user_model
    member = get_user_model().objects.filter(pk=mid, member_profile__isnull=False).first()
    if not member:
        return fail('成员不存在')
    r, created = LevelReviewer.objects.get_or_create(level=lv, member=member, defaults={'added_by': request.user})
    if not created and not r.active:
        r.active = True
        r.save()
    _log(request, f'关卡审核人新增 · {lv.id} {_member_name(member)}')
    return ok()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def levels_reviewers_remove(request, lid, mid):
    if (err := require(request.user, 'action:level.manage', '没有管理关卡的权限')):
        return err
    pid = parse_member_id(mid)
    if pid:
        LevelReviewer.objects.filter(level_id=lid, member_id=pid).update(active=False)
    _log(request, f'关卡审核人移除 · {lid}')
    return ok()


def workspace_slice(profile, staff):
    """快照：关卡列表（含我的记录/坐标/连线）+ 我的进阶档案（水平/标章/战绩）。"""
    _place_and_save()
    _next = _flow_next_id()
    pos, _, _ = _flow_snapshot()
    levels = []
    for lv in Level.objects.prefetch_related('pass_records', 'reviewers'):
        d = _level_dict(lv, profile)
        p = pos.get(lv.id, (lv.pos_x, lv.pos_y))
        d['posX'], d['posY'] = p
        d['flowNextId'] = _next.get(lv.id, '')
        levels.append(d)
    from apps.levels.gaming import my_payload
    return {'levels': levels, 'myProfile': my_payload(profile.user), '_ts': [l.updated for l in Level.objects.all()]}