from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import requests

from netbox.plugins.utils import get_plugin_config

DEFAULT_DIFY_API_BASE_URL = "http://localhost"
DEFAULT_DIFY_TIMEOUT = 60


@dataclass(slots=True)
class DifyGatewayResponse:
    status_code: int
    payload: dict[str, Any]
    request_id: str | None = None
    execute_id: str | None = None
    debug_url: str | None = None


class DifyGatewayError(Exception):
    """Dify 网关基础异常。"""


class DifyGatewayConfigError(DifyGatewayError):
    """Dify 配置缺失或不合法。"""


class DifyGatewayRequestError(DifyGatewayError):
    """Dify 请求失败。"""


class DifyGateway:
    """对 Dify 能力的轻量封装，接口兼容原 CozeGateway。

    当前聚焦两个核心能力：
    1. 发起 Chat 对话（chat-messages API）
    2. 执行已发布工作流（workflows/run API）

    建议在 PLUGINS_CONFIG["lab_manager"] 中配置：
    - dify_api_base_url：Dify 服务地址（默认 http://localhost）
    - dify_api_key：Dify Chat 应用 API Key
    - dify_workflow_api_keys：{别名: api_key} 工作流 API Key 映射
    - dify_timeout
    """

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        plugin_name: str = "lab_manager",
    ) -> None:
        self.plugin_name = plugin_name
        self.session = session or requests.Session()
        self.api_base_url = str(
            self._get_config("dify_api_base_url", DEFAULT_DIFY_API_BASE_URL)
        ).rstrip("/")
        self.timeout = int(self._get_config("dify_timeout", DEFAULT_DIFY_TIMEOUT))

    def _get_config(self, key: str, default: Any = None) -> Any:
        return get_plugin_config(self.plugin_name, key, default)

    def _get_required_config(self, key: str) -> Any:
        value = self._get_config(key)
        if value in (None, ""):
            raise DifyGatewayConfigError(
                f"缺少插件配置项: {self.plugin_name}.{key}"
            )
        return value

    def _build_url(self, path: str) -> str:
        return f"{self.api_base_url}/{path.lstrip('/')}"

    def _build_headers(self, api_key: str | None = None) -> dict[str, str]:
        access_token = api_key or self._get_required_config("dify_api_key")
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    def _ensure_json_response(self, response: requests.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise DifyGatewayRequestError(
                "Dify 接口未返回合法 JSON 响应"
            ) from exc
        if response.status_code >= 400:
            message = data.get("message") or data.get("msg") or "Dify 接口返回错误"
            code = data.get("code") or ""
            raise DifyGatewayRequestError(
                f"{message} (HTTP {response.status_code}, code={code})"
            )
        return data

    def _post(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        timeout: int | None = None,
        api_key: str | None = None,
    ) -> DifyGatewayResponse:
        try:
            response = self.session.post(
                self._build_url(path),
                headers=self._build_headers(api_key=api_key),
                json=payload,
                timeout=timeout or self.timeout,
            )
        except requests.exceptions.RequestException as exc:
            raise DifyGatewayRequestError(f"调用 Dify 接口失败: {exc}") from exc
        data = self._ensure_json_response(response)
        return DifyGatewayResponse(
            status_code=response.status_code,
            payload=data,
            request_id=data.get("workflow_run_id")
            or data.get("id")
            or response.headers.get("x-request-id"),
        )

    # ── 工作流 API Key ──

    def get_workflow_api_key(self, workflow_alias: str) -> str:
        workflow_keys = self._get_config("dify_workflow_api_keys", {})
        if not isinstance(workflow_keys, dict):
            raise DifyGatewayConfigError(
                f"{self.plugin_name}.dify_workflow_api_keys 必须是一个字典"
            )
        key = workflow_keys.get(workflow_alias)
        if not key:
            raise DifyGatewayConfigError(
                f'未找到工作流别名 "{workflow_alias}" 的 Dify API Key'
            )
        return str(key)

    # ── 工作流执行 ──

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
    ) -> DifyGatewayResponse:
        """执行 Dify 工作流，兼容原 CozeGateway 调用签名。"""
        api_key = None
        if workflow_alias:
            api_key = self.get_workflow_api_key(workflow_alias)

        inputs = dict(parameters or {})
        if user_id:
            inputs.setdefault("user_id", str(user_id))

        payload: dict[str, Any] = {
            "inputs": inputs,
            "response_mode": "streaming" if is_async else "blocking",
            "user": str(user_id) if user_id else "system",
        }
        if workflow_version:
            payload["inputs"]["workflow_version"] = workflow_version

        response = self._post("/v1/workflows/run", payload, api_key=api_key)
        payload_data = response.payload

        if isinstance(payload_data.get("data"), dict):
            data_block = payload_data["data"]
            normalized_data = {
                "status": data_block.get("status", ""),
                "outputs": data_block.get("outputs", {}),
                "workflow_run_id": data_block.get("workflow_run_id", ""),
                "elapsed_time": data_block.get("elapsed_time", 0),
                "total_tokens": data_block.get("total_tokens", 0),
            }
        else:
            normalized_data = payload_data

        return DifyGatewayResponse(
            status_code=response.status_code,
            payload={
                "code": 0,
                "msg": "ok",
                "data": normalized_data,
                "execute_id": payload_data.get("workflow_run_id", ""),
                "debug_url": "",
            },
            request_id=response.request_id,
            execute_id=payload_data.get("workflow_run_id"),
        )

    # ── Chat 对话 ──

    def run_chat_and_wait_answer(
        self,
        *,
        message: str,
        user_id: str | None = None,
        conversation_id: str | None = None,
        max_attempts: int = 30,
        poll_interval_seconds: float = 1.0,
    ) -> dict[str, Any]:
        """发起 Dify Chat 对话并等待回答（blocking 模式直接返回）。"""
        payload: dict[str, Any] = {
            "inputs": {},
            "query": message,
            "response_mode": "blocking",
            "user": str(user_id) if user_id else "system",
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id

        response = self._post("/v1/chat-messages", payload)
        data = response.payload

        return {
            "conversation_id": data.get("conversation_id", ""),
            "message_id": data.get("message_id", ""),
            "answer_text": data.get("answer", ""),
            "status": "completed",
            "chat_payload": data,
            "retrieve_payload": {},
            "messages_payload": data,
        }

    # ── 兼容方法 ──

    def has_site_workflow(self) -> bool:
        """Dify 无 coze.site 直连模式。"""
        return False

    def has_chat_bot(self) -> bool:
        """检查是否配置了 Dify Chat API Key。"""
        try:
            self._get_required_config("dify_api_key")
            return True
        except DifyGatewayConfigError:
            return False

    def run_workflow_stream(
        self,
        *,
        parameters: dict[str, Any] | None = None,
    ) -> DifyGatewayResponse:
        return self.run_workflow(parameters=parameters, is_async=True)

    def run_workflow_async(
        self,
        *,
        parameters: dict[str, Any] | None = None,
    ) -> DifyGatewayResponse:
        return self.run_workflow(parameters=parameters, is_async=True)
