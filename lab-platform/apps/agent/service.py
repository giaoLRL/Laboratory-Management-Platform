"""LLM 智能体服务：DeepSeek（OpenAI 兼容协议）+ 权限门控工具 + 写操作二次确认。

写操作（create_task 等）：
  - TOOLSPEC 按当前用户权限过滤（无权限的工具不出现在 prompt，从源头隔离）；
  - 首次触发不执行，暂存到会话 pending_op，等待用户在前端确认后由 /agent/confirm 执行；
  - 执行时再次校验权限并写 OperationLog。

个人记忆：UserMemory 键值存储，随 system prompt 注入（近 20 条）。
"""

import json

import requests
from django.conf import settings

from apps.common.rbac import can as rbac_can

# (key, label)
TOOL_BUILDERS = [
    ('get_stats', '实验室整体统计', False, '', {}),
    ('query_assets', '按名称/类别/状态查询模块', False, '', {
        'q': {'type': 'string', 'description': '名称关键词'},
        'status': {'type': 'string', 'description': '空闲/使用中/维修中/报废'}}),
    ('query_loans', '查询借用单（可按状态筛选）', False, '', {
        'status': {'type': 'string', 'description': '待审批/已批准/已拒绝/使用中/归还申请中/已完成'}}),
    ('query_tasks', '查询任务（可按看板列与负责人筛选）', False, '', {
        'status': {'type': 'string', 'description': 'todo/doing/done'},
        'assignee': {'type': 'string', 'description': '负责人姓名关键词'}}),
    ('query_members', '按姓名/方向查询实验室成员公开信息', False, '', {
        'q': {'type': 'string', 'description': '姓名或方向关键词'}}),
    ('query_competitions', '查询比赛安排（可按状态筛）', False, '', {
        'status': {'type': 'string', 'description': '未开放/报名中/进行中/已结束'}}),
    ('checkin_status', '查询某人今天是否已打卡', False, '', {
        'name': {'type': 'string', 'description': '成员姓名'}}),
    ('create_task', '创建任务（写操作，需用户确认）', True, 'action:task.create', {
        'title': {'type': 'string', 'description': '任务标题'},
        'description': {'type': 'string', 'description': '任务描述'},
        'priority': {'type': 'string', 'description': 'low/normal/high/urgent'},
        'assigneeId': {'type': 'string', 'description': '负责人成员编号（m 开头，如 m3，可先调用 query_members 查询后再填）'},
        'due': {'type': 'string', 'description': '截止时间，如 2026-10-08 18:00'}}),
    ('remember', '记住我的偏好/信息（个人记忆，写操作）', True, '', {
        'key': {'type': 'string', 'description': '记忆标签，如 direction'},
        'value': {'type': 'string', 'description': '记忆内容，如 STM32/ROS'}}),
    ('forget', '删除一条个人记忆（写操作）', True, '', {
        'key': {'type': 'string', 'description': '要删除的记忆标签'}}),
]

OPERATE_KEY = 'action:agent.operate'


def toolspec_for(user):
    """按当前用户权限过滤工具（写工具额外要求 action:agent.operate）。"""
    out = []
    for name, desc, write, perm, props in TOOL_BUILDERS:
        if write:
            if not rbac_can(user, OPERATE_KEY):
                continue
            if perm and not rbac_can(user, perm):
                continue
        out.append({'type': 'function', 'function': {
            'name': name, 'description': desc,
            'parameters': {'type': 'object', 'properties': props, 'required': []}}})
    return out


SYSTEM_PROMPT = (
    '你是"具身智能实验室"的管理助手。可以调用工具查询实时数据（成员/模块/借用/任务/比赛/打卡）并给出简洁可行动的建议。'
    '你还可以为用户创建任务、记录个人记忆，但这些写操作需要用户在前端确认后才会真正执行；'
    '当写工具返回"等待用户确认"时，请明确告诉用户需要点击确认。'
    '涉及借用/请假等流程请引导用户去对应页面操作。'
)


def _memory_prompt(user):
    from apps.agent.models import UserMemory
    mem = UserMemory.objects.filter(user=user).order_by('-updated')[:20]
    if not mem:
        return ''
    lines = [f'- {m.key}: {m.value[:80]}' for m in mem]
    return '\n用户个人记忆（供对话参考，可被 remember/forget 工具维护）：\n' + '\n'.join(lines)


