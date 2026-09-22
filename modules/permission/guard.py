"""权限守卫工具。"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from functools import wraps

from nicegui import app, ui

from modules.permission.service import PermissionService


def require_permission(permission_code: str):
    """权限检查装饰器。"""

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not await check_permission(permission_code):
                ui.label("没有访问权限").classes("text-base text-gray-500")
                return None
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)

        return wrapper

    return decorator


async def check_permission(permission_code: str) -> bool:
    """检查当前会话用户是否拥有指定权限。"""
    user_id = app.storage.user.get("user_id")
    if not isinstance(user_id, int):
        return False
    return await PermissionService.has_permission(user_id, permission_code)
