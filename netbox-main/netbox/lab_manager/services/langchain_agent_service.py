from __future__ import annotations

import json
from typing import Any

from netbox.plugins.utils import get_plugin_config

from .backend_agent_service import BackendAgentResponse, BackendAgentService
from .platform_data_service import PlatformDataError, PlatformDataService


class LangChainAgentService:
    """LangChain-backed tool agent for the lab manager assistant.

    Tools are loaded dynamically from the AgentTool model (is_enabled=True),
    enabling modular tool management from the admin UI.
    """

    def __init__(self, *, plugin_name: str = 'lab_manager') -> None:
        self.plugin_name = plugin_name
        self.platform = PlatformDataService()
        self.backend = BackendAgentService()

    # ── 公开 API ──────────────────────────────────────────────

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

    # ── Agent 构建（动态加载工具） ─────────────────────────────

    def _build_agent(self, *, user):
        from langchain.agents import create_agent
        from langchain_core.tools import StructuredTool
        from langchain_openai import ChatOpenAI

        base_url = self._get_config('langchain_base_url', self._get_config('openai_base_url', None)) or None
        model = ChatOpenAI(
            model=str(self._get_config('langchain_model', self._get_config('openai_model', 'gpt-4o-mini'))),
            api_key=str(self._get_config('langchain_api_key', self._get_config('openai_api_key', ''))),
            base_url=base_url,
            temperature=float(self._get_config('langchain_temperature', 0.1)),
            timeout=int(self._get_config('langchain_timeout', 60)),
        )

        enabled_tools = self._load_enabled_tools()
        langchain_tools = [
            self._build_dynamic_tool(tool_def, user) for tool_def in enabled_tools
        ]

        return create_agent(
            model=model,
            tools=langchain_tools,
            system_prompt=self._build_system_prompt(),
        )

    def _load_enabled_tools(self) -> list[dict[str, Any]]:
        """从数据库加载所有已启用的工具定义。"""
        try:
            from ..models import AgentTool
            qs = AgentTool.objects.filter(is_enabled=True).order_by('sort_order', 'name')
            tools = []
            for t in qs:
                tools.append({
                    'name': t.name,
                    'display_name': t.display_name or t.name,
                    'description': t.description,
                    'tool_type': t.tool_type,
                    'execution_key': t.effective_execution_key,
                    'default_args': t.default_args or {},
                    'requires_superuser': t.requires_superuser,
                    'parameters_schema': t.parameters_schema or {},
                })
            # 如果数据库为空，返回默认工具集
            if not tools:
                tools = self._get_fallback_tools()
            return tools
        except Exception:
            return self._get_fallback_tools()

    @staticmethod
    def _get_fallback_tools() -> list[dict[str, Any]]:
        """数据库不可用或没有记录时的默认工具集。"""
        return [
            {
                'name': 'list_records', 'display_name': '列表查询',
                'description': 'List records from a whitelisted lab platform model. '
                               'Args: model (str), filters_json (str, optional JSON), '
                               'fields_json (str, optional JSON array), limit (int, default 20)',
                'tool_type': 'platform_query', 'execution_key': 'platform_query',
                'default_args': {'action': 'list_records'},
                'requires_superuser': False, 'parameters_schema': {},
            },
            {
                'name': 'count_records', 'display_name': '计数查询',
                'description': 'Count records from a whitelisted lab platform model. '
                               'Args: model (str), filters_json (str, optional JSON)',
                'tool_type': 'platform_query', 'execution_key': 'platform_query',
                'default_args': {'action': 'count_records'},
                'requires_superuser': False, 'parameters_schema': {},
            },
            {
                'name': 'get_record_detail', 'display_name': '记录详情',
                'description': 'Get one whitelisted lab platform record by id. '
                               'Args: model (str), record_id (int), fields_json (str, optional JSON array)',
                'tool_type': 'platform_query', 'execution_key': 'platform_query',
                'default_args': {'action': 'get_record_detail'},
                'requires_superuser': False, 'parameters_schema': {},
            },
            {
                'name': 'search_records', 'display_name': '关键字搜索',
                'description': 'Search records from a whitelisted lab platform model by keyword. '
                               'Args: model (str), keyword (str), fields_json (str, optional JSON array), limit (int, default 20)',
                'tool_type': 'platform_query', 'execution_key': 'platform_query',
                'default_args': {'action': 'search_records'},
                'requires_superuser': False, 'parameters_schema': {},
            },
            {
                'name': 'describe_platform_data', 'display_name': '数据模型描述',
                'description': 'Describe all platform data models and whitelisted fields available to the agent. No arguments needed.',
                'tool_type': 'describe_data', 'execution_key': 'describe_data',
                'default_args': {}, 'requires_superuser': False, 'parameters_schema': {},
            },
            {
                'name': 'find_task_videos', 'display_name': '视频检索',
                'description': 'Find video attachments from tasks using natural-language conditions. '
                               'Args: query (str)',
                'tool_type': 'video_search', 'execution_key': 'video_search',
                'default_args': {}, 'requires_superuser': False, 'parameters_schema': {},
            },
            {
                'name': 'analyze_hardware_gap', 'display_name': '硬件缺口分析',
                'description': 'Analyze missing hardware for a lab project based on current inventory. '
                               'Args: project_description (str)',
                'tool_type': 'hardware_gap', 'execution_key': 'hardware_gap',
                'default_args': {}, 'requires_superuser': False, 'parameters_schema': {},
            },
            {
                'name': 'create_task', 'display_name': '创建任务',
                'description': '当用户要求管理员创建/布置/安排/派发任务时调用本工具。\n'
                               '参数：title(任务标题,必填), assigned_to(执行人用户名,必填), '
                               'description(详细描述), deadline(截止日期), priority(优先级: urgent/high/medium/low, 默认medium)',
                'tool_type': 'task_create', 'execution_key': 'task_create',
                'default_args': {}, 'requires_superuser': True, 'parameters_schema': {},
            },
        ]

    def _build_dynamic_tool(self, tool_def: dict, user):
        """根据工具定义动态创建一个 LangChain StructuredTool。"""
        from langchain_core.tools import StructuredTool

        execution_key = tool_def['execution_key']
        default_args = tool_def['default_args'].copy()
        tool_name = tool_def['name']
        tool_desc = tool_def['description']
        requires_superuser = tool_def.get('requires_superuser', False)

        def tool_func(**kwargs) -> str:
            # 合并默认参数 + LLM 传入参数（LLM 参数优先）
            merged_args = {**default_args, **kwargs}
            if requires_superuser and not user.is_superuser:
                return json.dumps(
                    {'ok': False, 'error': '只有管理员可以使用此工具'},
                    ensure_ascii=False,
                )
            from .tool_registry import execute_tool
            return execute_tool(execution_key, user, merged_args)

        # 构建函数签名（参数名来自 parameters_schema 或默认推断）
        from pydantic import BaseModel, create_model
        from typing import Optional

        param_schema = tool_def.get('parameters_schema') or {}
        if param_schema:
            fields = {}
            for pname, pdef in param_schema.items():
                ptype = str
                if pdef.get('type') == 'integer':
                    ptype = int
                elif pdef.get('type') == 'number':
                    ptype = float
                elif pdef.get('type') == 'boolean':
                    ptype = bool
                default_val = pdef.get('default', None)
                if default_val is not None:
                    fields[pname] = (ptype, default_val)
                else:
                    fields[pname] = (Optional[ptype], None)
            if fields:
                try:
                    args_schema = create_model(f'{tool_name}_args', **fields)
                except Exception:
                    args_schema = create_model(f'{tool_name}_args', __base__=BaseModel)
            else:
                # pydantic v2 要求至少一个字段，加占位 message 字段
                args_schema = create_model(f'{tool_name}_args', message=(Optional[str], None))
        else:
            # 无显式 schema 时提供默认 message 参数
            args_schema = create_model(f'{tool_name}_args', message=(Optional[str], None))

        return StructuredTool(
            name=tool_name,
            description=tool_desc,
            func=tool_func,
            args_schema=args_schema,
        )

    def _build_system_prompt(self) -> str:
        """动态构建系统提示，包含所有已启用工具的描述。"""
        tools = self._load_enabled_tools()
        tool_lines = []
        for t in tools:
            tag = ' [仅管理员]' if t.get('requires_superuser') else ''
            tool_lines.append(f'  - {t["name"]}: {t["display_name"]}{tag}')
        tool_list = '\n'.join(tool_lines)

        return (
            '你是实验室平台智能体助手。你的职责是理解用户自然语言需求，主动调用工具读取或修改平台真实数据，'
            '再把结果总结成清晰中文。\n\n'
            '当前可用的工具：\n'
            f'{tool_list}\n\n'
            '重要规则：\n'
            '1. 不要声称自己无法访问后台、数据库或系统；你必须先尝试调用工具。\n'
            '2. 只能通过工具查询或创建数据，不能编造人员、任务、硬件或附件。\n'
            '3. 平台模型包括 hardware、hardware_approval、task、task_attachment、checkin、member_open_record、user。\n'
            '4. 用户问项目缺什么硬件、采购建议时，使用 analyze_hardware_gap。\n'
            '5. 用户说"他/这个人/该用户/这个任务"时，结合最近会话上下文解析引用。\n'
            '6. 如果查询为空，要说明你查询的条件，并给出可放宽的条件。\n'
            '7. 用户要求创建任务时，必须调用 create_task 工具。'
        )

    # ── 辅助方法 ──────────────────────────────────────────────

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

    # ── 静态工具方法 ──────────────────────────────────────────

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