def _llm_config():
    key = settings.LAB_LLM_API_KEY
    return {
        'key': key,
        'base': settings.LAB_LLM_BASE_URL.rstrip('/'),
        'model': settings.LAB_LLM_MODEL,
    }


def llm_ready():
    return bool(_llm_config()['key'])


def _member_name(user):
    prof = getattr(user, 'member_profile', None)
    return prof.name if prof else (user.username if user else '')


def _run_read_tool(name, args):
    from django.utils import timezone
    from apps.accounts.models import MemberProfile
    from apps.inventory.models import Asset, Loan
    from apps.tasksapp.models import Task

    if name == 'get_stats':
        assets = Asset.objects.exclude(status=Asset.STATUS_RETIRED)
        overdue = Loan.objects.filter(status__in=(Loan.STATUS_IN_USE, Loan.STATUS_RETURNING),
                                      due__lt=timezone.now()).count()
        return {'成员数': MemberProfile.objects.filter(active=True).count(),
                '模块总数': assets.count(),
                '空闲': assets.filter(status=Asset.STATUS_FREE).count(),
                '使用中': assets.filter(status=Asset.STATUS_IN_USE).count(),
                '维修中': assets.filter(status=Asset.STATUS_REPAIR).count(),
                '进行中任务': Task.objects.filter(status=Task.STATUS_DOING).count(),
                '逾期借用': overdue}

    if name == 'query_assets':
        qs = Asset.objects.all()
        if args.get('q'):
            qs = qs.filter(name__icontains=args['q'])
        if args.get('status'):
            qs = qs.filter(status=args['status'])
        return [{'编号': a.id, '名称': a.name, '类别': a.category, '位置': a.location, '状态': a.status}
                for a in qs[:15]]

    if name == 'query_loans':
        qs = Loan.objects.all()
        if args.get('status'):
            qs = qs.filter(status=args['status'])
        return [{'单号': l.id, '借用人': _member_name(l.member), '状态': l.status,
                 '预计归还': str(l.due)[:16]} for l in qs[:15]]

    if name == 'query_tasks':
        qs = Task.objects.all()
        if args.get('status'):
            qs = qs.filter(status=args['status'])
        if args.get('assignee'):
            qs = qs.filter(assignee__member_profile__name__icontains=args['assignee'])
        return [{'编号': t.id, '标题': t.title, '看板列': t.status, '负责人': _member_name(t.assignee)}
                for t in qs[:15]]

    if name == 'query_members':
        qs = MemberProfile.objects.filter(active=True)
        if args.get('q'):
            qs = qs.filter(name__icontains=args['q']) | qs.filter(direction__icontains=args['q'])
        return [{'姓名': m.name, '方向': m.direction, '状态': m.base_status} for m in qs[:15]]

    if name == 'query_competitions':
        from apps.competitions.models import Competition
        qs = Competition.objects.filter(archived=False)
        return [{'名称': c.name, '级别': c.level, '报名截止': str(c.registration_end)[:16],
                 '开赛': str(c.start)[:16]} for c in qs[:10]]

    if name == 'checkin_status':
        from apps.checkins.models import CheckInRecord
        from django.utils import timezone
        prof = MemberProfile.objects.filter(active=True, name__icontains=args.get('name', '')).first()
        if not prof:
            return {'结果': '未找到该成员'}
        today = timezone.localdate()
        checked = CheckInRecord.objects.filter(user=prof.user, created__date=today).exists()
        return {'成员': prof.name, '今天是否打卡': '已打卡' if checked else '未打卡'}

    return {'error': '未知工具'}


def _pending_summary(conversation):
    op = conversation.pending_op
    if not op:
        return None
    return {'name': op.get('name'), 'summary': op.get('summary', ''), 'args': op.get('args', {})}


