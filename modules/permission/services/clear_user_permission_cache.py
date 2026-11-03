"""系统能力用例：清理当前会话的权限缓存。"""

from __future__ import annotations

from nicegui import app

from .permission_context import CACHE_KEY, UserPermissionContext


def clear_user_permission_cache(user_id: int | None = None) -> None:
    """清理当前浏览器会话中的权限缓存。"""
    cached = UserPermissionContext.from_cache_dict(app.storage.user.get(CACHE_KEY))
    if user_id is None or cached is None or cached.user_id == int(user_id):
        app.storage.user.pop(CACHE_KEY, None)
