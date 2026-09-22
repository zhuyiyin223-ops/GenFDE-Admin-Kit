"""系统日志页面入口。"""

from __future__ import annotations

from typing import Any

from nicegui import ui

from modules.layout import create_layout
from modules.permission.definitions import PermissionItem
from modules.permission.guard import check_permission, require_permission
from modules.ui.helpers import render_page_title

from .page_controller import SysLogPageController
from .page_table import build_operation_table


@require_permission(PermissionItem.SYS_LOG_QUERY.code)
async def sys_log() -> None:
    """构建系统日志页面。"""
    controller = SysLogPageController()
    can_export = await check_permission(PermissionItem.SYS_LOG_EXPORT.code)
    list_page = controller.list_page

    with ui.row().classes("w-full items-center"):
        with ui.row().classes("flex-1 min-w-0 items-center gap-3"):
            render_page_title("系统日志")
            with ui.button(
                icon="refresh",
                color="dark_page",
                on_click=ui.navigate.reload,
            ).classes("text-sm font-bold").props("flat rounded"):
                ui.tooltip("刷新页面")
        with ui.tabs().classes("flex-none w-auto") as tabs:
            operation_tab = ui.tab("操作日志")
            error_tab = ui.tab("错误日志")
        ui.element("div").classes("flex-1 min-w-0")

    with ui.row().classes("w-full items-center justify-between gap-3 flex-wrap"):
        with ui.row().classes("items-center gap-3 flex-wrap"):
            list_page.render_search()
            save_scheme_button = list_page.render_save_scheme_button()
            error_refresh = ui.button("刷新", icon="refresh", on_click=controller.refresh_error_logs).props(
                "flat rounded"
            )
        if can_export:
            list_page.render_export(on_click=controller.export_to_excel)

    def _tab_text(value: Any) -> str:
        return str(getattr(value, "text", value) or "")

    def _sync_log_toolbar(_=None) -> None:
        current = _tab_text(getattr(tabs, "value", operation_tab))
        is_operation = current in ("操作日志", _tab_text(operation_tab))
        list_page.search_input.set_visibility(is_operation)
        if save_scheme_button is not None:
            save_scheme_button.set_visibility(is_operation)
        error_refresh.set_visibility(not is_operation)
        if list_page.export_button is not None:
            list_page.export_button.set_visibility(is_operation)

    _sync_log_toolbar()
    tabs.on_value_change(_sync_log_toolbar)

    with ui.tab_panels(tabs, value=operation_tab).classes("w-full").props(
        "animated=false swipeable=false transition-prev=none transition-next=none"
    ):
        with ui.tab_panel(operation_tab):
            list_page.mount(build_operation_table())

        with ui.tab_panel(error_tab):
            with ui.scroll_area().classes("w-full h-96 border rounded"):
                controller.error_log_view = ui.column().classes("w-full gap-0 p-2")

    await list_page.initialize()
    await controller.update_operation_log_table()


create_layout(sys_log, path="/sys/log")
