"""后台页面公共壳。

壳页常驻 header、左侧菜单和页头右侧附加区，主内容区通过 ``ui.sub_pages`` 切换。
保留 ``admin_page`` 名称兼容早期模板代码，实际布局统一走 ``create_layout``。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar
from urllib.parse import urlparse

from fastapi.responses import RedirectResponse
from nicegui import app, ui

from modules.layout.entry import ContentPage, create_layout, get_content_pages, get_content_routes
from modules.layout.header import HeaderNav, build_header
from modules.layout.navigation import (
    LayoutMenuCategory,
    LeftDrawerNav,
    build_left_drawer,
    build_navigation_context,
    category_contains_path,
    find_active_category,
)
from modules.layout.side_chrome import get_side_chrome
from modules.layout.styles import apply_layout_styles
from modules.permission.service import PermissionService

PageResult = TypeVar("PageResult")

_REGISTERED_SHELL_PATHS: set[str] = set()


@dataclass
class AdminShell:
    """后台壳状态，负责路径切换时同步导航高亮。"""

    menu_categories: list[LayoutMenuCategory]
    header_nav: HeaderNav
    left_nav: LeftDrawerNav
    current_path: str

    def sync_path(self, raw_path: str) -> None:
        """处理壳内路径变化：无权限则回退，否则只同步导航。"""
        page_path = _normalize_page_path(raw_path)
        target_path = self._resolve_target(page_path)
        if target_path != page_path:
            ui.context.client.sub_pages_router.current_path = target_path
            page_path = target_path
        if page_path == self.current_path:
            return
        self.current_path = page_path
        self._sync_navigation(page_path)

    def _resolve_target(self, page_path: str) -> str:
        """解析壳内应展示的内容路径，非后台路径原样返回。"""
        content_paths = set(get_content_routes())
        if page_path not in content_paths and page_path != "/":
            return page_path
        if page_path in content_paths and self._is_accessible(page_path):
            return page_path
        if self.menu_categories:
            return self.menu_categories[0].default_link
        return page_path

    def _is_accessible(self, page_path: str) -> bool:
        """判断当前壳内菜单是否包含该路径。"""
        return any(category_contains_path(category, page_path) for category in self.menu_categories)

    def _sync_navigation(self, page_path: str) -> None:
        """同步顶栏和左侧菜单到当前路径。"""
        active_category = find_active_category(self.menu_categories, page_path)
        self.header_nav.sync(active_category)
        self.left_nav.sync(page_path, active_category)


def admin_page(path: str, *, title: str) -> Callable[[Callable[[], PageResult]], Callable[[], PageResult]]:
    """注册一个带公共后台布局的页面。"""

    def decorator(func: Callable[[], PageResult]) -> Callable[[], PageResult]:
        create_layout(func, path=path)
        return func

    return decorator


def register_admin_shell() -> None:
    """将后台内容页绑定到同一壳页面，使切页只刷新主内容区。"""
    paths = ["/"]
    for path in get_content_routes():
        if path not in paths:
            paths.append(path)
    for path in paths:
        if path in _REGISTERED_SHELL_PATHS:
            continue
        ui.page(path)(admin_shell)
        _REGISTERED_SHELL_PATHS.add(path)


async def admin_shell() -> RedirectResponse | None:
    """后台公共壳：header、菜单和页头右侧附加区常驻，仅主内容区随路由切换。"""
    user_id = app.storage.user.get("user_id")
    if not isinstance(user_id, int) or not app.storage.user.get("authenticated", False):
        return RedirectResponse("/login")

    content_pages = get_content_pages()
    current_path = _normalize_page_path(ui.context.client.sub_pages_router.current_path)
    target_path = await PermissionService.get_first_accessible_path(user_id, preferred_path=current_path)
    if target_path in content_pages and current_path != target_path:
        return RedirectResponse(target_path)

    permissions = await PermissionService.get_cached_user_permissions(user_id)
    page_path = current_path if current_path in content_pages else target_path
    menu_categories, active_category, drawer_category = build_navigation_context(page_path, permissions)
    content_page = content_pages.get(page_path)
    expanded = content_page.expand_left_drawer if isinstance(content_page, ContentPage) else True
    home_path = menu_categories[0].default_link if menu_categories else "/"

    apply_layout_styles()
    side_chrome = get_side_chrome()
    bound_side = (
        side_chrome.bind(user_id=user_id, client=ui.context.client) if side_chrome is not None else None
    )
    side_button_builder = None
    if bound_side is not None:
        await bound_side.start()
        side_drawer = bound_side.build_drawer()

        def _build_side_button() -> None:
            bound_side.build_header_button(side_drawer)

        side_button_builder = _build_side_button

    left_nav = build_left_drawer(
        page_path,
        active_category=drawer_category,
        expanded=expanded,
    )
    header_nav = build_header(
        left_nav.drawer,
        menu_categories,
        active_category,
        str(app.storage.user.get("username") or app.storage.user.get("userid") or "当前用户"),
        home_path=home_path,
        build_side_button=side_button_builder,
    )
    with ui.column().classes("w-full p-6 md:p-8 min-h-screen"):
        ui.sub_pages(get_content_routes()).classes("w-full")

    shell = AdminShell(
        menu_categories=menu_categories,
        header_nav=header_nav,
        left_nav=left_nav,
        current_path=page_path,
    )
    ui.context.client.sub_pages_router.on_path_changed(shell.sync_path)
    if bound_side is not None:
        await bound_side.refresh()
    return None


def _normalize_page_path(path: str) -> str:
    """去掉查询串和尾斜杠，得到壳内路径。"""
    normalized = (urlparse(path).path or "/").rstrip("/")
    return normalized or "/"
