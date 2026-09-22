"""分页表格辅助。

本模块统一分页整数解析、总页数计算、序号行转换和标准分页渲染。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from nicegui import ui

from modules.ui.helpers import clear_element


def to_page_int(value: Any, *, default: int, min_value: int = 1) -> int:
    """将任意值转为不小于下限的分页整数。"""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return max(min_value, int(default))
    return max(min_value, parsed)


def parse_pagination_event(event: Any, *, default: int, min_value: int = 1) -> int:
    """从 NiceGUI 事件中解析分页整数。"""
    sender = getattr(event, "sender", None)
    value = getattr(sender, "value", sender) if sender is not None else getattr(event, "value", event)
    return to_page_int(value, default=default, min_value=min_value)


def compute_total_pages(total: int, page_size: int) -> int:
    """计算总页数。"""
    safe_page_size = max(1, int(page_size))
    return max(1, (max(0, int(total)) + safe_page_size - 1) // safe_page_size)


def map_rows_with_index(
    items: list[dict[str, Any]],
    *,
    current_page: int,
    page_size: int,
    row_mapper: Callable[[dict[str, Any], int], dict[str, Any]],
) -> list[dict[str, Any]]:
    """为分页结果追加序号并转换展示行。"""
    start_index = (max(1, int(current_page)) - 1) * max(1, int(page_size)) + 1
    return [row_mapper(item, index) for index, item in enumerate(items, start=start_index)]


def render_standard_pagination(
    container: Any,
    *,
    current_page: int,
    page_size: int,
    total: int,
    on_page_change: Callable,
    on_page_size_change: Callable,
    page_size_options: list[int],
    render_leading_content: Callable[[], None] | None = None,
    render_trailing_content: Callable[[], None] | None = None,
) -> None:
    """渲染标准分页，可在两侧插入列设置等附属控件。"""
    if container is None:
        return

    total_pages = compute_total_pages(total, page_size)
    clear_element(container)
    with container:
        with ui.row().classes("w-full items-center gap-6"):
            with ui.row().classes("items-center gap-2 shrink-0"):
                if render_leading_content is not None:
                    render_leading_content()

            pagination_classes = (
                "items-center gap-4 shrink-0"
                if render_trailing_content is not None
                else "items-center gap-4 ml-auto"
            )
            with ui.row().classes(pagination_classes):
                ui.select(
                    options=page_size_options,
                    value=page_size,
                    label="每页显示",
                    on_change=on_page_size_change,
                ).classes("w-25").props("dense options-dense")

                pagination = ui.pagination(
                    min=1,
                    max=total_pages,
                    value=current_page,
                    direction_links=True,
                    on_change=on_page_change,
                )
                pagination.props("max-pages=8")

                ui.label().bind_text_from(
                    pagination,
                    "value",
                    lambda _: f"共 {total} 条记录，{total_pages} 页",
                )

            if render_trailing_content is not None:
                with ui.row().classes("min-w-0 flex-1 items-center"):
                    render_trailing_content()
