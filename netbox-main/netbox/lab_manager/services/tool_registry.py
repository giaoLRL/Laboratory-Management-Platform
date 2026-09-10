"""工具执行注册表——将 tool_type / execution_key 映射到实际执行函数。

每个执行函数签名：
    handler(user, args: dict) -> str   (返回 JSON 字符串)

添加新工具时，在此处注册执行函数，然后在管理界面创建对应的 AgentTool 记录即可。
"""
from __future__ import annotations

import json
import time
from typing import Any, Callable

from django.contrib.auth import get_user_model
from django.db.models import Q

from ..logging_config import logger

# LLM 按 AgentTool.parameters_schema 传参时用的是 filters_json / fields_json /
# record_id，而执行层读的是 filters / fields / id。这里统一归一化，
# 否则过滤条件会被静默丢弃，模型会把全量数据当成筛选结果。
_ARG_ALIASES = (('filters_json', 'filters'), ('fields_json', 'fields'), ('record_id', 'id'))


def normalize_platform_args(args: dict) -> tuple[dict, str]:
    """返回 (归一化后的参数, 错误信息)。"""
    if not isinstance(args, dict):
        return {}, '工具参数必须是对象'
    normalized = dict(args)
    for src_key, dst_key in _ARG_ALIASES:
        if src_key not in normalized:
            continue
        value = normalized.pop(src_key)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                return {}, f'{src_key} 不是合法 JSON'
        if dst_key not in normalized and value is not None:
            normalized[dst_key] = value
    return normalized, ''


# ── 工具执行函数 ──────────────────────────────────────────────

def _exec_platform_query(user, args: dict) -> str:
    """平台数据查询——最常用的通用工具"""
    from .platform_data_service import PlatformDataError, PlatformDataService
    args, arg_error = normalize_platform_args(args)
    if arg_error:
        return json.dumps({'ok': False, 'error': arg_error}, ensure_ascii=False)
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


def _exec_image_search(user, args: dict) -> str:
    """搜索任务图片附件"""
    from .backend_agent_service import BackendAgentService
    backend = BackendAgentService()
    query = str(args.get('query', args.get('message', '')))
    result = backend._search_task_images(user, query)
    return json.dumps(result, ensure_ascii=False, default=str)


def _exec_find_members(user, args: dict) -> str:
    """搜索平台成员（只返回启用账号；邮箱仅管理员可见）"""
    keyword = str(args.get('keyword', '')).strip()
    User = get_user_model()
    queryset = User.objects.filter(is_active=True)
    if keyword:
        queryset = queryset.filter(
            Q(username__icontains=keyword) | Q(email__icontains=keyword)
            | Q(first_name__icontains=keyword) | Q(last_name__icontains=keyword)
        )
    fields = ('id', 'username', 'email') if user.is_superuser else ('id', 'username')
    members = list(queryset.values(*fields).order_by('username')[:20])
    return json.dumps({'ok': True, 'members': members, 'total': len(members)},
                      ensure_ascii=False, default=str)


# ── 注册表 ────────────────────────────────────────────────────

# execution_key -> handler
TOOL_REGISTRY: dict[str, Callable] = {
    'platform_query': _exec_platform_query,
    'describe_data': _exec_describe_data,
    'task_create': _exec_task_create,
    'video_search': _exec_video_search,
    'image_search': _exec_image_search,
    'hardware_gap': _exec_hardware_gap,
    'find_members': _exec_find_members,
}


def tool_requires_superuser(execution_key: str) -> bool:
    """从数据库读取该执行标识是否要求超级管理员（LangChain 与降级路径统一生效）。"""
    try:
        from ..models import AgentTool
        return bool(
            AgentTool.objects.filter(is_enabled=True).filter(
                Q(execution_key=execution_key) | Q(execution_key='', name=execution_key)
            ).values_list('requires_superuser', flat=True).first()
        )
    except Exception:  # noqa: BLE001
        return False


def execute_tool(execution_key: str, user, args: dict[str, Any]) -> str:
    """根据执行标识调用对应的工具处理函数。"""
    handler = TOOL_REGISTRY.get(execution_key)
    if handler is None:
        return json.dumps(
            {'ok': False, 'error': f'未知工具执行标识: {execution_key}'},
            ensure_ascii=False,
        )
    if tool_requires_superuser(execution_key) and not getattr(user, 'is_superuser', False):
        return json.dumps(
            {'ok': False, 'error': '该工具仅限管理员使用'},
            ensure_ascii=False,
        )
    started = time.monotonic()
    try:
        result = handler(user, args)
        elapsed = time.monotonic() - started
        if elapsed > 10:
            logger.warning('工具 %s 执行耗时 %.1fs', execution_key, elapsed)
        return result
    except Exception as exc:
        logger.exception('工具 %s 执行异常', execution_key)
        return json.dumps(
            {'ok': False, 'error': f'工具执行异常: {exc}'},
            ensure_ascii=False,
        )


def get_registered_keys() -> list[str]:
    """返回所有已注册的执行 key 列表。"""
    return sorted(TOOL_REGISTRY.keys())
