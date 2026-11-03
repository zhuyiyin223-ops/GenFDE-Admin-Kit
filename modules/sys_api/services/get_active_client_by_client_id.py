"""业务域事务用例：按客户端标识读取启用账号。"""

from __future__ import annotations

from models import ApiClient


async def get_active_client_by_client_id(client_id: object) -> ApiClient | None:
    """按客户端标识查询启用的 API 客户端。"""
    normalized_client_id = str(client_id or "").strip()
    if not normalized_client_id:
        return None
    return await ApiClient.filter(client_id=normalized_client_id, is_active=True).first()
