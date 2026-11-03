"""系统能力用例：查询用户未读站内消息。"""

from __future__ import annotations

from typing import Any

from models import UserMessage


async def get_unread_messages(user_id: int) -> list[dict[str, Any]]:
    """查询用户未读消息。"""
    messages = await UserMessage.filter(user_id=int(user_id), read=False).order_by("-id").limit(50)
    return [
        {
            "id": int(message.id),
            "content": message.content,
            "time": message.created_at.strftime("%Y-%m-%d %H:%M"),
            "read": bool(message.read),
        }
        for message in messages
    ]
