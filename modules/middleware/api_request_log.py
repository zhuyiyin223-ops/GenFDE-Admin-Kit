"""API 请求日志中间件。

负责请求和响应摘要采集、敏感字段脱敏、客户端识别及日志写入。
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, Request
from loguru import logger
from starlette.responses import Response

from modules.sys_api.auth_service import decode_token
from modules.sys_api.client_service import ApiClientService
from modules.sys_api.request_log_service import ApiRequestLogService

if TYPE_CHECKING:
    from models import ApiClient


def _truncate_text(value: str | None, limit: int = 4000) -> str:
    """限制日志文本长度，避免大报文撑爆存储。"""
    if value is None:
        return ""
    if len(value) <= limit:
        return value
    return value[:limit] + f"...(truncated {len(value) - limit} chars)"


def _sanitize_json_payload(payload: object) -> object:
    """递归脱敏 JSON 载荷中的敏感字段。"""
    if isinstance(payload, dict):
        result = {}
        for key, value in payload.items():
            key_lower = str(key).lower()
            if key_lower in {"client_secret", "refresh_token", "access_token", "password", "token"}:
                result[key] = "***"
            else:
                result[key] = _sanitize_json_payload(value)
        return result
    if isinstance(payload, list):
        return [_sanitize_json_payload(item) for item in payload]
    return payload


def _serialize_payload(text: str, prefer_json: bool) -> tuple[Any | None, str]:
    """序列化请求或响应体，优先按 JSON 解析后脱敏。"""
    parsed: Any | None = None
    if prefer_json and text:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None

    if parsed is not None:
        serialized = json.dumps(_sanitize_json_payload(parsed), ensure_ascii=False)
    else:
        serialized = text
    return parsed, _truncate_text(serialized or "")


async def _extract_client_info(
    request: Request,
    request_json: object | None,
) -> tuple[ApiClient | None, str | None]:
    """从请求头或请求体中解析客户端身份。"""
    auth_header = request.headers.get("authorization") or ""
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        try:
            payload = decode_token(token, "access")
            client_id = payload.get("sub")
            if client_id:
                client = await ApiClientService.get_active_client_by_client_id(client_id)
                return client, str(client_id)
        except HTTPException:
            pass

    if isinstance(request_json, dict):
        client_id = request_json.get("client_id")
        if client_id:
            client = await ApiClientService.get_active_client_by_client_id(client_id)
            return client, str(client_id)

    return None, None


def _build_response_headers(response: Response) -> dict[str, str]:
    """将响应头规范化为字符串映射。"""
    return {str(key): str(value) for key, value in response.headers.items()}


async def api_request_log_middleware(request: Request, call_next):
    """记录 API 请求与响应摘要，并在读取响应体后重建响应对象。"""
    if not request.url.path.startswith("/api"):
        return await call_next(request)

    start_time = time.perf_counter()
    body_bytes = await request.body()
    request_text = body_bytes.decode("utf-8", errors="replace")
    prefer_request_json = request.headers.get("content-type", "").lower().startswith("application/json")
    request_json, request_body = _serialize_payload(request_text, prefer_request_json)

    response = await call_next(request)
    response_body_bytes = b"".join([chunk async for chunk in response.body_iterator])
    response_text = response_body_bytes.decode("utf-8", errors="replace")
    prefer_response_json = response.headers.get("content-type", "").lower().startswith("application/json")
    _, response_body = _serialize_payload(response_text, prefer_json=prefer_response_json)

    process_ms = int((time.perf_counter() - start_time) * 1000)
    ip_addr = getattr(request.state, "real_ip", None) or (request.client.host if request.client else "")
    user_agent = request.headers.get("user-agent")

    try:
        client, client_id_text = await _extract_client_info(request, request_json)
        await ApiRequestLogService.create_log(
            client=client,
            client_id_text=client_id_text,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            ip_addr=ip_addr,
            user_agent=user_agent,
            request_body=request_body,
            response_body=response_body,
            process_ms=process_ms,
        )
    except Exception:
        logger.exception("API 请求日志写入失败")

    return Response(
        content=response_body_bytes,
        status_code=response.status_code,
        headers=_build_response_headers(response),
        media_type=response.media_type,
    )
