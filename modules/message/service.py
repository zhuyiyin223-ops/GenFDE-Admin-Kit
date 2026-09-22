"""系统能力：站内消息读写与在线推送。

业务域只通过本服务发给指定用户，不要直接使用事件总线。
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from models import UserMessage
from modules.event_hub import EventHandler, EventHub

_TOPIC = "message"


class MessageService:
    """用户消息读写服务。"""

    @staticmethod
    def subscribe(*, user_id: int, handler: EventHandler) -> str:
        """订阅指定用户的站内消息事件。"""
        return EventHub.subscribe(topic=_TOPIC, user_id=int(user_id), handler=handler)

    @staticmethod
    def unsubscribe(*, user_id: int, subscriber_id: str) -> None:
        """取消站内消息订阅。"""
        EventHub.unsubscribe(topic=_TOPIC, user_id=int(user_id), subscriber_id=subscriber_id)

    @staticmethod
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

    @staticmethod
    async def get_unread_messages(user_id: int) -> list[dict[str, Any]]:
        """查询用户未读消息。"""
        return await MessageService.get_user_messages(user_id, read=False)

    @staticmethod
    async def send_message_to_user(user_id: int, content: str) -> None:
        """给指定用户发送站内消息；对方在线时推到页头通知。"""
        await MessageService.send_message_to_users([user_id], content)

    @staticmethod
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
        await UserMessage.bulk_create(
            [UserMessage(user_id=user_id, content=text) for user_id in unique_ids]
        )
        for user_id in unique_ids:
            EventHub.publish(
                topic=_TOPIC,
                user_id=user_id,
                event={"type": "message_created", "user_id": user_id},
            )
        return len(unique_ids)

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    async def get_unread_count(user_id: int) -> int:
        """返回当前用户未读消息数量。"""
        return await UserMessage.filter(user_id=int(user_id), read=False).count()
