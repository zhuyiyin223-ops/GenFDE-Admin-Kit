"""sys_api 页面控制器。

本模块负责：
- 页面状态维护；
- 事件处理与 service 调用编排；
- 弹框内容渲染编排。

本模块不负责：
- 路由挂载；
- 业务规则实现（由 service 负责）。
"""

from __future__ import annotations

import json
from typing import Any

from nicegui import ui

from modules.list_page import ListPageFacade
from modules.ui.helpers import clear_element

from .client_service import ApiClientService
from .page_forms import ClientFormData, ClientFormRefs, build_client_form, collect_client_form_data
from .page_table import (
    CLIENT_LIST_SPEC,
    REQUEST_LOG_LIST_SPEC,
    TOKEN_LIST_SPEC,
    format_client_for_display,
    format_request_log_for_display,
    format_token_for_display,
)
from .request_log_service import ApiRequestLogService
from .token_service import ApiTokenService


class ApiClientPageController:
    """API 客户端管理控制器。"""

    def __init__(self) -> None:
        self.list_page = ListPageFacade(spec=CLIENT_LIST_SPEC, on_refresh=self.update_table)
        self.status: bool | None = None
        self.add_dialog = None
        self.edit_dialog = None

    async def save_new_client(self, form: ClientFormRefs) -> None:
        """保存新增客户端。"""
        form_data = collect_client_form_data(form)
        if not form_data.client_id or not form_data.password:
            ui.notify("请填写必填字段：账号和密码", type="negative")
            return
        success, message, _ = await ApiClientService.create_client(
            client_id=form_data.client_id,
            client_secret=form_data.password,
            name=form_data.name,
            ip_whitelist=form_data.ip_whitelist,
            is_active=form_data.is_active,
        )
        if not success:
            ui.notify(message, type="negative")
            return
        ui.notify(message, type="positive")
        self.add_dialog.close()
        await self.update_table()

    async def save_edit_client(self, form: ClientFormRefs, client_id: int) -> None:
        """保存编辑客户端。"""
        form_data: ClientFormData = collect_client_form_data(form)
        new_secret = None
        if form_data.reset_password:
            if not form_data.password:
                ui.notify("请输入新密码", type="negative")
                return
            new_secret = form_data.password
        success, message = await ApiClientService.update_client(
            client_id=client_id,
            name=form_data.name,
            is_active=form_data.is_active,
            new_secret=new_secret,
            ip_whitelist=form_data.ip_whitelist,
        )
        if not success:
            ui.notify(message, type="negative")
            return
        ui.notify(message, type="positive")
        self.edit_dialog.close()
        await self.update_table()

    @staticmethod
    def _render_client_dialog(
            dialog: Any,
            *,
            title: str,
            initial: dict[str, Any] | None,
            include_reset_password: bool,
            readonly_client_id: bool,
            on_save: Any,
            include_status_switch: bool = False,
    ) -> None:
        """渲染客户端弹窗。"""
        clear_element(dialog)
        with dialog, ui.card().classes("w-[680px] max-w-[96vw] rounded-2xl shadow-xl"):
            with ui.column().classes("w-full gap-3 p-6 max-[640px]:p-4"):
                with ui.row().classes("w-full items-center justify-between gap-3"):
                    ui.label(title).classes("text-xl font-bold")
                    ui.button(icon="close", on_click=dialog.close).props("flat round dense")
                form = build_client_form(
                    initial=initial,
                    include_password=True,
                    include_status_switch=include_status_switch,
                    include_reset_password=include_reset_password,
                    readonly_client_id=readonly_client_id,
                )
                with ui.row().classes("w-full justify-end items-center gap-3 pt-5 mt-1"):
                    ui.button("保存", icon="save", on_click=lambda: on_save(form)).props(
                        "rounded unelevated no-caps"
                    ).classes("px-5")

    async def open_add_dialog(self) -> None:
        """打开新增客户端弹窗。"""
        self._render_client_dialog(
            self.add_dialog,
            title="新增API账号",
            initial=None,
            include_reset_password=False,
            readonly_client_id=False,
            on_save=self.save_new_client,
            include_status_switch=False,
        )
        self.add_dialog.open()

    async def open_edit_dialog(self, client_data: dict[str, Any]) -> None:
        """打开编辑客户端弹窗。"""
        detail = await ApiClientService.get_client_detail(int(client_data["id"]))
        if not detail:
            ui.notify("客户端不存在", type="negative")
            return
        self._render_client_dialog(
            self.edit_dialog,
            title="编辑API账号",
            initial=detail,
            include_reset_password=True,
            readonly_client_id=True,
            on_save=lambda form: self.save_edit_client(form, int(detail["id"])),
            include_status_switch=True,
        )
        self.edit_dialog.open()

    async def update_table(self) -> None:
        """刷新客户端表格和分页。"""
        current_page, page_size = self.list_page.page_and_size()
        result = await ApiClientService.search_clients(
            page=current_page,
            page_size=page_size,
            keyword=self.list_page.search_state.keyword,
            status=self.status,
            **self.list_page.filter_kwargs(),
        )
        clients = result.get("clients", [])
        self.list_page.apply_items(
            clients if isinstance(clients, list) else [],
            total=int(result.get("total", 0)),
            row_mapper=format_client_for_display,
        )


