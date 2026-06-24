"""工具执行注册表——将 tool_type / execution_key 映射到实际执行函数。

每个执行函数签名：
    handler(user, args: dict) -> str   (返回 JSON 字符串)

添加新工具时，在此处注册执行函数，然后在管理界面创建对应的 AgentTool 记录即可。
"""
from __future__ import annotations

import json
from typing import Any, Callable

from django.contrib.auth import get_user_model
from django.db.models import Q

# ── 工具执行函数 ──────────────────────────────────────────────

def _exec_platform_query(user, args: dict) -> str:
    """平台数据查询——最常用的通用工具"""
    from .platform_data_service import PlatformDataError, PlatformDataService
    platform = PlatformDataService()
    try:
        result = platform.execute(user=user, payload=args)
        return json.dumps(result, ensure_ascii=False, default=str)
    except PlatformDataError as exc:
        return json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False)


def _exec_describe_data(user, args: dict) -> str:
    """描述所有可用的平台数据模型"""
    from .platform_data_service import PlatformDataService
    platform = PlatformDataService()
    return json.dumps({'models': platform.describe_registry()}, ensure_ascii=False, default=str)


def _exec_task_create(user, args: dict) -> str:
    """创建任务（管理员权限）

    支持两种模式：
    1. 结构化模式 — LLM 已提取 title/assigned_to/description/deadline/priority
    2. 消息模式 — 仅有 raw message，回退到自然语言解析
    """
    from .backend_agent_service import BackendAgentService
    backend = BackendAgentService()
    if not user.is_superuser:
        return json.dumps({'ok': False, 'error': '只有管理员可以通过智能体创建任务'}, ensure_ascii=False)

    title = str(args.get('title', '')).strip()
    message = str(args.get('message', ''))

    # 有结构化标题 → 直接创建
    if title:
        result = backend._create_task_structured(
            user=user,
            title=title,
            assigned_to=str(args.get('assigned_to', '')),
            description=str(args.get('description', title)),
            deadline=str(args.get('deadline', '')),
            priority=str(args.get('priority', 'medium')),
        )
    elif message:
        # 回退：从自然语言消息中解析任务参数
        result = backend._create_task_from_message(user, message)
    else:
        result = {'ok': False, 'error': '任务标题不能为空'}

    return json.dumps(result, ensure_ascii=False, default=str)


def _exec_video_search(user, args: dict) -> str:
    """搜索任务视频附件"""
    from .backend_agent_service import BackendAgentService
    backend = BackendAgentService()
    query = str(args.get('query', args.get('message', '')))
    result = backend._search_task_videos(user, query)
    return json.dumps(result, ensure_ascii=False, default=str)


def _exec_hardware_gap(user, args: dict) -> str:
    """分析硬件缺口"""
    from .backend_agent_service import BackendAgentService
    backend = BackendAgentService()
    project_desc = str(args.get('project_description', args.get('message', '')))
    result = backend._analyze_hardware_gap(user, project_desc)
    return json.dumps(result, ensure_ascii=False, default=str)


def _exec_find_members(user, args: dict) -> str:
    """搜索平台成员"""
    keyword = str(args.get('keyword', '')).strip()
    User = get_user_model()
    if not keyword:
        members = list(User.objects.values('id', 'username', 'email', 'is_active', 'is_superuser')[:20])
    else:
        members = list(
            User.objects.filter(
                Q(username__icontains=keyword) | Q(email__icontains=keyword)
            ).values('id', 'username', 'email', 'is_active', 'is_superuser')[:20]
        )
    return json.dumps({'ok': True, 'members': members, 'total': len(members)}, ensure_ascii=False, default=str)


# ── 注册表 ────────────────────────────────────────────────────

# execution_key -> handler
TOOL_REGISTRY: dict[str, Callable] = {
    'platform_query': _exec_platform_query,
    'describe_data': _exec_describe_data,
    'task_create': _exec_task_create,
    'video_search': _exec_video_search,
    'hardware_gap': _exec_hardware_gap,
    'find_members': _exec_find_members,
}


def execute_tool(execution_key: str, user, args: dict[str, Any]) -> str:
    """根据执行标识调用对应的工具处理函数。"""
    handler = TOOL_REGISTRY.get(execution_key)
    if handler is None:
        return json.dumps(
            {'ok': False, 'error': f'未知工具执行标识: {execution_key}'},
            ensure_ascii=False,
        )
    try:
        return handler(user, args)
    except Exception as exc:
        return json.dumps(
            {'ok': False, 'error': f'工具执行异常: {exc}'},
            ensure_ascii=False,
        )


def get_registered_keys() -> list[str]:
    """返回所有已注册的执行 key 列表。"""
    return sorted(TOOL_REGISTRY.keys())
