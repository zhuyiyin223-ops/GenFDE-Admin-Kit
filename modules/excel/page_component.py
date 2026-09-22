"""系统能力：Excel 导出的页面触发。"""

from __future__ import annotations

from typing import Any

from nicegui import ui

from .service import ExcelFile


def render_export_button(*, on_click: Any) -> Any:
    """渲染列表页靠右的导出按钮。"""
    return (
        ui.button("导出EXCEL", icon="download", color="secondary", on_click=on_click)
        .classes("text-xs")
        .props("flat dense rounded")
    )


def set_export_loading(button: Any, loading: bool) -> None:
    """切换导出按钮 loading，避免重复点击。"""
    if button is None:
        return
    if loading:
        button.props("loading disable")
        return
    button.props(remove="loading disable")


def download_excel(excel_file: ExcelFile) -> bool:
    """触发浏览器下载当前导出文件。

    没有数据时只提示、不下载，返回 False。
    """
    if excel_file.row_count <= 0:
        ui.notify("没有数据可导出", type="warning")
        return False
    ui.download(excel_file.content, filename=excel_file.filename)
    if excel_file.truncated:
        ui.notify(f"导出成功，已截断为前 {excel_file.row_count} 条", type="warning")
        return True
    ui.notify("导出成功", type="positive")
    return True