class ApiTokenLogController:
    """API 令牌日志控制器。"""

    def __init__(self) -> None:
        self.list_page = ListPageFacade(spec=TOKEN_LIST_SPEC, on_refresh=self.update_table)
        self.token_type: str | None = None
        self.status: str | None = None

    async def update_table(self) -> None:
        """刷新令牌日志表格和分页。"""
        current_page, page_size = self.list_page.page_and_size()
        result = await ApiTokenService.search_tokens(
            page=current_page,
            page_size=page_size,
            keyword=self.list_page.search_state.keyword,
            token_type=self.token_type,
            status=self.status,
            **self.list_page.filter_kwargs(),
        )
        tokens = result.get("tokens", [])
        self.list_page.apply_items(
            tokens if isinstance(tokens, list) else [],
            total=int(result.get("total", 0)),
            row_mapper=format_token_for_display,
        )


class ApiRequestLogController:
    """API 请求日志控制器。"""

    def __init__(self) -> None:
        self.list_page = ListPageFacade(spec=REQUEST_LOG_LIST_SPEC, on_refresh=self.update_table)
        self.status_code: int | None = None
        self.detail_dialog = None

    async def update_table(self) -> None:
        """刷新请求日志表格和分页。"""
        current_page, page_size = self.list_page.page_and_size()
        result = await ApiRequestLogService.search_logs(
            page=current_page,
            page_size=page_size,
            keyword=self.list_page.search_state.keyword,
            status_code=self.status_code,
            **self.list_page.filter_kwargs(),
        )
        logs = result.get("logs", [])
        self.list_page.apply_items(
            logs if isinstance(logs, list) else [],
            total=int(result.get("total", 0)),
            row_mapper=format_request_log_for_display,
        )

    @staticmethod
    def _format_json(text: str) -> str:
        """对 JSON 文本做友好格式化。"""
        if not text:
            return ""
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return text
        return json.dumps(data, ensure_ascii=False, indent=2)

    async def open_detail_dialog(self, log_id: int) -> None:
        """打开请求日志详情弹窗。"""
        detail = await ApiRequestLogService.get_log_detail(log_id)
        if not detail:
            ui.notify("请求日志不存在", type="negative")
            return

        if self.detail_dialog is None:
            self.detail_dialog = ui.dialog()
        clear_element(self.detail_dialog)

        request_text = self._format_json(str(detail.get("request_body", "")))
        response_text = self._format_json(str(detail.get("response_body", "")))

        with self.detail_dialog, ui.card().classes("w-[960px] max-w-[96vw] rounded-2xl shadow-xl"):
            with ui.column().classes("w-full gap-3 p-6 max-[640px]:p-4"):
                with ui.row().classes("w-full items-center justify-between gap-3"):
                    ui.label("请求日志详情").classes("text-xl font-bold")
                    ui.button(icon="close", on_click=self.detail_dialog.close).props("flat round dense")
                with ui.element("div").classes("grid w-full grid-cols-2 gap-3 max-[900px]:grid-cols-1"):
                    with ui.column().classes("gap-1"):
                        ui.label("请求信息").classes("text-sm font-semibold")
                        ui.textarea(value=request_text).props(
                            "readonly autogrow dense outlined autocomplete=off"
                        ).classes("w-full")
                    with ui.column().classes("gap-1"):
                        ui.label("响应信息").classes("text-sm font-semibold")
                        ui.textarea(value=response_text).props(
                            "readonly autogrow dense outlined autocomplete=off"
                        ).classes("w-full")

        self.detail_dialog.open()
