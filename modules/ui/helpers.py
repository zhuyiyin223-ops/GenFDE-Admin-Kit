"""NiceGUI 页面通用辅助函数。

本模块只提供标题、容器清理和上传事件读取，不承载业务逻辑和数据访问。
分页控件见 ``modules.ui.paged_table``。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from inspect import isawaitable
from typing import Any

from nicegui import events, ui

PAGE_TITLE_CLASSES = "text-3xl font-weight-900"
SECTION_TITLE_CLASSES = "text-xl font-bold"
SUBSECTION_TITLE_CLASSES = "text-base font-bold"


def render_page_title(title: str) -> Any:
    """按项目一级标题规范渲染页面主标题。"""
    return ui.label(title).classes(PAGE_TITLE_CLASSES)


def render_section_title(title: str, *, accent: bool = False) -> Any:
    """按项目二级标题规范渲染区块标题，可选主色竖杠。"""
    if not accent:
        return ui.label(title).classes(SECTION_TITLE_CLASSES)

    with ui.row().classes("items-center gap-3"):
        ui.element("div").classes("h-6 w-1 rounded-full bg-primary")
        return ui.label(title).classes(SECTION_TITLE_CLASSES)


def render_subsection_title(title: str, *, accent: bool = False) -> Any:
    """按项目三级标题规范渲染分组标题，可选主色竖杠。"""
    if not accent:
        return ui.label(title).classes(SUBSECTION_TITLE_CLASSES)

    with ui.row().classes("items-center gap-2"):
        ui.element("div").classes("h-4 w-1 rounded-full bg-primary")
        return ui.label(title).classes(SUBSECTION_TITLE_CLASSES)


def clear_element(element: Any) -> None:
    """清空 NiceGUI 容器，兼容同步/异步 clear 行为。"""
    if element is None:
        return
    result = element.clear()
    if not isawaitable(result):
        return
    try:
        asyncio.create_task(_await_and_ignore(result))
    except RuntimeError:
        return


async def _await_and_ignore(awaitable_obj: Awaitable[Any]) -> None:
    """等待异步 clear 结果，避免 UI 清理异常影响页面主流程。"""
    try:
        await awaitable_obj
    except asyncio.CancelledError:
        return
    except Exception:
        return


async def read_upload_event_file(event: events.UploadEventArguments) -> tuple[str, bytes]:
    """兼容读取上传事件中的文件名与字节内容。

    本函数只处理 NiceGUI 不同上传事件结构的兼容，不负责文件类型、大小或业务校验。
    """
    upload_file = getattr(event, "file", None)
    if upload_file is not None and hasattr(upload_file, "read"):
        file_name = str(getattr(upload_file, "name", "") or getattr(event, "name", "") or "").strip()
        file_bytes = await upload_file.read()
        if not file_name or not isinstance(file_bytes, bytes):
            raise ValueError("上传文件读取失败")
        return file_name, file_bytes

    file_name = str(getattr(event, "name", "") or "").strip()
    content = getattr(event, "content", None)
    if content is None or not hasattr(content, "read"):
        raise ValueError("上传文件读取失败")

    file_bytes = content.read()
    if not file_name or not isinstance(file_bytes, bytes):
        raise ValueError("上传文件读取失败")
    return file_name, file_bytes
