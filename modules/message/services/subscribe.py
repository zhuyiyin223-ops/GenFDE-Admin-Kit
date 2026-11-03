"""系统能力用例：订阅站内消息事件。"""

from __future__ import annotations

from modules.event_hub import EventHandler, EventHub

_TOPIC = "message"


def subscribe(*, user_id: int, handler: EventHandler) -> str:
    """订阅指定用户的站内消息事件。"""
    return EventHub.subscribe(topic=_TOPIC, user_id=int(user_id), handler=handler)
