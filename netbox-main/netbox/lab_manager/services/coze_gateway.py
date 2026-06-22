from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import requests

from netbox.plugins.utils import get_plugin_config

DEFAULT_COZE_API_BASE_URL = 'https://api.coze.cn'
DEFAULT_COZE_SITE_BASE_URL = ''
DEFAULT_COZE_CONNECTOR_ID = '1024'
DEFAULT_COZE_TIMEOUT = 60


@dataclass(slots=True)
class CozeGatewayResponse:
    status_code: int
    payload: dict[str, Any]
    request_id: str | None = None
    execute_id: str | None = None
    debug_url: str | None = None


class CozeGatewayError(Exception):
    """扣子网关基础异常。"""


class CozeGatewayConfigError(CozeGatewayError):
    """扣子配置缺失或不合法。"""


class CozeGatewayRequestError(CozeGatewayError):
    """扣子请求失败。"""


class CozeGateway:
    """
    对扣子能力的轻量封装。

    当前版本聚焦两个最常用能力：
    1. 发起 Bot 对话（OpenAPI）
    2. 执行已发布工作流（优先支持 coze.site 直连）

    建议在 `PLUGINS_CONFIG['lab_manager']` 中配置：
    - `coze_pat_token`
    - `coze_site_base_url` 或 `coze_api_base_url`
    - `coze_bot_id`（仅 Bot 对话模式需要）
    - `coze_workflow_ids`（仅 OpenAPI 工作流模式需要）
    - `coze_timeout`
    """

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        plugin_name: str = 'lab_manager',
    ) -> None:
        self.plugin_name = plugin_name
        self.session = session or requests.Session()
        self.api_base_url = self._get_config('coze_api_base_url', DEFAULT_COZE_API_BASE_URL)
        self.site_base_url = str(self._get_config('coze_site_base_url', DEFAULT_COZE_SITE_BASE_URL) or '').strip()
        self.timeout = int(self._get_config('coze_timeout', DEFAULT_COZE_TIMEOUT))

    def _get_config(self, key: str, default: Any = None) -> Any:
        return get_plugin_config(self.plugin_name, key, default)

    def _get_required_config(self, key: str) -> Any:
        value = self._get_config(key)
        if value in (None, ''):
            raise CozeGatewayConfigError(f'缺少插件配置项: {self.plugin_name}.{key}')
        return value

    def _build_url(self, path: str) -> str:
        return f"{self.api_base_url.rstrip('/')}/{path.lstrip('/')}"

    def _build_site_url(self, path: str) -> str:
        if not self.site_base_url:
            raise CozeGatewayConfigError(f'缺少插件配置项: {self.plugin_name}.coze_site_base_url')
        return f"{self.site_base_url.rstrip('/')}/{path.lstrip('/')}"

    def _build_headers(self, token: str | None = None) -> dict[str, str]:
        access_token = token or self._get_required_config('coze_pat_token')
        return {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

    def _ensure_json_response(self, response: requests.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise CozeGatewayRequestError('扣子接口未返回合法 JSON 响应') from exc

        if response.status_code >= 400:
            message = data.get('msg') or data.get('message') or '扣子接口返回错误'
            raise CozeGatewayRequestError(f'{message} (HTTP {response.status_code})')

        code = data.get('code')
        if code not in (None, 0):
            message = data.get('msg') or data.get('message') or '扣子接口业务状态异常'
            raise CozeGatewayRequestError(f'{message} (code={code})')
        return data

    def _post(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        timeout: int | None = None,
    ) -> CozeGatewayResponse:
        try:
            response = self.session.post(
                self._build_url(path),
                headers=self._build_headers(),
                json=payload,
                timeout=timeout or self.timeout,
            )
        except requests.exceptions.RequestException as exc:
            raise CozeGatewayRequestError(f'调用扣子接口失败: {exc}') from exc

        data = self._ensure_json_response(response)

        return CozeGatewayResponse(
            status_code=response.status_code,
            payload=data,
            request_id=response.headers.get('x-tt-logid'),
            execute_id=data.get('execute_id'),
            debug_url=data.get('debug_url'),
        )

    def _get(
        self,
        path: str,
        *,
        params: dict[str, Any],
        timeout: int | None = None,
    ) -> CozeGatewayResponse:
        try:
            response = self.session.get(
                self._build_url(path),
                headers=self._build_headers(),
                params=params,
                timeout=timeout or self.timeout,
            )
        except requests.exceptions.RequestException as exc:
            raise CozeGatewayRequestError(f'调用扣子接口失败: {exc}') from exc

        data = self._ensure_json_response(response)

        return CozeGatewayResponse(
            status_code=response.status_code,
            payload=data,
            request_id=response.headers.get('x-tt-logid'),
            execute_id=data.get('execute_id'),
            debug_url=data.get('debug_url'),
        )

    def _post_site(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        timeout: int | None = None,
        stream: bool = False,
        accept: str | None = None,
    ) -> CozeGatewayResponse:
        headers = self._build_headers()
        if accept:
            headers['Accept'] = accept

        try:
            response = self.session.post(
                self._build_site_url(path),
                headers=headers,
                json=payload,
                timeout=timeout or self.timeout,
                stream=stream,
            )
        except requests.exceptions.RequestException as exc:
            raise CozeGatewayRequestError(f'调用扣子工作流失败: {exc}') from exc

        data = self._ensure_json_response(response)
        return CozeGatewayResponse(
            status_code=response.status_code,
            payload=data,
            request_id=response.headers.get('x-tt-logid'),
            execute_id=data.get('task_id') or data.get('execute_id'),
            debug_url=data.get('debug_url'),
        )

    def _get_site(
        self,
        path: str,
        *,
        timeout: int | None = None,
    ) -> CozeGatewayResponse:
        try:
            response = self.session.get(
                self._build_site_url(path),
                headers=self._build_headers(),
                timeout=timeout or self.timeout,
            )
        except requests.exceptions.RequestException as exc:
            raise CozeGatewayRequestError(f'调用扣子工作流失败: {exc}') from exc

        data = self._ensure_json_response(response)
        return CozeGatewayResponse(
            status_code=response.status_code,
            payload=data,
            request_id=response.headers.get('x-tt-logid'),
            execute_id=data.get('task_id') or data.get('execute_id'),
            debug_url=data.get('debug_url'),
        )

    @staticmethod
    def _extract_chat_identifiers(payload: dict[str, Any]) -> tuple[str | None, str | None]:
        data = payload.get('data')
        if isinstance(data, dict):
            conversation_id = data.get('conversation_id') or payload.get('conversation_id')
            chat_id = data.get('id') or data.get('chat_id') or payload.get('id')
            return (
                str(conversation_id) if conversation_id else None,
                str(chat_id) if chat_id else None,
            )

        conversation_id = payload.get('conversation_id')
        chat_id = payload.get('id') or payload.get('chat_id')
        return (
            str(conversation_id) if conversation_id else None,
            str(chat_id) if chat_id else None,
        )

    @staticmethod
    def _extract_answer_text(messages_payload: dict[str, Any]) -> str:
        data = messages_payload.get('data')
        if not isinstance(data, list):
            return ''

        answers = []
        for item in data:
            if not isinstance(item, dict):
                continue
            if item.get('role') != 'assistant':
                continue
            if item.get('type') != 'answer':
                continue
            content = item.get('content')
            if content:
                answers.append(str(content))

        return '\n'.join(answers).strip()

    def get_default_bot_id(self) -> str:
        return str(self._get_required_config('coze_bot_id'))

    def get_workflow_id(self, alias: str) -> str:
        workflow_ids = self._get_required_config('coze_workflow_ids')
        if not isinstance(workflow_ids, dict):
            raise CozeGatewayConfigError('coze_workflow_ids 必须为字典配置')

        workflow_id = workflow_ids.get(alias)
        if not workflow_id:
            raise CozeGatewayConfigError(f'未找到工作流别名: {alias}')
        return str(workflow_id)

    def has_site_workflow(self) -> bool:
        return bool(self.site_base_url)

    def has_chat_bot(self) -> bool:
        return bool(str(self._get_config('coze_bot_id', '') or '').strip())

    @staticmethod
    def _normalize_site_workflow_parameters(
        parameters: dict[str, Any] | None,
        *,
        fallback_query: str = '',
    ) -> dict[str, Any]:
        normalized = dict(parameters or {})

        if 'user_query' not in normalized:
            query = normalized.get('query') or normalized.get('message') or fallback_query
            normalized['user_query'] = str(query or '')

        if 'hardware_items_str' in normalized and not isinstance(normalized['hardware_items_str'], str):
            normalized['hardware_items_str'] = json.dumps(normalized['hardware_items_str'], ensure_ascii=False)

        # 把 intent 也加进去，让工作流如果接收的话能知道这是什么意图
        normalized.setdefault('intent', normalized.get('intent', ''))
        normalized.setdefault('hardware_items_str', '')
        normalized.setdefault('import_action', 'validate')
        normalized.setdefault('batch_id', '')
        return normalized

    @staticmethod
    def _normalize_site_workflow_payload(payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        if 'data' not in normalized:
            if 'result' in normalized:
                normalized['data'] = normalized.get('result')
            elif 'output' in normalized:
                normalized['data'] = normalized.get('output')
        return normalized

    def run_chat(
        self,
        *,
        message: str,
        user_id: str,
        bot_id: str | None = None,
        conversation_id: str | None = None,
        stream: bool = False,
        auto_save_history: bool = True,
        additional_messages: list[dict[str, Any]] | None = None,
        custom_variables: dict[str, Any] | None = None,
    ) -> CozeGatewayResponse:
        if not message.strip():
            raise CozeGatewayRequestError('message 不能为空')

        payload: dict[str, Any] = {
            'bot_id': bot_id or self.get_default_bot_id(),
            'user_id': str(user_id),
            'stream': stream,
            'auto_save_history': auto_save_history,
            'additional_messages': additional_messages or [
                {
                    'role': 'user',
                    'content': message,
                    'content_type': 'text',
                }
            ],
        }

        if conversation_id:
            payload['conversation_id'] = conversation_id

        if custom_variables:
            payload['custom_variables'] = custom_variables

        return self._post('/v3/chat', payload)

    def retrieve_chat(
        self,
        *,
        conversation_id: str,
        chat_id: str,
    ) -> CozeGatewayResponse:
        return self._get(
            '/v3/chat/retrieve',
            params={
                'conversation_id': conversation_id,
                'chat_id': chat_id,
            },
        )

    def list_chat_messages(
        self,
        *,
        conversation_id: str,
        chat_id: str,
    ) -> CozeGatewayResponse:
        return self._get(
            '/v3/chat/message/list',
            params={
                'conversation_id': conversation_id,
                'chat_id': chat_id,
            },
        )

    def run_chat_and_wait_answer(
        self,
        *,
        message: str,
        user_id: str,
        bot_id: str | None = None,
        conversation_id: str | None = None,
        max_attempts: int = 15,
        poll_interval_seconds: float = 1.0,
    ) -> dict[str, Any]:
        chat_response = self.run_chat(
            message=message,
            user_id=user_id,
            bot_id=bot_id,
            conversation_id=conversation_id,
            stream=False,
            auto_save_history=True,
        )
        resolved_conversation_id, chat_id = self._extract_chat_identifiers(chat_response.payload)
        if not resolved_conversation_id or not chat_id:
            raise CozeGatewayRequestError('未能从扣子响应中提取 conversation_id/chat_id')

        status = None
        retrieve_payload: dict[str, Any] = {}
        for _attempt in range(max_attempts):
            retrieve_response = self.retrieve_chat(
                conversation_id=resolved_conversation_id,
                chat_id=chat_id,
            )
            retrieve_payload = retrieve_response.payload
            data = retrieve_payload.get('data') or {}
            if isinstance(data, dict):
                status = data.get('status')
            if status == 'completed':
                break
            time.sleep(poll_interval_seconds)

        messages_response = self.list_chat_messages(
            conversation_id=resolved_conversation_id,
            chat_id=chat_id,
        )
        answer_text = self._extract_answer_text(messages_response.payload)

        return {
            'conversation_id': resolved_conversation_id,
            'chat_id': chat_id,
            'status': status,
            'answer_text': answer_text,
            'chat_payload': chat_response.payload,
            'retrieve_payload': retrieve_payload,
            'messages_payload': messages_response.payload,
        }

    def run_workflow(
        self,
        *,
        workflow_id: str | None = None,
        workflow_alias: str | None = None,
        parameters: dict[str, Any] | None = None,
        user_id: str | None = None,
        bot_id: str | None = None,
        app_id: str | None = None,
        connector_id: str | None = None,
        is_async: bool = False,
        workflow_version: str | None = None,
        ext: dict[str, str] | None = None,
    ) -> CozeGatewayResponse:
        if self.has_site_workflow():
            normalized_parameters = self._normalize_site_workflow_parameters(parameters)
            site_path = '/async_run' if is_async else '/run'
            site_response = self._post_site(site_path, normalized_parameters)
            normalized_payload = self._normalize_site_workflow_payload(site_response.payload)
            return CozeGatewayResponse(
                status_code=site_response.status_code,
                payload=normalized_payload,
                request_id=site_response.request_id,
                execute_id=site_response.execute_id,
                debug_url=site_response.debug_url,
            )

        resolved_workflow_id = workflow_id
        if not resolved_workflow_id and workflow_alias:
            resolved_workflow_id = self.get_workflow_id(workflow_alias)
        if not resolved_workflow_id:
            raise CozeGatewayRequestError('workflow_id 或 workflow_alias 必须提供一个')

        resolved_ext = dict(ext or {})
        if user_id:
            resolved_ext.setdefault('user_id', str(user_id))

        payload: dict[str, Any] = {
            'workflow_id': str(resolved_workflow_id),
            'parameters': json.dumps(parameters or {}, ensure_ascii=False),
            'is_async': is_async,
            'connector_id': connector_id or DEFAULT_COZE_CONNECTOR_ID,
        }

        if bot_id:
            payload['bot_id'] = str(bot_id)
        if app_id:
            payload['app_id'] = str(app_id)
        if workflow_version:
            payload['workflow_version'] = workflow_version
        if resolved_ext:
            payload['ext'] = resolved_ext

        return self._post('/v1/workflow/run', payload)

    def run_workflow_stream(
        self,
        *,
        parameters: dict[str, Any] | None = None,
    ) -> CozeGatewayResponse:
        normalized_parameters = self._normalize_site_workflow_parameters(parameters)
        site_response = self._post_site(
            '/stream_run',
            normalized_parameters,
            stream=False,
            accept='text/event-stream',
        )
        normalized_payload = self._normalize_site_workflow_payload(site_response.payload)
        return CozeGatewayResponse(
            status_code=site_response.status_code,
            payload=normalized_payload,
            request_id=site_response.request_id,
            execute_id=site_response.execute_id,
            debug_url=site_response.debug_url,
        )

    def run_workflow_async(
        self,
        *,
        parameters: dict[str, Any] | None = None,
    ) -> CozeGatewayResponse:
        return self.run_workflow(parameters=parameters, is_async=True)

    def retrieve_workflow_task(self, task_id: str) -> CozeGatewayResponse:
        if not str(task_id).strip():
            raise CozeGatewayRequestError('task_id 不能为空')
        return self._get_site(f'/task/{task_id}')

    def get_workflow_schema(self) -> CozeGatewayResponse:
        return self._get_site('/graph_parameter')
