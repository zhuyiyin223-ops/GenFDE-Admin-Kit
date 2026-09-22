"""系统能力：进程内事件总线。可被业务域引用。

用于单进程运行时的用户级事件投递；多进程部署时应替换为 Redis Pub/Sub 等外部消息通道。
站内消息请走 ``MessageService``，不要直接向本总线发布。
"""

from __future__ import annotations

import asyncio
import inspect
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger

EventPayload = dict[str, Any]
EventHandler = Callable[[EventPayload], Awaitable[None] | None]


class EventHub:
    """用户级事件总线。"""

    _subscribers: dict[str, dict[int, dict[str, EventHandler]]]
    _loop: asyncio.AbstractEventLoop | None = None

    @classmethod
    def bind_loop(cls, loop: asyncio.AbstractEventLoop | None) -> None:
        """绑定或清空进程主事件循环，供其他线程投递事件。"""
        cls._loop = loop

    @classmethod
    def _store(cls) -> dict[str, dict[int, dict[str, EventHandler]]]:
        """返回订阅存储。"""
        if not hasattr(cls, "_subscribers"):
            cls._subscribers = {}
        return cls._subscribers

    @classmethod
    def _resolve_loop(cls) -> asyncio.AbstractEventLoop | None:
        """解析应投递到的事件循环。"""
        if cls._loop is not None and not cls._loop.is_closed():
            return cls._loop
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return None

    @classmethod
    def subscribe(cls, *, topic: str, user_id: int, handler: EventHandler) -> str:
        """订阅指定用户的指定 topic 事件。"""
        subscriber_id = uuid.uuid4().hex
        cls._store().setdefault(topic, {}).setdefault(int(user_id), {})[subscriber_id] = handler
        return subscriber_id

    @classmethod
    def unsubscribe(cls, *, topic: str, user_id: int, subscriber_id: str) -> None:
        """取消订阅。"""
        topic_subscribers = cls._store().get(topic)
        if not topic_subscribers:
            return
        user_subscribers = topic_subscribers.get(int(user_id))
        if not user_subscribers:
            return
        user_subscribers.pop(subscriber_id, None)
        if not user_subscribers:
            topic_subscribers.pop(int(user_id), None)
        if not topic_subscribers:
            cls._store().pop(topic, None)

    @classmethod
    def publish(cls, *, topic: str, user_id: int, event: EventPayload) -> None:
        """发布指定用户的指定 topic 事件。"""
        handlers = list(cls._store().get(topic, {}).get(int(user_id), {}).values())
        if not handlers:
            return
        loop = cls._resolve_loop()
        if loop is None:
            logger.warning("事件总线未绑定事件循环，丢弃事件")
            return
        for handler in handlers:
            cls._dispatch(loop, handler, event)

    @classmethod
    def _dispatch(
        cls,
        loop: asyncio.AbstractEventLoop,
        handler: EventHandler,
        event: EventPayload,
    ) -> None:
        """把事件处理器投递到主循环。"""
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            loop.create_task(cls._invoke(handler, event))
            return
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(cls._invoke(handler, event), loop)
            return
        logger.warning("事件循环未运行，丢弃事件")

    @staticmethod
    async def _invoke(handler: EventHandler, event: EventPayload) -> None:
        """执行事件处理器。"""
        try:
            result = handler(event)
            if inspect.isawaitable(result):
                await result
        except Exception:
            logger.exception("事件处理失败")
