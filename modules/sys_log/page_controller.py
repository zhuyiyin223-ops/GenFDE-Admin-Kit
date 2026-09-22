"""系统日志页面控制器。"""

from __future__ import annotations

from nicegui import app, ui

from models import OperationType
from modules.excel.page_component import download_excel, set_export_loading
from modules.list_page import ListPageFacade
from modules.log_audit import write_user_log
from modules.permission.definitions import PermissionItem
from modules.permission.guard import check_permission

from .page_table import OPERATION_LIST_SPEC, render_colored_log_lines
from .service import LogService


class SysLogPageController:
    """系统日志页面控制器。"""

    def __init__(self) -> None:
        self.list_page = ListPageFacade(
            spec=OPERATION_LIST_SPEC,
            on_refresh=self.update_operation_log_table,
        )
        self.date_range = ""
        self.operation_type: int | None = None
        self.error_log_view = None

    async def export_to_excel(self) -> None:
        """按当前筛选导出操作日志并触发下载。"""
        if not await check_permission(PermissionItem.SYS_LOG_EXPORT.code):
            ui.notify("没有导出权限", type="negative")
            return
        set_export_loading(self.list_page.export_button, True)
        try:
            excel_file = await LogService.export_user_logs(
                keyword=self.list_page.search_state.keyword,
                date_range=self.date_range,
                operation_type=self.operation_type,
                **self.list_page.filter_kwargs(),
            )
            if not download_excel(excel_file):
                return
            await write_user_log(
                user_id=int(app.storage.user.get("user_id") or 0),
                module="系统日志",
                operation_type=OperationType.EXPORT,
                action="导出操作日志",
                note={
                    "keyword": self.list_page.search_state.keyword,
                    "date_range": self.date_range,
                    "operation_type": self.operation_type,
                },
            )
        except Exception as exc:
            ui.notify(f"导出失败: {exc}", type="negative")
        finally:
            set_export_loading(self.list_page.export_button, False)

    async def update_operation_log_table(self) -> None:
        """刷新操作日志表格及分页。"""
        if not self.list_page.is_mounted:
            return
        current_page, page_size = self.list_page.page_and_size()
        result = await LogService.query_user_logs(
            page=current_page,
            page_size=page_size,
            keyword=self.list_page.search_state.keyword,
            date_range=self.date_range,
            operation_type=self.operation_type,
            **self.list_page.filter_kwargs(),
        )
        logs = result["logs"]
        self.list_page.apply_rows(
            logs if isinstance(logs, list) else [],
            total=int(result["total"]),
        )

    async def refresh_error_logs(self) -> None:
        """刷新错误日志内容。"""
        lines = await LogService.read_error_log_lines(limit=500)
        render_colored_log_lines(self.error_log_view, lines)
