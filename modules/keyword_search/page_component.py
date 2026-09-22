"""系统能力：列表模糊搜索输入框。"""

from __future__ import annotations

from typing import Any

from nicegui import ui

KEYWORD_SEARCH_LABEL = "模糊搜索（多个关键词用空格分隔）"
KEYWORD_SEARCH_PLACEHOLDER = "输入关键词即可搜索所有列"
KEYWORD_SEARCH_CLASSES = "w-65 text-xs"


def render_keyword_search(*, on_search: Any, value: str = "") -> Any:
    """渲染可复用的模糊搜索框，回车与放大镜都会触发查询。"""
    with ui.input(
        KEYWORD_SEARCH_LABEL,
        placeholder=KEYWORD_SEARCH_PLACEHOLDER,
        value=value,
    ).classes(KEYWORD_SEARCH_CLASSES).props("dense autocomplete=off") as search_input:
        ui.button(on_click=on_search, icon="search").props("flat dense")
    search_input.on("keydown.enter", on_search)
    return search_input
