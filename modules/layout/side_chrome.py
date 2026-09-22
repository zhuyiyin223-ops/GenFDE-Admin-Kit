"""系统能力：后台壳页头右侧扩展点。由装配层注入，不依赖业务域。"""

from __future__ import annotations

from typing import Protocol

from nicegui import ui
from nicegui.client import Client


class BoundSideChrome(Protocol):
    """已绑定当前用户的页头右侧附加区。"""

    async def start(self) -> None:
        """启动订阅或监听。"""
        ...

    def build_drawer(self) -> ui.right_drawer:
        """构建右侧抽屉。"""
        ...

    def build_header_button(self, drawer: ui.right_drawer) -> None:
        """在页头构建打开抽屉的按钮。"""
        ...

    async def refresh(self) -> None:
        """刷新抽屉内容与页头状态。"""
        ...


class SideChrome(Protocol):
    """页头右侧附加区工厂。"""

    def bind(self, *, user_id: int, client: Client) -> BoundSideChrome:
        """绑定到当前登录用户和页面客户端。"""
        ...


_side_chrome: SideChrome | None = None


def register_side_chrome(chrome: SideChrome) -> None:
    """装配层注入页头右侧附加区。未注册时壳不渲染该区域。"""
    global _side_chrome
    _side_chrome = chrome


def get_side_chrome() -> SideChrome | None:
    """返回已注册的页头右侧附加区。"""
    return _side_chrome
