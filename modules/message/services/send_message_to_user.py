"""系统能力用例：给指定用户发送站内消息。"""

from __future__ import annotations

from models import UserMessage
from modules.event_hub import EventHub

_TOPIC = "message"


async def send_message_to_user(user_id: int, content: str) -> None:
    """给指定用户发送站内消息；对方在线时推到页头通知。"""
    text = str(content or "").strip()
    if not text:
        return
    target_id = int(user_id)
    await UserMessage.bulk_create([UserMessage(user_id=target_id, content=text)])
    EventHub.publish(
        topic=_TOPIC,
        user_id=target_id,
        event={"type": "message_created", "user_id": target_id},
    )
