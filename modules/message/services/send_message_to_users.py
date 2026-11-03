"""系统能力用例：给多名用户发送同一条站内消息。"""

from __future__ import annotations

from collections.abc import Iterable

from models import UserMessage
from modules.event_hub import EventHub

_TOPIC = "message"


async def send_message_to_users(user_ids: Iterable[int], content: str) -> int:
    """给多名用户发送同一条站内消息。返回实际发送人数。"""
    text = str(content or "").strip()
    if not text:
        return 0
    unique_ids: list[int] = []
    seen: set[int] = set()
    for raw in user_ids:
        user_id = int(raw)
        if user_id in seen:
            continue
        seen.add(user_id)
        unique_ids.append(user_id)
    if not unique_ids:
        return 0
    await UserMessage.bulk_create([UserMessage(user_id=user_id, content=text) for user_id in unique_ids])
    for user_id in unique_ids:
        EventHub.publish(
            topic=_TOPIC,
            user_id=user_id,
            event={"type": "message_created", "user_id": user_id},
        )
    return len(unique_ids)
