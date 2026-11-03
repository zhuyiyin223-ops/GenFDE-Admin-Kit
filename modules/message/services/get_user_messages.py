"""系统能力用例：查询用户站内消息。"""

from __future__ import annotations

from typing import Any

from models import UserMessage


async def get_user_messages(
    user_id: int,
    read: bool | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """查询用户消息。"""
    query = UserMessage.filter(user_id=int(user_id))
    if read is not None:
        query = query.filter(read=read)
    messages = await query.order_by("-id").limit(limit)
    return [
        {
            "id": int(message.id),
            "content": message.content,
            "time": message.created_at.strftime("%Y-%m-%d %H:%M"),
            "read": bool(message.read),
        }
        for message in messages
    ]
