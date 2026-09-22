"""布局头部组件。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from nicegui import ui

from modules.layout.navigation import LayoutMenuCategory
from modules.theme.page_component import build_theme_button
from settings import APP


@dataclass
class HeaderNav:
    """页头一级菜单状态，切页时只更新高亮。"""

    desktop_buttons: dict[str, ui.button] = field(default_factory=dict)
    mobile_buttons: dict[str, ui.button] = field(default_factory=dict)
    active_title: str | None = None

    def sync(self, active_category: LayoutMenuCategory | None) -> None:
        """同步一级菜单高亮。"""
        title = active_category.title if active_category is not None else None
        if title == self.active_title:
            return
        self.active_title = title
        for category_title, button in self.desktop_buttons.items():
            _set_top_nav_active(button, category_title == title, chip=False)
        for category_title, button in self.mobile_buttons.items():
            _set_top_nav_active(button, category_title == title, chip=True)


def build_header(
    left_drawer: ui.left_drawer,
    menu_categories: list[LayoutMenuCategory],
    active_category: LayoutMenuCategory | None,
    current_username: str,
    home_path: str = "/",
    *,
    build_side_button: Callable[[], None] | None = None,
) -> HeaderNav:
    """构建页面头部。"""
    header_nav = HeaderNav(
        active_title=active_category.title if active_category is not None else None,
    )
    with ui.header(elevated=True).classes("ng-app-header text-white px-3 py-2 md:px-4 shadow-lg"):
        with ui.row().classes("w-full items-center no-wrap gap-2 md:gap-4"):
            ui.button(icon="menu", on_click=left_drawer.toggle).props("flat round dense text-color=white").classes(
                "ng-header-icon"
            )

            with ui.row().classes("ng-brand items-center cursor-pointer").on(
                "click", lambda: ui.navigate.to(home_path)
            ):
                with ui.column().classes("ng-brand-text gap-0"):
                    ui.label(APP.title).classes("ng-brand-title")
                    ui.label("ADMIN FDE FRAMEWORK STARTER").classes("ng-brand-subtitle")

            ui.space()

            with ui.row().classes("ng-header-nav items-center justify-end no-wrap gap-2 pr-3"):
                for category in menu_categories:
                    is_active = active_category is not None and category.title == active_category.title
                    button_classes = "ng-top-nav-btn"
                    if is_active:
                        button_classes += " ng-top-nav-btn-active"
                    header_nav.desktop_buttons[category.title] = ui.button(
                        category.title,
                        icon=category.icon,
                        on_click=lambda link=category.default_link: ui.navigate.to(link),
                    ).props("flat dense no-caps text-color=white").classes(button_classes)

            build_theme_button()
            if build_side_button is not None:
                build_side_button()
            _build_account_menu(current_username)

        if menu_categories:
            with ui.row().classes("ng-header-mobile-nav w-full items-center gap-2 overflow-x-auto px-1 pb-1 lg:hidden"):
                for category in menu_categories:
                    is_active = active_category is not None and category.title == active_category.title
                    chip_classes = "ng-top-nav-chip"
                    if is_active:
                        chip_classes += " ng-top-nav-chip-active"
                    header_nav.mobile_buttons[category.title] = ui.button(
                        category.title,
                        icon=category.icon,
                        on_click=lambda link=category.default_link: ui.navigate.to(link),
                    ).props("flat dense no-caps text-color=white").classes(chip_classes)
    return header_nav


def _set_top_nav_active(button: ui.button, is_active: bool, *, chip: bool) -> None:
    """更新一级菜单按钮高亮。"""
    active_class = "ng-top-nav-chip-active" if chip else "ng-top-nav-btn-active"
    if is_active:
        button.classes(add=active_class)
        return
    button.classes(remove=active_class)


def _build_account_menu(current_username: str) -> None:
    """构建账号菜单。"""
    with ui.button(icon="account_circle").props("flat round dense text-color=white").classes("ng-header-icon"):
        with ui.menu().props("auto-close").classes("ng-account-menu"):
            ui.label(f"你好，{current_username}").classes("ng-account-greeting px-4 pt-3 pb-2 text-sm")
            ui.separator().classes("my-1")
            with ui.item(on_click=lambda: ui.navigate.to("/logout")).classes("w-full cursor-pointer"):
                with ui.row().classes("items-center gap-2 px-2"):
                    ui.icon("logout").classes("ng-account-item-icon")
                    ui.label("退出登录")
