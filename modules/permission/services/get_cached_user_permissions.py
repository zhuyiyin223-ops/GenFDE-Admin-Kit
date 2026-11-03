"""系统能力用例：读取用户权限编码。"""

from __future__ import annotations

from .permission_context import load_user_permission_context


async def get_cached_user_permissions(user_id: int | None) -> list[str]:
    """返回用户权限编码列表。"""
    if user_id is None:
        return []
    context = await load_user_permission_context(int(user_id))
    return list(context.permission_codes)
