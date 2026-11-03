"""业务域事务用例：按当前筛选导出用户账号。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from modules.column_filter.services import ColumnFilterSpec, ColumnFilterValue
from modules.excel.services import ExcelExportService, ExcelFile

from .user_rows import collect_users, to_export_row

USER_EXPORT_HEADERS = {
    "userid": "账号",
    "name": "姓名",
    "is_admin": "管理员",
    "roles": "角色",
    "is_active": "状态",
    "login_count": "登录次数",
    "last_active_at": "最近活跃时间",
    "ip_addr": "登录IP",
    "create_at": "创建于",
    "disabled_at": "禁用于",
}


async def export_users(
    *,
    keyword: str | None = None,
    status: bool | None = None,
    column_filters: Mapping[str, ColumnFilterValue] | None = None,
    column_filter_specs: Sequence[ColumnFilterSpec] = (),
) -> ExcelFile:
    """按当前筛选导出用户账号，不处理浏览器下载。"""
    result = await collect_users(
        page=1,
        page_size=ExcelExportService.MAX_ROWS,
        keyword=keyword,
        status=status,
        column_filters=column_filters,
        column_filter_specs=column_filter_specs,
    )
    rows = [to_export_row(user) for user in result.get("users", [])]
    return ExcelExportService.build_file(
        rows,
        USER_EXPORT_HEADERS,
        filename_stem="用户账号",
        total=int(result.get("total") or 0),
        sheet_name="用户账号",
    )
