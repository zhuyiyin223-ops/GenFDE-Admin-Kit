"""业务域事务用例：读取 API 请求日志详情。"""

from __future__ import annotations

from typing import Any

from models import ApiRequestLog

from .client_lookup import map_by_ids


def _format_time(value) -> str | None:
    if not value:
        return None
    return value.strftime("%Y-%m-%d %H:%M")


async def get_log_detail(log_id: int) -> dict[str, Any] | None:
    """按主键读取请求日志详情。"""
    log = await ApiRequestLog.filter(id=log_id).first()
    if not log:
        return None
    client_map = await map_by_ids([log.client_id])
    client_row = client_map.get(int(log.client_id)) if log.client_id else None
    return {
        "id": log.id,
        "client_id": (client_row.get("client_id") if client_row else None) or log.client_id_text or "",
        "client_name": (client_row.get("name") if client_row else None) or "",
        "method": log.method,
        "path": log.path,
        "status_code": log.status_code,
        "ip_addr": log.ip_addr or "",
        "user_agent": log.user_agent or "",
        "process_ms": log.process_ms,
        "request_body": log.request_body or "",
        "response_body": log.response_body or "",
        "created_at": _format_time(log.created_at) or "-",
    }
