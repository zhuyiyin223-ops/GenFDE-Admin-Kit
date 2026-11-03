"""业务域事务用例：按当前筛选导出操作日志。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from modules.column_filter.services import ColumnFilterSpec, ColumnFilterValue
from modules.excel.services import ExcelExportService, ExcelFile

from .log_query import collect_user_logs, to_export_row

USER_LOG_EXPORT_HEADERS = {
    "user_name": "姓名",
    "user_id": "账号",
    "operation_type": "操作类型",
    "module": "模块",
    "action": "动作",
    "execution_time": "耗时",
    "created_at": "时间",
}


async def export_user_logs(
    *,
    keyword: str = "",
    date_range: str = "",
    operation_type: int | None = None,
    column_filters: Mapping[str, ColumnFilterValue] | None = None,
    column_filter_specs: Sequence[ColumnFilterSpec] = (),
) -> ExcelFile:
    """按当前筛选导出操作日志，不处理浏览器下载。"""
    result = await collect_user_logs(
        page=1,
        page_size=ExcelExportService.MAX_ROWS,
        keyword=keyword,
        date_range=date_range,
        operation_type=operation_type,
        column_filters=column_filters,
        column_filter_specs=column_filter_specs,
    )
    rows = [to_export_row(item) for item in result.get("logs", [])]
    return ExcelExportService.build_file(
        rows,
        USER_LOG_EXPORT_HEADERS,
        filename_stem="操作日志",
        total=int(result.get("total") or 0),
        sheet_name="操作日志",
    )
