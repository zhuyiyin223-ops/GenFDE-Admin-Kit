"""系统能力：站内消息的壳页头组件。仅由装配层挂到 layout。"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any

from nicegui import ui
from nicegui.client import Client

from modules.message.service import MessageService


class MessageController:
    """消息中心控制器，满足 layout 页头右侧附加区协议。"""

    def __init__(self, *, user_id: int, client: Client) -> None:
        self.user_id = int(user_id)
        self.client = client
        self.subscription_id: str | None = None
        self._lifecycle_bound = False
        self._refresh_lock = asyncio.Lock()
        self.messages_container: ui.column | None = None
        self.unread_label: ui.label | None = None
        self.badge: ui.badge | None = None

    async def start(self) -> None:
        """启动当前客户端的消息订阅。"""
        if not self._lifecycle_bound:
            self.client.on_disconnect(self.stop)
            self.client.on_connect(self.start)
            self._lifecycle_bound = True
        if self.subscription_id is None:
            self.subscription_id = MessageService.subscribe(
                user_id=self.user_id,
                handler=self.handle_event,
            )
            if self.messages_container is not None:
                await self.refresh()

    async def stop(self) -> None:
        """停止当前客户端的消息订阅。"""
        if self.subscription_id is None:
            return
        MessageService.unsubscribe(
            user_id=self.user_id,
            subscriber_id=self.subscription_id,
        )
        self.subscription_id = None

    async def handle_event(self, _event: dict[str, Any]) -> None:
        """收到消息事件后刷新视图。"""
        self.client.safe_invoke(self.refresh_message_center)

    async def refresh(self) -> None:
        """刷新抽屉列表与未读数。"""
        await self.refresh_message_center()
        await self.update_unread_count()

    def build_drawer(self) -> ui.right_drawer:
        """构建右侧消息抽屉。"""
        return build_message_drawer(self)

    def build_header_button(self, drawer: ui.right_drawer) -> None:
        """构建页头消息按钮。"""
        with ui.button(icon="notifications").props("flat round dense text-color=white").classes(
            "ng-header-icon"
        ).on("click", drawer.toggle).tooltip("消息通知"):
            self.badge = ui.badge("", color="red").props("floating")

    async def refresh_message_center(self) -> None:
        """刷新未读消息列表。"""
        if not self.messages_container:
            return
        async with self._refresh_lock:
            clear_result = self.messages_container.clear()
            if inspect.isawaitable(clear_result):
                await clear_result

            messages = await MessageService.get_unread_messages(self.user_id)
            if not messages:
                with self.messages_container:
                    ui.label("暂无未读消息").classes("ng-muted-text text-sm")
            for message in messages:
                self._render_message_row(message)
            await self.update_unread_count()

    def _render_message_row(self, message: dict[str, Any]) -> None:
        """渲染单条未读消息。"""
        if not self.messages_container:
            return
        with self.messages_container:
            with ui.row().classes("items-center justify-between w-full gap-3"):
                with ui.column().classes("gap-1 min-w-0"):
                    ui.label(str(message["content"])).classes("text-xs")
                    with ui.row().classes("items-center gap-2"):
                        ui.label(str(message["time"])).classes("text-xs text-gray-500")
                        ui.button("已读", on_click=self._build_read_handler(message)).props(
                            "flat rounded size=sm"
                        ).classes("text-xs font-bold")

    def _build_read_handler(self, message: dict[str, Any]):
        """构建单条已读回调。"""

        async def handler() -> None:
            await MessageService.mark_as_read(int(message["id"]), self.user_id)

        return handler

    async def update_unread_count(self) -> int:
        """更新未读数量。"""
        unread_count = await MessageService.get_unread_count(self.user_id)
        if self.unread_label:
            self.unread_label.set_text(f"你有 {unread_count} 条未读消息")
        if self.badge:
            self.badge.set_text(str(unread_count) if unread_count > 0 else "")
        return unread_count

    async def mark_all_messages_read(self) -> None:
        """全部标记为已读。"""
        await MessageService.mark_all_read(self.user_id)


class MessageSideChrome:
    """把站内消息挂到后台壳页头右侧。"""

    def bind(self, *, user_id: int, client: Client) -> MessageController:
        """绑定到当前登录用户和页面客户端。"""
        return MessageController(user_id=user_id, client=client)


def build_message_drawer(message_controller: MessageController) -> ui.right_drawer:
    """构建右侧消息抽屉。"""
    with ui.right_drawer(value=False, elevated=True) as right_drawer:
        with ui.column().classes("p-4 w-full gap-3"):
            with ui.row().classes("justify-between items-center w-full"):
                ui.label("消息通知").classes("text-lg font-bold")
                ui.button(icon="close", on_click=right_drawer.toggle).props("flat round dense")

            with ui.row().classes("justify-between items-center w-full"):
                message_controller.unread_label = ui.label("").classes("text-sm font-bold")
                ui.button(
                    "全部已读",
                    on_click=lambda: ui.timer(0, message_controller.mark_all_messages_read, once=True),
                ).props("flat rounded size=sm color=primary").classes("text-xs font-bold")

            ui.separator()
            message_controller.messages_container = ui.column().classes("w-full gap-2")

    return right_drawer
