from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .backend_agent_service import BackendAgentResponse, BackendAgentService
from .platform_data_service import PlatformDataError, PlatformDataService
from .tool_registry import execute_tool as _registry_execute


MODEL_LABELS = {
    'hardware': '硬件',
    'hardware_approval': '硬件审批',
    'task': '任务',
    'task_attachment': '任务附件',
    'checkin': '打卡记录',
    'member_open_record': '成员打卡记录',
    'user': '人员',
}


@dataclass
class AgentToolCall:
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    reason: str = ''


class AgentToolOrchestrator:
    """LLM-facing tool orchestration layer for the lab assistant.

    The assistant should reason in terms of safe tools, not direct database access.
    This class builds a tool plan, executes only whitelisted tools, then asks the
    configured chat model to summarize the trusted results when possible.
    """

    def __init__(self) -> None:
        self.platform = PlatformDataService()
        self.backend = BackendAgentService()

    def process_message(self, *, user, message: str, conversation=None) -> BackendAgentResponse:
        normalized_message = str(message or '').strip()
        if not normalized_message:
            return BackendAgentResponse(handled=False)

        context = self._build_context(conversation)
        tool_calls = self._plan_tool_calls(normalized_message, context)
        if not tool_calls:
            tool_calls = [
                AgentToolCall(
                    tool='platform.query',
                    args={'action': 'describe_registry', 'model': 'hardware'},
                    reason='说明当前智能体可读取的平台数据范围',
                )
            ]

        tool_results: list[dict[str, Any]] = []
        for call in tool_calls:
            tool_results.append(self._execute_tool_call(user=user, call=call))

        # 写操作（如 task.create）直接走本地确定性回复，避免外部 LLM 跑偏
        if any(call.tool in ('task.create',) for call in tool_calls):
            answer_text = self._summarize_locally(normalized_message, tool_results, context)
        else:
            answer_text = self._summarize_with_llm(
                user=user,
                message=normalized_message,
                tool_calls=tool_calls,
                tool_results=tool_results,
                context=context,
            )
            if not answer_text:
                answer_text = self._summarize_locally(normalized_message, tool_results, context)

        raw_payload = {
            'intent': 'agent_tools',
            'tool_calls': [
                {'tool': call.tool, 'args': call.args, 'reason': call.reason}
                for call in tool_calls
            ],
            'tool_results': tool_results,
            'context': context,
        }
        return BackendAgentResponse(
            handled=True,
            intent='agent_tools',
            answer_text=answer_text,
            data={'tool_calls': raw_payload['tool_calls'], 'tool_results': tool_results},
            raw_payload=raw_payload,
        )

    def _plan_tool_calls(self, message: str, context: dict[str, Any]) -> list[AgentToolCall]:
        message_lower = message.lower()
        referenced_user = self._resolve_referenced_user(message, context)

        if any(word in message for word in ('能查询', '可查询', '查询哪些数据', '哪些数据', '数据能力', '能读取', '可读取')):
            return [
                AgentToolCall(
                    tool='platform.query',
                    args={'action': 'describe_registry', 'model': 'hardware'},
                    reason='用户询问智能体可读取哪些平台数据',
                )
            ]

        if self._is_task_create(message):
            return [
                AgentToolCall(
                    tool='task.create',
                    args={'message': message},
                    reason='用户要求管理员通过智能体布置任务',
                )
            ]

        if self._looks_like_project_gap(message):
            return [
                AgentToolCall(
                    tool='hardware.gap_analysis',
                    args={'message': message},
                    reason='用户在描述项目或系统方案，需要结合库存分析缺口',
                )
            ]

        if self._asks_for_image(message):
            enriched_message = message
            if referenced_user and not self._message_mentions_known_user(message):
                enriched_message = f'{message} {referenced_user.get("username") or referenced_user.get("full_name")}'
            return [
                AgentToolCall(
                    tool='task.image_search',
                    args={'message': enriched_message, 'referenced_user': referenced_user or {}},
                    reason='用户要查任务图片/照片附件，使用专用图片检索工具',
                )
            ]

        if self._asks_for_video(message):
            enriched_message = message
            if referenced_user and not self._message_mentions_known_user(message):
                enriched_message = f'{message} {referenced_user.get("username") or referenced_user.get("full_name")}'
            return [
                AgentToolCall(
                    tool='task.video_search',
                    args={'message': enriched_message, 'referenced_user': referenced_user or {}},
                    reason='用户要查任务视频附件，使用专用视频检索工具',
                )
            ]

        if any(word in message for word in ('附件', '文件')) and any(word in message for word in ('任务', '上传', '材料', '资料', '列表', '查询', '查看')):
            return [
                AgentToolCall(
                    tool='platform.query',
                    args={
                        'action': 'list_records',
                        'model': 'task_attachment',
                        'fields': ('id', 'task_title', 'task_status_label', 'assigned_to_name', 'file_name', 'file_type', 'file_url', 'remark', 'uploaded_by_name', 'created'),
                        'limit': 50,
                    },
                    reason='用户要读取任务附件，直接查询附件模型',
                )
            ]

        inferred_query = self.platform.infer_query(message)
        if inferred_query:
            return [
                AgentToolCall(
                    tool='platform.query',
                    args=inferred_query,
                    reason='用户问题可映射为平台通用数据查询',
                )
            ]

        if any(word in message for word in ('打卡记录', '定位打卡', '拍照打卡', '今日打卡', '谁打卡', '打开记录', '访问记录', '浏览记录')):
            return [
                AgentToolCall(
                    tool='platform.query',
                    args={'action': 'describe_registry', 'model': 'hardware'},
                    reason='用户要读取打卡或成员打卡记录，但未形成具体查询条件',
                )
            ]

        if referenced_user and any(word in message for word in ('任务', '工作', '进度', '情况', '完成', '待办')):
            return [
                AgentToolCall(
                    tool='platform.query',
                    args={
                        'action': 'list_records',
                        'model': 'task',
                        'filters': {'assigned_to': referenced_user.get('username') or referenced_user.get('full_name')},
                        'fields': ('id', 'title', 'status_label', 'priority_label', 'assigned_to_name', 'deadline', 'completed_at', 'completion_note'),
                        'limit': 50,
                    },
                    reason='用户使用上下文代词追问上一位人员的任务',
                )
            ]

        if referenced_user and any(word in message for word in ('信息', '详情', '邮箱', '账号', '权限', '管理员')):
            return [
                AgentToolCall(
                    tool='platform.query',
                    args={
                        'action': 'get_record_detail',
                        'model': 'user',
                        'id': referenced_user.get('id'),
                        'fields': ('id', 'username', 'full_name', 'email', 'is_active', 'is_superuser', 'date_joined', 'task_total', 'task_pending', 'task_in_progress', 'task_completed'),
                    },
                    reason='用户使用上下文代词追问上一位人员详情',
                )
            ]

        if any(word in message for word in ('人员', '成员', '用户', '管理员', 'admin', '名单')):
            query: dict[str, Any] = {
                'action': 'list_records',
                'model': 'user',
                'limit': 50,
            }
            if '管理员' in message or '超级管理员' in message or 'admin' in message_lower:
                query['filters'] = {'is_superuser': True}
                query['fields'] = ('id', 'username', 'full_name', 'email', 'is_active', 'is_superuser', 'date_joined', 'task_total')
            return [
                AgentToolCall(
                    tool='platform.query',
                    args=query,
                    reason='用户要读取平台人员/管理员数据',
                )
            ]

        if any(word in message for word in ('任务', '待办', '进度', '负责人', '执行人', '完成')):
            return [
                AgentToolCall(
                    tool='platform.query',
                    args=self._build_task_query(message),
                    reason='用户要读取平台任务数据',
                )
            ]

        if any(word in message for word in ('硬件', '库存', '设备', '器材', '报废', '待审核', '待审批')):
            query = self.platform.infer_query(message) or self._build_hardware_query(message)
            return [
                AgentToolCall(
                    tool='platform.query',
                    args=query,
                    reason='用户要读取平台硬件或审批数据',
                )
            ]

        return [
            AgentToolCall(
                tool='platform.query',
                args={'action': 'describe_registry', 'model': 'hardware'},
                reason='默认先读取平台数据能力，再结合用户问题回答',
            )
        ]

    def _execute_tool_call(self, *, user, call: AgentToolCall) -> dict[str, Any]:
        """通过统一工具注册表执行工具调用。"""
        # 将旧的 tool 名称映射到注册表 execution_key
        tool_key_map = {
            'platform.query': 'platform_query',
            'task.video_search': 'video_search',
            'task.image_search': 'image_search',
            'hardware.gap_analysis': 'hardware_gap',
            'task.create': 'task_create',
        }
        try:
            execution_key = tool_key_map.get(call.tool, call.tool)
            result_json = _registry_execute(execution_key, user, call.args)
            result = json.loads(result_json)
            return {
                'tool': call.tool,
                'ok': result.get('ok', True),
                'result': result,
            }
        except (PlatformDataError, ValueError) as exc:
            return {'tool': call.tool, 'ok': False, 'error': str(exc)}
        except Exception as exc:
            return {'tool': call.tool, 'ok': False, 'error': f'工具执行失败: {exc}'}

    def _summarize_with_llm(
        self,
        *,
        user,
        message: str,
        tool_calls: list[AgentToolCall],
        tool_results: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> str:
        # 不再依赖外部平台，统一走本地格式化
        return ''

    def _summarize_locally(self, message: str, tool_results: list[dict[str, Any]], context: dict[str, Any]) -> str:
        first = tool_results[0] if tool_results else {}
        if not first.get('ok'):
            return f"我调用工具时遇到问题：{first.get('error') or '未知错误'}"

        tool = first.get('tool')
        result = first.get('result') or {}
        if tool == 'hardware.gap_analysis':
            return self.backend._format_hardware_gap_answer(result)
        if tool == 'task.video_search':
            return self.backend._format_task_video_answer(result)
        if tool == 'task.image_search':
            return self.backend._format_task_image_answer(result)
        if tool == 'task.create':
            return self.backend._format_task_create_answer(result)
        if tool == 'platform.query':
            return self._format_platform_result(result)
        return '我已经完成工具查询，但暂时没有可展示的结果。'

    def _format_platform_result(self, result: dict[str, Any]) -> str:
        if 'models' in result:
            return self.backend._format_platform_query_answer(result)

        model = result.get('model') or ''
        action = result.get('action') or ''
        label = MODEL_LABELS.get(model, model or '数据')
        items = result.get('items') or []

        if action == 'count_records':
            return f'我查到了，{label}共有 {result.get("total", 0)} 条。'

        if action == 'get_record_detail' and result.get('item'):
            return self._format_items(label, [result['item']], total=1, detail=True)

        if action == 'aggregate_records':
            rows = result.get('items') or []
            if not rows:
                return f'我调用统计工具查了 {label}，没有匹配数据。'
            lines = [f'我按你的条件统计了 {label}：']
            for row in rows[:12]:
                lines.append('- ' + self._human_join(row))
            return '\n'.join(lines)

        total = int(result.get('total') or 0)
        if not items:
            return f'我调用平台数据工具查了 {label}，没有找到匹配记录。'
        return self._format_items(label, items, total=total)

    def _format_items(self, label: str, items: list[dict[str, Any]], *, total: int, detail: bool = False) -> str:
        lines = [f'我查到了 {total} 条{label}信息，先给你整理关键内容：']
        for item in items[:8]:
            lines.append('- ' + self._human_join(item))
        if total > len(items[:8]) and not detail:
            lines.append(f'还有 {total - len(items[:8])} 条没有展开，可以继续告诉我要筛选的条件。')
        return '\n'.join(lines)

    def _human_join(self, item: dict[str, Any]) -> str:
        labels = {
            'id': 'ID',
            'username': '账号',
            'full_name': '姓名',
            'email': '邮箱',
            'is_active': '启用',
            'is_superuser': '管理员',
            'date_joined': '加入时间',
            'task_total': '任务总数',
            'task_pending': '待开始',
            'task_in_progress': '进行中',
            'task_completed': '已完成',
            'title': '任务',
            'status_label': '状态',
            'priority_label': '优先级',
            'assigned_to_name': '负责人',
            'deadline': '截止时间',
            'completed_at': '完成时间',
            'completion_note': '完成说明',
            'name': '名称',
            'category_label': '类别',
            'quantity': '数量',
            'storage_location': '位置',
            'custodian_name': '保管人',
            'approval_status_label': '审批',
            'task_title': '任务',
            'file_name': '文件',
            'file_type': '类型',
            'file_url': '链接',
            'uploaded_by_name': '上传人',
            'user_name': '成员',
            'page_title': '页面',
            'path': '路径',
            'target_type': '对象类型',
            'target_id': '对象ID',
            'ip_address': 'IP',
            'latitude': '纬度',
            'longitude': '经度',
            'accuracy': '精度',
            'address': '地址',
            'photo_url': '照片',
            'created': '创建时间',
        }
        parts = []
        for key, value in item.items():
            if value in (None, ''):
                continue
            if isinstance(value, bool):
                value = '是' if value else '否'
            parts.append(f'{labels.get(key, key)}：{value}')
        return '；'.join(parts) if parts else str(item)

    def _build_context(self, conversation) -> dict[str, Any]:
        context: dict[str, Any] = {'last_user': None, 'last_task': None, 'last_tool_results': []}
        if not conversation:
            return context

        messages = list(conversation.messages.order_by('-created')[:10])
        for message in messages:
            payload = message.raw_payload or {}
            for tool_result in payload.get('tool_results') or []:
                context['last_tool_results'].append(tool_result)
                result = tool_result.get('result') or {}
                model = result.get('model')
                items = result.get('items') or []
                item = result.get('item')
                if model == 'user' and not context['last_user']:
                    context['last_user'] = item or (items[0] if items else None)
                if model == 'task' and not context['last_task']:
                    context['last_task'] = item or (items[0] if items else None)
            if context['last_user'] and context['last_task']:
                break
        return context

    def _resolve_referenced_user(self, message: str, context: dict[str, Any]) -> dict[str, Any] | None:
        if not any(word in message for word in ('他', '她', '这个人', '此人', '该用户', '这个用户', '这个成员')):
            return None
        user = context.get('last_user')
        return user if isinstance(user, dict) else None

    @staticmethod
    def _is_task_create(message: str) -> bool:
        """检测任务创建意图，匹配"创建任务""创建一个任务""布置个任务"等变体。"""
        import re
        return bool(re.search(r'(创建|新建|布置|安排|派发|分配).{0,4}任务', message))

    @staticmethod
    def _looks_like_project_gap(message: str) -> bool:
        return any(word in message for word in ('缺什么', '缺哪些', '还缺', '采购', '购买', '方案', '做一个', '做个', '项目', '系统'))

    @staticmethod
    def _asks_for_video(message: str) -> bool:
        return any(word in message for word in ('视频', '录像', '录屏')) and any(word in message for word in ('任务', '附件', '完成', '导出', '下载', '给我', '找'))

    @staticmethod
    def _asks_for_image(message: str) -> bool:
        return any(word in message for word in ('图片', '照片', '截图', '图像', '相片')) and any(word in message for word in ('任务', '附件', '完成', '导出', '下载', '给我', '找', '看'))

    @staticmethod
    def _message_mentions_known_user(message: str) -> bool:
        return bool(BackendAgentService._find_members_in_message(message))

    def _build_task_query(self, message: str) -> dict[str, Any]:
        query: dict[str, Any] = {
            'action': 'list_records',
            'model': 'task',
            'filters': {},
            'fields': ('id', 'title', 'status_label', 'priority_label', 'assigned_to_name', 'deadline', 'completed_at', 'completion_note'),
            'limit': 50,
        }
        if '已完成' in message:
            query['filters']['status'] = 'completed'
        elif '进行中' in message:
            query['filters']['status'] = 'in_progress'
        elif any(word in message for word in ('待开始', '待办')):
            query['filters']['status'] = 'pending'
        elif '未完成' in message:
            query['filters']['status__in'] = ['pending', 'in_progress']
        member = self.platform._find_member_name(message)
        if member:
            query['filters']['assigned_to'] = member
        return query

    @staticmethod
    def _build_hardware_query(message: str) -> dict[str, Any]:
        query: dict[str, Any] = {
            'action': 'list_records',
            'model': 'hardware',
            'filters': {},
            'limit': 50,
        }
        if '闲置' in message:
            query['filters']['status'] = 'idle'
        elif '在用' in message:
            query['filters']['status'] = 'in_use'
        elif '维修' in message:
            query['filters']['status'] = 'repair'
        elif '报废' in message:
            query['filters']['status'] = 'scrapped'
        if '待审核' in message or '待审批' in message:
            query['model'] = 'hardware_approval'
            query['filters']['approval_status'] = 'pending'
        return query
