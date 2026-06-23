from __future__ import annotations

import json
from typing import Any

from netbox.plugins.utils import get_plugin_config

from .backend_agent_service import BackendAgentResponse, BackendAgentService
from .platform_data_service import PlatformDataError, PlatformDataService


class LangChainAgentService:
    """LangChain-backed tool agent for the lab manager assistant.

    LangChain owns the model/tool loop. The tools themselves still call the
    existing permission-aware platform services, so the LLM never receives raw
    database access.
    """

    def __init__(self, *, plugin_name: str = 'lab_manager') -> None:
        self.plugin_name = plugin_name
        self.platform = PlatformDataService()
        self.backend = BackendAgentService()

    def is_configured(self) -> bool:
        return bool(self._get_config('langchain_api_key') or self._get_config('openai_api_key'))

    def process_message(self, *, user, message: str, conversation=None) -> BackendAgentResponse:
        if not self.is_configured():
            return BackendAgentResponse(handled=False)

        try:
            agent = self._build_agent(user=user)
            response = agent.invoke(
                {
                    'messages': [
                        {
                            'role': 'user',
                            'content': self._build_user_prompt(message=message, conversation=conversation),
                        }
                    ]
                },
                config={'configurable': {'thread_id': f'lab-agent-{user.pk}-{getattr(conversation, "pk", "new")}'}},
            )
            answer_text = self._extract_answer(response)
            if not answer_text:
                return BackendAgentResponse(handled=False)
            return BackendAgentResponse(
                handled=True,
                intent='langchain_agent',
                answer_text=answer_text,
                data={'langchain_response': self._safe_json(response)},
                raw_payload={'intent': 'langchain_agent', 'langchain_response': self._safe_json(response)},
            )
        except Exception as exc:
            return BackendAgentResponse(
                handled=False,
                intent='langchain_agent_error',
                data={'error': str(exc)},
                raw_payload={'intent': 'langchain_agent_error', 'error': str(exc)},
            )

    def _build_agent(self, *, user):
        from langchain.agents import create_agent
        from langchain_core.tools import tool
        from langchain_openai import ChatOpenAI

        base_url = self._get_config('langchain_base_url', self._get_config('openai_base_url', None)) or None
        model = ChatOpenAI(
            model=str(self._get_config('langchain_model', self._get_config('openai_model', 'gpt-4o-mini'))),
            api_key=str(self._get_config('langchain_api_key', self._get_config('openai_api_key', ''))),
            base_url=base_url,
            temperature=float(self._get_config('langchain_temperature', 0.1)),
            timeout=int(self._get_config('langchain_timeout', 60)),
        )

        @tool
        def list_records(model: str, filters_json: str = '{}', fields_json: str = '[]', limit: int = 20) -> str:
            """List records from a whitelisted lab platform model."""
            payload = {
                'action': 'list_records',
                'model': model,
                'filters': self._parse_json_object(filters_json),
                'fields': self._parse_json_list(fields_json),
                'limit': limit,
            }
            if not payload['fields']:
                payload.pop('fields')
            return self._execute_platform_tool(user=user, payload=payload)

        @tool
        def count_records(model: str, filters_json: str = '{}') -> str:
            """Count records from a whitelisted lab platform model."""
            return self._execute_platform_tool(
                user=user,
                payload={
                    'action': 'count_records',
                    'model': model,
                    'filters': self._parse_json_object(filters_json),
                },
            )

        @tool
        def get_record_detail(model: str, record_id: int, fields_json: str = '[]') -> str:
            """Get one whitelisted lab platform record by id."""
            payload = {
                'action': 'get_record_detail',
                'model': model,
                'id': record_id,
                'fields': self._parse_json_list(fields_json),
            }
            if not payload['fields']:
                payload.pop('fields')
            return self._execute_platform_tool(user=user, payload=payload)

        @tool
        def search_records(model: str, keyword: str, fields_json: str = '[]', limit: int = 20) -> str:
            """Search records from a whitelisted lab platform model by keyword."""
            payload = {
                'action': 'search_records',
                'model': model,
                'keyword': keyword,
                'fields': self._parse_json_list(fields_json),
                'limit': limit,
            }
            if not payload['fields']:
                payload.pop('fields')
            return self._execute_platform_tool(user=user, payload=payload)

        @tool
        def describe_platform_data() -> str:
            """Describe all platform data models and whitelisted fields available to the agent."""
            return json.dumps({'models': self.platform.describe_registry()}, ensure_ascii=False, default=str)

        @tool
        def find_task_videos(query: str) -> str:
            """Find video attachments from tasks using natural-language conditions."""
            return json.dumps(self.backend._search_task_videos(user, query), ensure_ascii=False, default=str)

        @tool
        def analyze_hardware_gap(project_description: str) -> str:
            """Analyze missing hardware for a lab project based on current inventory."""
            return json.dumps(self.backend._analyze_hardware_gap(user, project_description), ensure_ascii=False, default=str)

        @tool
        def create_task(title: str, assigned_to: str, description: str = "", deadline: str = "", priority: str = "medium") -> str:
            """当用户要求管理员创建/布置/安排/派发任务时调用本工具。

参数说明：
- title: 任务标题（必填），从用户消息中提取任务名称
- assigned_to: 执行人用户名或姓名（必填），如"admin""张三"
- description: 任务详细描述，默认与标题相同
- deadline: 截止日期，如"2026-07-01""本周五""明天"，为空则不设截止
- priority: 优先级，可选 urgent/high/medium/low，默认 medium"""
            if not user.is_superuser:
                return json.dumps({'ok': False, 'error': '只有管理员可以通过智能体创建任务'}, ensure_ascii=False)
            result = self.backend._create_task_structured(
                user=user,
                title=title,
                assigned_to=assigned_to,
                description=description or title,
                deadline=deadline or '',
                priority=priority or 'medium',
            )
            return json.dumps(result, ensure_ascii=False, default=str)

        return create_agent(
            model=model,
            tools=[
                list_records,
                count_records,
                get_record_detail,
                search_records,
                describe_platform_data,
                find_task_videos,
                analyze_hardware_gap,
                create_task,
            ],
            system_prompt=self._system_prompt(),
        )

    def _execute_platform_tool(self, *, user, payload: dict[str, Any]) -> str:
        try:
            result = self.platform.execute(user=user, payload=payload)
            return json.dumps(result, ensure_ascii=False, default=str)
        except PlatformDataError as exc:
            return json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False)

    def _build_user_prompt(self, *, message: str, conversation) -> str:
        context = self._conversation_context(conversation)
        return (
            f'用户问题：{message}\n\n'
            f'最近会话上下文：{json.dumps(context, ensure_ascii=False, default=str)[:3000]}\n\n'
            '请根据问题自主选择一个或多个工具查询真实平台数据，然后用中文总结给用户。'
        )

    def _conversation_context(self, conversation) -> list[dict[str, Any]]:
        if not conversation:
            return []
        rows = []
        for msg in conversation.messages.order_by('-created')[:6]:
            rows.append(
                {
                    'role': msg.role,
                    'content': msg.content[:800],
                    'raw_payload': msg.raw_payload,
                }
            )
        return list(reversed(rows))

    @staticmethod
    def _system_prompt() -> str:
        return (
            '你是实验室平台智能体助手。你的职责是理解用户自然语言需求，主动调用工具读取或修改平台真实数据，'
            '再把结果总结成清晰中文。\n'
            '重要规则：\n'
            '1. 不要声称自己无法访问后台、数据库或系统；你必须先尝试调用工具。\n'
            '2. 只能通过工具查询或创建数据，不能编造人员、任务、硬件或附件。\n'
            '3. 平台模型包括 hardware、hardware_approval、task、task_attachment、checkin、member_open_record、user。\n'
            '4. 用户问附件、视频、任务文件时优先使用 task_attachment 或 find_task_videos。\n'
            '5. 用户问项目缺什么硬件、采购建议、做某个系统时，使用 analyze_hardware_gap。\n'
            '6. 用户说”他/这个人/该用户/这个任务”时，结合最近会话上下文解析引用。\n'
            '7. 如果查询为空，要说明你查询的条件，并给出可放宽的条件。\n'
            '8. **用户要求创建/布置/安排/派发任务时，必须调用 create_task 工具**，把用户完整消息原文传入 user_message 参数。'
        )

    @staticmethod
    def _extract_answer(response: Any) -> str:
        if isinstance(response, dict):
            messages = response.get('messages') or []
            if messages:
                last = messages[-1]
                content = getattr(last, 'content', None)
                if content:
                    return str(content)
                if isinstance(last, dict) and last.get('content'):
                    return str(last['content'])
            if response.get('output'):
                return str(response['output'])
        return ''

    @staticmethod
    def _safe_json(value: Any) -> Any:
        # 始终序列化再反序列化，确保不含不可 JSON 序列化的对象（如 LangChain Message）
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))

    @staticmethod
    def _parse_json_object(value: str) -> dict[str, Any]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _parse_json_list(value: str) -> list[Any]:
        if not value:
            return []
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []

    def _get_config(self, key: str, default: Any = None) -> Any:
        return get_plugin_config(self.plugin_name, key, default)
