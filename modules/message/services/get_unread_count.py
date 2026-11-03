"""系统能力用例：统计当前用户未读消息数量。"""

from __future__ import annotations

from models import UserMessage


async def get_unread_count(user_id: int) -> int:
    """返回当前用户未读消息数量。"""
    return await UserMessage.filter(user_id=int(user_id), read=False).count()
