"""系统能力用例：取消站内消息订阅。"""

from __future__ import annotations

from modules.event_hub import EventHub

_TOPIC = "message"


def unsubscribe(*, user_id: int, subscriber_id: str) -> None:
    """取消站内消息订阅。"""
    EventHub.unsubscribe(topic=_TOPIC, user_id=int(user_id), subscriber_id=subscriber_id)
