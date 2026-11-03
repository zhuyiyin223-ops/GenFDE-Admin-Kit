"""业务域事务用例：读取 API 客户端详情。"""

from __future__ import annotations

from typing import Any

from models import ApiClient


async def get_client_detail(client_id: int) -> dict[str, Any] | None:
    """按主键读取客户端详情。"""
    client = await ApiClient.filter(id=client_id).first()
    if not client:
        return None

    return {
        "id": client.id,
        "client_id": client.client_id,
        "name": client.name,
        "is_active": client.is_active,
        "last_login_at": client.last_login_at.strftime("%Y-%m-%d %H:%M") if client.last_login_at else None,
        "last_ip": client.last_ip,
        "ip_whitelist": client.ip_whitelist,
        "created_at": client.created_at.strftime("%Y-%m-%d %H:%M"),
        "updated_at": client.updated_at.strftime("%Y-%m-%d %H:%M") if client.updated_at else None,
    }
