"""系统能力用例：标记单条站内消息为已读。"""

from __future__ import annotations

from models import UserMessage
from modules.event_hub import EventHub

_TOPIC = "message"


async def mark_as_read(message_id: int, user_id: int) -> bool:
    """标记单条消息为已读。"""
    updated = await UserMessage.filter(id=int(message_id), user_id=int(user_id)).update(read=True)
    if updated <= 0:
        return False
    EventHub.publish(
        topic=_TOPIC,
        user_id=int(user_id),
        event={"type": "message_read", "user_id": int(user_id), "message_id": int(message_id)},
    )
    return True
