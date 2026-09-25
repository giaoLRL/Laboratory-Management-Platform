"""实验室可视化座位：俯视图、在席位置、气泡、状态、形象、大厅聊天、地图编辑。

核心派生规则：**小人 = 今日已打卡且未签退**。座位位置由
`SeatPresence`（挪动落库）→ `layout.owners`（默认归属）→ 空工位
三级解析得到，因此无需为「谁坐哪」单独开真值表。
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.accounts.models import MemberProfile, OperationLog
from apps.checkins.models import CheckInRecord
from apps.common.ids import create_with_code, member_id, parse_member_id
from apps.common.permissions import get_member
from apps.common.rbac import require
from apps.common.response import ok, fail
from apps.seats.models import (MemberCharacter, SeatChat, SeatChatCursor, SeatLayout,
                               SeatMessage, SeatPresence, SeatStatus)

# 格子类型：. 通道空地  w 工位  s 储物柜  t 测试台  d 门口  # 墙体
GRID_KINDS = ('.', 'w', 's', 't', 'd', '#')
WALKABLE = ('.', 'w')          # 能站人的格子（家具与墙体不行）
MAX_DIM = 40

BUBBLE_TTL = 15                # 气泡存活秒数
BUBBLE_COOLDOWN = 60           # 同一人两次气泡的最小间隔
CHAT_COOLDOWN = 3              # 大厅发言最小间隔
CHAT_PER_MINUTE = 20           # 大厅发言频率上限
CHAT_PAGE = 30                 # 大厅每页条数

MAX_STATUS_TEXT = 30
MAX_BUBBLE_TEXT = 50
MAX_CHAT_TEXT = 200

# 参数化形象的槽位白名单：后端只校验取值，前端按同一份清单拼 SVG
CHARACTER_BOOK = {
    'skin': ('#f6d0ac', '#eec096', '#d8a377', '#c08a5e'),
    'hairStyle': ('flat', 'cap', 'bob', 'spike'),
    'hairColor': ('#3a3f46', '#6a5a41', '#2e3648', '#1b1d21'),
    'top': ('#243E70', '#6f7c8c', '#3e6b5a', '#96603a', '#6a4a7f'),
    'chair': ('#9aa0a8', '#6d747d', '#b9a68a', '#c3c7cd'),
    'prop': ('none', 'pc', 'wrench', 'book'),
    'glasses': (True, False),
}


# ────────────────────────────── 通用小工具 ──────────────────────────────

def _log(actor, text):
    OperationLog.objects.create(actor=actor, text=str(text)[:256])


def _truthy(value):
    return str(value).lower() in ('1', 'true', 'yes', 'on')


def _in_bounds(r, c, rows, cols):
    return 0 <= r < rows and 0 <= c < cols


def _parse_key(key):
    """'3-2' → (3, 2)；非法返回 (None, None)。"""
    try:
        r, c = (int(x) for x in str(key).split('-'))
    except (TypeError, ValueError):
        return None, None
    return r, c


def active_layout():
    return SeatLayout.objects.filter(active=True).order_by('-updated').first()


def _grid_of(layout):
    """返回 rows×cols 的二维字符数组，脏数据按通道补齐。"""
    rows, cols = layout.rows or 0, layout.cols or 0
    src = layout.grid or []

    def ch(r, c):
        try:
            v = src[r][c]
        except (IndexError, TypeError):
            return '.'
        return v if v in GRID_KINDS else '.'

    return [[ch(r, c) for c in range(cols)] for r in range(rows)]


def _on_duty_ids():
    """今日已打卡且未签退的成员 id 集合 —— 小人存在与否的唯一依据。"""
    now = timezone.localtime()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return set(CheckInRecord.objects.filter(
        created__gte=day_start, signout_at__isnull=True).values_list('user_id', flat=True))


def _resolve_positions(layout, on_duty):
    """算出在席成员各自的格子：SeatPresence → 默认归属 → 空工位。

    返回值 {user_id: (row, col)}。这一步是只读的，不落库；
    只有用户主动挪位时才写 SeatPresence。
    """
    grid = _grid_of(layout)
    rows, cols = layout.rows or 0, layout.cols or 0
    owners = layout.owners or {}
    placed = {}          # 'r-c' → user_id
    result = {}          # user_id → (row, col)

    # 1) 用户自己挪过的位置（最高优先级）
    for p in SeatPresence.objects.filter(layout=layout).select_related('member'):
        if p.member_id not in on_duty or p.member_id in result:
            continue
        key = f'{p.row}-{p.col}'
        if (_in_bounds(p.row, p.col, rows, cols)
                and grid[p.row][p.col] in WALKABLE and key not in placed):
            placed[key] = p.member_id
            result[p.member_id] = (p.row, p.col)

    # 2) 布局里配的默认归属
    for key, value in owners.items():
        uid = parse_member_id(value)
        if not uid or uid not in on_duty or uid in result or key in placed:
            continue
        r, c = _parse_key(key)
        if r is not None and _in_bounds(r, c, rows, cols) and grid[r][c] in WALKABLE:
            placed[key] = uid
            result[uid] = (r, c)

    # 3) 其余在席成员按「先工位后通道」的空位顺序补上，保证打卡就能看见人
    free = [(r, c) for r in range(rows) for c in range(cols)
            if grid[r][c] in WALKABLE and f'{r}-{c}' not in placed]
    ordered = [p for p in free if grid[p[0]][p[1]] == 'w'] + [p for p in free if grid[p[0]][p[1]] == '.']
    cursor = 0
    for uid in sorted(on_duty):
        if uid in result:
            continue
        if cursor >= len(ordered):
            break
        r, c = ordered[cursor]
        cursor += 1
        placed[f'{r}-{c}'] = uid
        result[uid] = (r, c)
    return result


def _layout_dict(layout):
    return {'id': layout.id, 'name': layout.name, 'rows': layout.rows, 'cols': layout.cols,
            'grid': layout.grid or [], 'labels': layout.labels or {},
            'owners': layout.owners or {}, 'updated': layout.updated}


def _chat_dict(msg):
    return {'id': msg.id, 'memberId': member_id(msg.member_id), 'text': msg.text,
            'created': msg.created}


def seat_state(profile, layout):
    """座位页所需的全部只读状态（workspace 快照与轻量轮询接口共用这一份逻辑）。

    只下发**当前有效**的数据：在席成员的状态/气泡、未过期的气泡。
    聊天正文不进这里（见 /seats/chat），只给未读数。
    """
    now = timezone.now()
    on_duty = _on_duty_ids()
    pos = _resolve_positions(layout, on_duty)
    presence = [{'memberId': member_id(uid), 'row': rc[0], 'col': rc[1]}
                for uid, rc in pos.items()]

    statuses, characters, bubbles, ts = [], [], [], [layout.updated]
    for s in SeatStatus.objects.all():
        if s.member_id in on_duty:
            statuses.append({'memberId': member_id(s.member_id),
                             'statusKey': s.status_key, 'text': s.text})
            ts.append(s.updated)
    for ch in MemberCharacter.objects.all():
        characters.append({'memberId': member_id(ch.member_id), 'parts': ch.parts or {}})
        ts.append(ch.updated)
    for b in SeatMessage.objects.filter(layout=layout, expires_at__gt=now):
        bubbles.append({'memberId': member_id(b.member_id), 'text': b.text,
                        'expiresAt': b.expires_at})
        ts.append(b.updated)

    chats = SeatChat.objects.filter(active=True)
    cursor = SeatChatCursor.objects.filter(member=profile.user).first()
    unread = chats.filter(created__gt=cursor.last_read_at).count() if cursor else chats.count()

    return {'presence': presence, 'statuses': statuses, 'characters': characters,
            'bubbles': bubbles, 'unread': unread, '_ts': ts}


def workspace_slice(profile, staff):
    """往 /workspace 快照里追加座位数据。"""
    layout = active_layout()
    if not layout:
        return {'seatLayout': None, 'seatPresence': [], 'seatStatuses': [],
                'seatCharacters': [], 'seatBubbles': [], 'seatChatUnread': 0, '_ts': []}
    st = seat_state(profile, layout)
    return {'seatLayout': _layout_dict(layout), 'seatPresence': st['presence'],
            'seatStatuses': st['statuses'], 'seatCharacters': st['characters'],
            'seatBubbles': st['bubbles'], 'seatChatUnread': st['unread'], '_ts': st['_ts']}


# ────────────────────────────── 读接口 ──────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def seats_layout(request):
    """座位页的**轻量轮询**接口：只返回座位状态，不拉整份 workspace 快照。

    前端每隔几秒轮询这一个接口即可（比 /workspace 少两个大请求：
    /auth/me 与全量快照），且拿到的东西与快照里的座位字段完全一致。
    """
    if (err := require(request.user, 'page:seats', '没有查看座位图的权限')):
        return err
    layout = active_layout()
    profile = get_member(request.user)
    if not layout or not profile:
        return ok({'layout': None, 'presence': [], 'statuses': [], 'characters': [],
                   'bubbles': [], 'unread': 0})
    st = seat_state(profile, layout)
    return ok({'layout': _layout_dict(layout), 'presence': st['presence'],
               'statuses': st['statuses'], 'characters': st['characters'],
               'bubbles': st['bubbles'], 'unread': st['unread']})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def seats_chat(request):
    """实验室大厅分页：`?before=<消息号>` 取更早的一页，返回按时间正序。"""
    if (err := require(request.user, 'page:seats', '没有查看实验室大厅的权限')):
        return err
    qs = SeatChat.objects.filter(active=True).select_related('member').order_by('-created')
    before = request.GET.get('before')
    if before:
        anchor = SeatChat.objects.filter(id=str(before)).first()
        if anchor:
            qs = qs.filter(created__lt=anchor.created)
    rows = list(qs[:CHAT_PAGE + 1])
    has_more = len(rows) > CHAT_PAGE
    rows = rows[:CHAT_PAGE]
    rows.reverse()
    return ok({'messages': [_chat_dict(m) for m in rows], 'hasMore': has_more})


# ────────────────────────────── 本人操作 ──────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def seats_move(request):
    """挪位：只能移动自己的小人，且目标格必须能站、且没被别人占。"""
    if (err := require(request.user, 'action:seats.move', '没有移动小人的权限')):
        return err
    layout = active_layout()
    if not layout:
        return fail('还没有配置实验室布局，请联系管理员', 409)
    d = request.data or {}
    try:
        r, c = int(d.get('row')), int(d.get('col'))
    except (TypeError, ValueError):
        return fail('目标位置参数不正确')
    rows, cols = layout.rows or 0, layout.cols or 0
    if not _in_bounds(r, c, rows, cols):
        return fail('目标位置超出地图范围')
    grid = _grid_of(layout)
    if grid[r][c] not in WALKABLE:
        return fail('那一格放不下人（墙 / 储物柜 / 测试台 / 门口）')

    on_duty = _on_duty_ids()
    if request.user.id not in on_duty:
        return fail('还没有打卡入席，先打卡才能入座', 409)
    for uid, rc in _resolve_positions(layout, on_duty).items():
        if rc == (r, c) and uid != request.user.id:
            return fail('那一格有人，换个空位吧', 409)

    SeatPresence.objects.update_or_create(
        member=request.user, defaults={'layout': layout, 'row': r, 'col': c})
    return ok({'row': r, 'col': c})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def seats_status(request):
    """设置本人状态 + 文字（持续到签退或下次修改）。"""
    if (err := require(request.user, 'action:seats.status', '没有设置状态的权限')):
        return err
    d = request.data or {}
    key = str(d.get('statusKey') or 'work').strip()
    if key not in dict(SeatStatus.STATUS_CHOICES):
        return fail('状态不在可选范围内')
    text = str(d.get('text') or '').strip()[:MAX_STATUS_TEXT]
    if key == 'custom' and not text:
        return fail('自定义状态必须填写文字')
    SeatStatus.objects.update_or_create(
        member=request.user, defaults={'status_key': key, 'text': text})
    return ok({'statusKey': key, 'text': text})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def seats_bubble(request):
    """冒一条气泡：限频（默认 60 秒一条），15 秒后服务端不再下发。"""
    if (err := require(request.user, 'action:seats.bubble', '没有发气泡的权限')):
        return err
    layout = active_layout()
    if not layout:
        return fail('还没有配置实验室布局，请联系管理员', 409)
    text = str((request.data or {}).get('text') or '').strip()[:MAX_BUBBLE_TEXT]
    if not text:
        return fail('气泡内容不能为空')

    now = timezone.now()
    last = SeatMessage.objects.filter(member=request.user, layout=layout).order_by('-created').first()
    if last:
        left = BUBBLE_COOLDOWN - (now - last.created).total_seconds()
        if left > 0:
            return fail(f'气泡发得太频繁了，{int(left) + 1} 秒后再试', 429)

    bubble = create_with_code(SeatMessage, 'SB', layout=layout, member=request.user,
                             text=text, expires_at=now + timedelta(seconds=BUBBLE_TTL))
    return ok({'id': bubble.id, 'expiresAt': bubble.expires_at})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def seats_character(request):
    """保存本人形象参数：逐槽位白名单校验，绝不落任意 SVG/HTML。"""
    if (err := require(request.user, 'action:seats.status', '没有设置形象的权限')):
        return err
    parts = (request.data or {}).get('parts')
    if not isinstance(parts, dict):
        return fail('形象参数格式不正确')
    clean = {}
    for slot, allowed in CHARACTER_BOOK.items():
        if slot not in parts or parts[slot] is None:
            continue
        value = parts[slot]
        if slot == 'glasses':
            clean[slot] = bool(value)
        elif value in allowed:
            clean[slot] = value
        else:
            return fail(f'形象参数「{slot}」不在可选范围内')
    MemberCharacter.objects.update_or_create(member=request.user, defaults={'parts': clean})
    return ok({'parts': clean})


# ────────────────────────────── 实验室大厅 ──────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def seats_chat_send(request):
    """大厅发言；可选同时在自己座位上冒一条气泡（同一条动作，不另受气泡限频）。"""
    if (err := require(request.user, 'action:seats.chat', '没有在大厅发言的权限')):
        return err
    d = request.data or {}
    text = str(d.get('text') or '').strip()[:MAX_CHAT_TEXT]
    if not text:
        return fail('消息内容不能为空')

    now = timezone.now()
    last = SeatChat.objects.filter(member=request.user).order_by('-created').first()
    if last:
        left = CHAT_COOLDOWN - (now - last.created).total_seconds()
        if left > 0:
            return fail('发得太快了，缓一缓', 429)
    if SeatChat.objects.filter(member=request.user,
                               created__gte=now - timedelta(minutes=1)).count() >= CHAT_PER_MINUTE:
        return fail('一分钟内发得太多了，先歇一会儿', 429)

    msg = create_with_code(SeatChat, 'SC', member=request.user, text=text)
    # 发言即视为已读，避免自己的消息给自己加未读
    SeatChatCursor.objects.update_or_create(
        member=request.user, defaults={'last_read_at': msg.created})

    if _truthy(d.get('bubble')):
        layout = active_layout()
        if layout:
            create_with_code(SeatMessage, 'SB', layout=layout, member=request.user,
                             text=text[:MAX_BUBBLE_TEXT],
                             expires_at=now + timedelta(seconds=BUBBLE_TTL))
    return ok(_chat_dict(msg))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def seats_chat_read(request):
    """把未读游标推到当前时刻。"""
    if (err := require(request.user, 'page:seats', '没有查看实验室大厅的权限')):
        return err
    SeatChatCursor.objects.update_or_create(
        member=request.user, defaults={'last_read_at': timezone.now()})
    return ok({'unread': 0})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def seats_chat_delete(request, cid):
    """管理端撤回大厅消息（软删除，保留审计痕迹）。"""
    if (err := require(request.user, 'action:seats.manage', '没有管理实验室大厅的权限')):
        return err
    msg = SeatChat.objects.filter(id=str(cid)).first()
    if not msg:
        return fail('消息不存在', 404)
    msg.active = False
    msg.save(update_fields=['active'])
    _log(request.user, f'撤回大厅消息 {msg.id}')
    return ok({'id': msg.id})


# ────────────────────────────── 地图编辑（管理端） ──────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def seats_layout_save(request):
    """保存实验室布局：整份校验后原子替换，越界的人退回自动分配。"""
    if (err := require(request.user, 'action:seats.manage', '没有编辑实验室布局的权限')):
        return err
    d = request.data or {}
    try:
        rows, cols = int(d.get('rows')), int(d.get('cols'))
    except (TypeError, ValueError):
        return fail('行数与列数必须是整数')
    if not (3 <= rows <= MAX_DIM and 3 <= cols <= MAX_DIM):
        return fail(f'地图尺寸需在 3~{MAX_DIM} 之间')

    raw = d.get('grid')
    if not isinstance(raw, list) or len(raw) != rows:
        return fail(f'格子矩阵必须正好是 {rows} 行')
    grid = []
    for r, line in enumerate(raw):
        text = str(line)
        if len(text) != cols:
            return fail(f'第 {r + 1} 行需要 {cols} 格，当前 {len(text)} 格')
        if any(ch not in GRID_KINDS for ch in text):
            return fail(f'第 {r + 1} 行含未知格子类型')
        grid.append(text)

    labels_in, owners_in = d.get('labels') or {}, d.get('owners') or {}
    if not isinstance(labels_in, dict) or not isinstance(owners_in, dict):
        return fail('座位编号 / 默认归属格式不正确')

    labels, seen = {}, set()
    for key, value in labels_in.items():
        r, c = _parse_key(key)
        if r is None or not _in_bounds(r, c, rows, cols) or grid[r][c] != 'w':
            continue
        label = str(value).strip()[:16]
        if not label:
            continue
        if label in seen:
            return fail(f'座位编号重复：{label}')
        seen.add(label)
        labels[key] = label

    owners = {}
    for key, value in owners_in.items():
        r, c = _parse_key(key)
        uid = parse_member_id(value)
        if r is None or not _in_bounds(r, c, rows, cols) or grid[r][c] != 'w':
            continue
        if uid and MemberProfile.objects.filter(user_id=uid).exists():
            owners[key] = member_id(uid)

    with transaction.atomic():
        layout, _created = SeatLayout.objects.update_or_create(
            id=str(d.get('id') or 'main').strip()[:32],
            defaults={'name': str(d.get('name') or '实验室平面').strip()[:64],
                      'rows': rows, 'cols': cols, 'grid': grid,
                      'labels': labels, 'owners': owners, 'active': True})
        # 被改成家具/挪出边界的在席位置作废，交给自动分配
        for p in SeatPresence.objects.filter(layout=layout):
            if not _in_bounds(p.row, p.col, rows, cols) or grid[p.row][p.col] not in WALKABLE:
                p.delete()

    _log(request.user, f'更新实验室布局 · {rows}×{cols}')
    return ok({'id': layout.id})