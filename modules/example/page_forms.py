"""业务域：示例事项表单构建与取值。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nicegui import ui


@dataclass
class ItemFormRefs:
    """示例事项表单组件引用。"""

    title: Any
    content: Any
    is_done: Any


@dataclass
class ItemFormData:
    """示例事项表单归一化结果。"""

    title: str
    content: str
    is_done: bool


def build_form_initial(item: dict[str, Any] | None = None) -> dict[str, Any]:
    """把详情转为表单初始值。"""
    item = item or {}
    return {
        "title": str(item.get("title") or ""),
        "content": str(item.get("content") or ""),
        "is_done": bool(item.get("is_done")),
    }


def build_item_form(*, initial: dict[str, Any] | None = None) -> ItemFormRefs:
    """构建示例事项表单，不处理保存。"""
    initial = initial or {}
    title_input = ui.input(
        label="* 标题",
        placeholder="请输入标题",
        value=str(initial.get("title") or ""),
    ).classes("w-full").props("dense outlined hide-bottom-space autocomplete=off")
    content_input = ui.textarea(
        label="内容",
        placeholder="可选",
        value=str(initial.get("content") or ""),
    ).classes("w-full").props("outlined hide-bottom-space")
    is_done_switch = ui.switch("已完成", value=bool(initial.get("is_done"))).props("dense")
    return ItemFormRefs(title=title_input, content=content_input, is_done=is_done_switch)


def collect_form_data(form: ItemFormRefs) -> ItemFormData:
    """读取表单当前值。"""
    return ItemFormData(
        title=str(form.title.value or "").strip(),
        content=str(form.content.value or "").strip(),
        is_done=bool(form.is_done.value),
    )
