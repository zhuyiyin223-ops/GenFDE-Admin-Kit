"""接口服务页面入口。"""

from __future__ import annotations

from typing import Any

from nicegui import ui

from modules.layout import create_layout
from modules.list_page import event_row
from modules.permission.definitions import PermissionItem
from modules.permission.guard import check_permission, require_permission
from modules.ui.helpers import render_page_title

from .page_controller import ApiClientPageController, ApiRequestLogController, ApiTokenLogController
from .page_table import build_client_table, build_request_log_table, build_token_table


@require_permission(PermissionItem.SYS_API_QUERY.code)
async def sys_api_page():
    """构建接口服务页面，不直接承载业务逻辑。"""
    controller = ApiClientPageController()
    token_controller = ApiTokenLogController()
    request_log_controller = ApiRequestLogController()

    can_edit = await check_permission(PermissionItem.SYS_API_EDIT.code)

    add_button = None

    with ui.row().classes("w-full items-center"):
        with ui.row().classes("flex-1 min-w-0 items-center gap-3"):
            render_page_title("接口服务")
            with ui.button(
                icon="refresh",
                color="dark_page",
                on_click=ui.navigate.reload,
            ).classes("text-sm font-bold").props("flat rounded"):
                ui.tooltip("刷新页面")
        with ui.tabs().classes("flex-none w-auto") as tabs:
            client_tab = ui.tab("客户端管理")
            token_tab = ui.tab("令牌日志")
            request_log_tab = ui.tab("请求日志")
        ui.element("div").classes("flex-1 min-w-0")

    def _tab_text(value: Any) -> str:
        return str(getattr(value, "text", value) or "")

    def _active_list_page():
        current = _tab_text(getattr(tabs, "value", client_tab))
        if current in ("令牌日志", _tab_text(token_tab)):
            return token_controller.list_page
        if current in ("请求日志", _tab_text(request_log_tab)):
            return request_log_controller.list_page
        return controller.list_page

    with ui.row().classes("w-full items-center gap-3 flex-wrap"):
        controller.list_page.render_search()
        token_controller.list_page.render_search()
        request_log_controller.list_page.render_search()
        if can_edit:
            add_button = ui.button(
                "新增API账号",
                icon="add",
                color="primary",
                on_click=controller.open_add_dialog,
            ).classes("font-bold").props("rounded")
        ui.button(
            "保存方案",
            icon="bookmarks",
            color="secondary",
            on_click=lambda: _active_list_page().open_save_scheme(),
        ).classes("font-bold").props("outline rounded")

    def _sync_api_toolbar(_=None) -> None:
        current = _tab_text(getattr(tabs, "value", client_tab))
        is_client = current in ("客户端管理", _tab_text(client_tab))
        is_token = current in ("令牌日志", _tab_text(token_tab))
        is_request = current in ("请求日志", _tab_text(request_log_tab))
        controller.list_page.search_input.set_visibility(is_client)
        token_controller.list_page.search_input.set_visibility(is_token)
        request_log_controller.list_page.search_input.set_visibility(is_request)
        if add_button is not None:
            add_button.set_visibility(is_client)

    _sync_api_toolbar()
    tabs.on_value_change(_sync_api_toolbar)

    with ui.tab_panels(tabs, value=client_tab).classes("w-full").props(
            'animated=false swipeable=false transition-prev=none transition-next=none'):
        with ui.tab_panel(client_tab):
            controller.list_page.mount(build_client_table(can_edit=can_edit))
            controller.add_dialog = ui.dialog()
            controller.edit_dialog = ui.dialog()

            if can_edit:
                async def handle_edit_client(event_args):
                    client_data = event_row(event_args)
                    if client_data is not None:
                        await controller.open_edit_dialog(client_data)
                        return
                    ui.notify("无法获取客户端数据", type="negative")

                controller.list_page.table.on("edit-client", handle_edit_client)

            await controller.list_page.initialize()
            await controller.update_table()

        with ui.tab_panel(token_tab):
            token_controller.list_page.mount(build_token_table())
            await token_controller.list_page.initialize()
            await token_controller.update_table()

        with ui.tab_panel(request_log_tab):
            request_log_controller.list_page.mount(build_request_log_table())
            request_log_controller.detail_dialog = ui.dialog()

            async def handle_view_log(event_args):
                log_data = event_row(event_args)
                if isinstance(log_data, dict):
                    raw_id_text = str(log_data.get("id") or "").strip()
                    try:
                        log_id = int(raw_id_text)
                    except (TypeError, ValueError):
                        ui.notify("日志ID无效", type="negative")
                        return
                    await request_log_controller.open_detail_dialog(log_id)
                    return
                ui.notify("无法获取日志数据", type="negative")

            request_log_controller.list_page.table.on("view-log", handle_view_log)
            await request_log_controller.list_page.initialize()
            await request_log_controller.update_table()


create_layout(sys_api_page, path="/sys/api")
