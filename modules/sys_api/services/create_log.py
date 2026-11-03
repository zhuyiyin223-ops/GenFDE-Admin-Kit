"""业务域事务用例：写入 API 请求日志。"""

from __future__ import annotations

from datetime import datetime

from models import ApiClient, ApiRequestLog


async def create_log(
    *,
    client: ApiClient | None = None,
    client_id_text: str | None = None,
    method: str,
    path: str,
    status_code: int,
    ip_addr: str | None = None,
    user_agent: str | None = None,
    request_body: str | None = None,
    response_body: str | None = None,
    process_ms: int | None = None,
) -> None:
    """记录一次 API 请求摘要。"""
    await ApiRequestLog.create(
        client_id=client.id if client is not None else None,
        client_id_text=client_id_text or (client.client_id if client else None),
        method=method,
        path=path,
        status_code=status_code,
        ip_addr=ip_addr,
        user_agent=user_agent,
        request_body=request_body,
        response_body=response_body,
        process_ms=process_ms,
        created_at=datetime.now(),
    )
