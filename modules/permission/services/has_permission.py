"""系统能力用例：判断用户是否拥有指定权限。"""

from __future__ import annotations

from .permission_context import load_user_permission_context


async def has_permission(user_id: int | None, permission_code: str) -> bool:
    """判断用户是否拥有指定权限。"""
    if user_id is None:
        return False
    context = await load_user_permission_context(int(user_id))
    return context.has_permission(permission_code)
