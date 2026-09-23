"""LLM 智能体服务：DeepSeek（OpenAI 兼容协议）+ 实验室数据工具。

环境变量：
  LAB_LLM_API_KEY   DeepSeek API Key（未配置时接口返回提示）
  LAB_LLM_BASE_URL  默认 https://api.deepseek.com
  LAB_LLM_MODEL     默认 deepseek-chat
"""

import json

import requests
from django.conf import settings

TOOLSPEC = [
    {'type': 'function', 'function': {
        'name': 'get_stats', 'description': '获取实验室整体统计：成员数、模块数、空闲/使用中/维修中、进行中任务、逾期借用等',
        'parameters': {'type': 'object', 'properties': {}}}},
    {'type': 'function', 'function': {
        'name': 'query_assets', 'description': '按名称/类别/状态查询实验室模块（硬件设备）',
        'parameters': {'type': 'object', 'properties': {
            'q': {'type': 'string', 'description': '名称关键词'},
            'status': {'type': 'string', 'description': '空闲/使用中/维修中/报废'}},
            'required': []}}},
    {'type': 'function', 'function': {
        'name': 'query_loans', 'description': '查询借用单（可按状态筛选）',
        'parameters': {'type': 'object', 'properties': {
            'status': {'type': 'string', 'description': '待审批/已批准/使用中/归还申请中/已完成'}},
            'required': []}}},
    {'type': 'function', 'function': {
        'name': 'query_tasks', 'description': '查询任务（可按看板列与负责人筛选）',
        'parameters': {'type': 'object', 'properties': {
            'status': {'type': 'string', 'description': 'todo/doing/done'},
            'assignee': {'type': 'string', 'description': '负责人姓名关键词'}},
            'required': []}}},
    {'type': 'function', 'function': {
        'name': 'query_members', 'description': '按姓名/方向查询实验室成员公开信息',
        'parameters': {'type': 'object', 'properties': {
            'q': {'type': 'string', 'description': '姓名或方向关键词'}},
            'required': []}}},
]

SYSTEM_PROMPT = (
    '你是"具身智能实验室"的管理助手。你可以调用工具查询成员、模块（硬件设备）、借用单、任务等实时数据，'
    '回答要简洁、面向行动。涉及借用/审批等写操作时，告知用户去对应页面操作，你只负责查询与建议。'
)


def _llm_config():
    key = settings.LAB_LLM_API_KEY
    return {
        'key': key,
        'base': settings.LAB_LLM_BASE_URL.rstrip('/'),
        'model': settings.LAB_LLM_MODEL,
    }


def llm_ready():
    return bool(_llm_config()['key'])


def _run_tool(name, args):
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
            qs = qs.filter(models_q(args['q']))
        return [{'姓名': m.name, '方向': m.direction, '状态': m.base_status} for m in qs[:15]]

    return {'error': '未知工具'}


def models_q(keyword):
    from django.db.models import Q
    return Q(name__icontains=keyword) | Q(direction__icontains=keyword)


def _member_name(user):
    prof = getattr(user, 'member_profile', None)
    return prof.name if prof else (user.username if user else '')


def chat(conversation, user_message):
    """执行一轮对话（含最多 4 轮工具调用），返回助手回复文本。"""
    cfg = _llm_config()
    if not cfg['key']:
        raise RuntimeError('未配置 LAB_LLM_API_KEY')

    from apps.agent.models import AgentMessage
    # QuerySet 不支持负数切片，取最后 20 条需先物化
    msgs = list(conversation.messages.exclude(role='tool').order_by('created'))
    history = [
        {'role': m.role, 'content': m.content}
        for m in msgs[-20:]
    ]
    # 注意：视图在调用 chat() 前已把本轮用户消息写入 conversation，
    # 因此 history 已含当前消息，无需再 append 一次（否则会发两遍）
    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}] + history

    reply = ''
    for _ in range(4):
        resp = requests.post(
            f"{cfg['base']}/chat/completions",
            headers={'Authorization': f"Bearer {cfg['key']}"},
            json={'model': cfg['model'], 'messages': messages, 'tools': TOOLSPEC},
            timeout=cfg.get('timeout', 60))
        resp.raise_for_status()
        msg = resp.json()['choices'][0]['message']
        if msg.get('tool_calls'):
            messages.append(msg)
            for tc in msg['tool_calls']:
                fn = tc['function']['name']
                try:
                    result = _run_tool(fn, json.loads(tc['function'].get('arguments') or '{}'))
                except Exception as e:  # 工具失败不中断对话
                    result = {'error': str(e)}
                AgentMessage.objects.create(conversation=conversation, role='tool',
                                            tool_name=fn, content=json.dumps(result, ensure_ascii=False))
                messages.append({'role': 'tool', 'tool_call_id': tc['id'],
                                 'content': json.dumps(result, ensure_ascii=False)})
            continue
        reply = msg.get('content') or ''
        break

    return reply or '（无回复）'
