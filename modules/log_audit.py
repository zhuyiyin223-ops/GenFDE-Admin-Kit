"""系统能力：操作日志审计。可被业务域引用。"""

from __future__ import annotations

import functools
import inspect
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

from loguru import logger
from nicegui import app
from tortoise.transactions import in_transaction

from models import OperationType, User, UserLog


def audit_log(module: str, operation_type: OperationType, action: str | None = None):
    """记录异步函数执行日志。"""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            started_at = time.time()
            result = await func(*args, **kwargs)

            await write_user_log(
                user_id=_current_user_id(),
                module=module,
                operation_type=operation_type,
                action=action or func.__name__,
                execution_time=time.time() - started_at,
            )
            return result

        return wrapper

    return decorator


async def write_user_log(
    *,
    user_id: int,
    module: str,
    operation_type: OperationType,
    action: str,
    note: Any = None,
    before_change: Any = None,
    after_change: Any = None,
    execution_time: float = 0,
) -> None:
    """显式写入一条操作日志。"""
    normalized_user_id = int(user_id or 0)
    try:
        async with in_transaction():
            await UserLog.create(
                user_id=normalized_user_id,
                operation_type=operation_type,
                module=str(module or "")[:128],
                action=str(action or "")[:128],
                note=note,
                before_change=before_change,
                after_change=after_change,
                execution_time=round(float(execution_time or 0), 4),
            )
            if normalized_user_id > 0:
                await User.filter(id=normalized_user_id).update(last_active_at=datetime.now())
    except Exception:
        logger.exception("保存操作日志失败")


def _current_user_id() -> int:
    """读取当前会话用户 ID。"""
    try:
        user_id = app.storage.user.get("user_id")
    except Exception:
        return 0
    return int(user_id) if isinstance(user_id, int) else 0


def describe_callable(func: Callable) -> str:
    """返回函数可读描述，保留给业务侧需要自定义日志时使用。"""
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return getattr(func, "__name__", "unknown")
    return f"{getattr(func, '__name__', 'unknown')}{signature}"