def _run_tool(user, conversation, name, args):
    from apps.common.response import fail
    from apps.tasksapp.api import _validate_task

    if name in ('remember', 'forget'):
        from apps.agent.models import UserMemory
        if name == 'remember':
            key = str(args.get('key', ''))[:64].strip()
            value = str(args.get('value', ''))[:2000].strip()
            if not key or not value:
                return {'result': '记忆的标签和内容不能为空'}
            UserMemory.objects.update_or_create(user=user, key=key, defaults={'value': value})
            from apps.accounts.models import OperationLog
            OperationLog.objects.create(actor=user, text=f'智能体记录记忆 · {key}')
            return {'result': f'已记住：{key} = {value[:50]}'}
        deleted, _ = UserMemory.objects.filter(user=user, key=str(args.get('key', ''))[:64]).delete()
        return {'result': '已删除该条记忆' if deleted else '没有这条记忆'}

    if name == 'create_task':
        if conversation.pending_op:
            return {'result': f'当前已有待确认操作，请先处理后再试：{conversation.pending_op.get("summary", "")}'}
        title = str(args.get('title', '')).strip()
        if not title:
            return {'result': '任务标题不能为空'}
        from apps.accounts.models import OperationLog
        conversation.pending_op = {
            'name': 'create_task', 'args': args,
            'summary': f'创建任务《{title[:30]}》',
        }
        conversation.save(update_fields=['pending_op'])
        return {'result': '该写操作已暂存并等待用户确认。请回复用户请在前端点击"确认执行"按钮，确认后系统将自动执行。'}

    # 只读工具直接执行
    return _run_read_tool(name, args)


def execute_pending_op(user, conversation):
    """确认后执行暂存写操作（再次校验权限），返回 (op, result, error)。"""
    op = conversation.pending_op
    if not op:
        return None, '', '当前没有待确认的操作'
    if not rbac_can(user, OPERATE_KEY):
        return op, '', '你没有智能体代操作的权限'

    name = op.get('name')
    try:
        if name == 'create_task':
            if not rbac_can(user, 'action:task.create'):
                return op, '', '你没有创建任务的权限'
            from apps.tasksapp.api import _validate_task
            from apps.tasksapp.models import Task
            from apps.common.ids import create_with_code
            fields, err = _validate_task(op.get('args') or {})
            if err is not None:
                return op, '', str(getattr(err, 'data', {}).get('message', '参数不合法'))
            task = create_with_code(Task, 'TASK', creator=user, **fields)
            from apps.accounts.models import OperationLog
            OperationLog.objects.create(actor=user, text=f'智能体代建任务 · {task.id} {task.title[:30]}')
            result = f'已创建任务 {task.id}「{task.title}」，可在任务看板查看。'
        else:
            return op, '', f'不支持的操作：{name}'
    except Exception as exc:  # noqa: BLE001
        conversation.pending_op = None
        conversation.save(update_fields=['pending_op'])
        return op, '', f'执行失败：{exc}'

    conversation.pending_op = None
    conversation.save(update_fields=['pending_op'])
    return op, result, ''


def chat(conversation, user_message, user):
    """执行一轮对话（含最多 4 轮工具调用），返回 (reply, pending_op)。"""
    cfg = _llm_config()
    if not cfg['key']:
        raise RuntimeError('未配置 LAB_LLM_API_KEY')

    from apps.agent.models import AgentMessage
    msgs = list(conversation.messages.exclude(role='tool').order_by('created'))
    history = [
        {'role': m.role, 'content': m.content}
        for m in msgs[-20:]
    ]
    system = SYSTEM_PROMPT + _memory_prompt(user)
    messages = [{'role': 'system', 'content': system}] + history
    tools = toolspec_for(user)

    reply = ''
    for _ in range(4):
        resp = requests.post(
            f"{cfg['base']}/chat/completions",
            headers={'Authorization': f"Bearer {cfg['key']}"},
            json={'model': cfg['model'], 'messages': messages, 'tools': tools} if tools else
                 {'model': cfg['model'], 'messages': messages},
            timeout=cfg.get('timeout', 60))
        resp.raise_for_status()
        msg = resp.json()['choices'][0]['message']
        if msg.get('tool_calls'):
            messages.append(msg)
            for tc in msg['tool_calls']:
                fn = tc['function']['name']
                try:
                    result = _run_tool(user, conversation, fn, json.loads(tc['function'].get('arguments') or '{}'))
                except Exception as e:  # 工具失败不中断对话
                    result = {'error': str(e)}
                AgentMessage.objects.create(conversation=conversation, role='tool',
                                            tool_name=fn, content=json.dumps(result, ensure_ascii=False))
                messages.append({'role': 'tool', 'tool_call_id': tc['id'],
                                 'content': json.dumps(result, ensure_ascii=False)})
            continue
        reply = msg.get('content') or ''
        break

    return reply or '（无回复）', _pending_summary(conversation)