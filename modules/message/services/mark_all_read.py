"""系统能力用例：标记当前用户全部未读消息为已读。"""

from __future__ import annotations

from models import UserMessage
from modules.event_hub import EventHub

_TOPIC = "message"


async def mark_all_read(user_id: int) -> int:
    """标记当前用户所有未读消息为已读。"""
    affected = await UserMessage.filter(user_id=int(user_id), read=False).update(read=True)
    if affected > 0:
        EventHub.publish(
            topic=_TOPIC,
            user_id=int(user_id),
            event={"type": "message_all_read", "user_id": int(user_id), "count": int(affected)},
        )
    return int(affected)
