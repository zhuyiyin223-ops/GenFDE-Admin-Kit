"""系统能力：页头主题按钮与主色圆点选择。"""

from __future__ import annotations

from typing import Any

from nicegui import ui

from modules.theme.catalog import Theme, list_themes
from modules.theme.service import ThemeService


def build_theme_button() -> None:
    """构建页头主题按钮；菜单内以主色圆点选择主题，选中后立即生效。"""
    current = ThemeService.resolve()
    dots: dict[str, Any] = {}

    def on_select(theme_key: str) -> None:
        theme = ThemeService.save(theme_key)
        ThemeService.apply(theme, live=True)
        _sync_dot_selection(dots, theme.key)

    with ui.button(icon="palette").props("flat round dense text-color=white").classes("ng-header-icon").tooltip(
        "主题"
    ):
        with ui.menu().props("auto-close").classes("ng-theme-menu"):
            ui.label("主题").classes("ng-theme-menu-title")
            with ui.element("div").classes("ng-theme-swatches"):
                for theme in list_themes():
                    with ui.element("div").classes("ng-theme-option").on(
                        "click",
                        lambda theme_key=theme.key: on_select(theme_key),
                    ):
                        dots[theme.key] = _build_theme_dot(theme, selected=theme.key == current.key)
                        ui.label(theme.name).classes("ng-theme-dot-name")


def _build_theme_dot(theme: Theme, *, selected: bool) -> Any:
    """构建一枚主色圆点。"""
    classes = "ng-theme-dot"
    if selected:
        classes += " ng-theme-dot-selected"
    return ui.element("div").classes(classes).style(f"background-color: {theme.primary}").tooltip(theme.name)


def _sync_dot_selection(dots: dict[str, Any], selected_key: str) -> None:
    """同步圆点选中态。"""
    for theme_key, dot in dots.items():
        if theme_key == selected_key:
            dot.classes(add="ng-theme-dot-selected")
            continue
        dot.classes(remove="ng-theme-dot-selected")
