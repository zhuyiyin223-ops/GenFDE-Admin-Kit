"""业务域事务用例：按当前筛选导出角色。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from modules.column_filter.services import ColumnFilterSpec, ColumnFilterValue
from modules.excel.services import ExcelExportService, ExcelFile

from .role_rows import collect_roles, to_export_row

ROLE_EXPORT_HEADERS = {
    "name": "角色名称",
    "is_active": "状态",
    "permissions": "关联权限",
    "users": "关联用户",
    "create_at": "创建时间",
    "update_at": "更新时间",
}


async def export_roles(
    *,
    keyword: str = "",
    status: bool | None = None,
    column_filters: Mapping[str, ColumnFilterValue] | None = None,
    column_filter_specs: Sequence[ColumnFilterSpec] = (),
) -> ExcelFile:
    """按当前筛选导出角色，不处理浏览器下载。"""
    result = await collect_roles(
        page=1,
        page_size=ExcelExportService.MAX_ROWS,
        keyword=keyword,
        column_filters=column_filters,
        column_filter_specs=column_filter_specs,
    )
    roles = list(result.get("roles") or [])
    if status is not None:
        roles = [role for role in roles if bool(role.get("is_active")) == bool(status)]
    rows = [to_export_row(role) for role in roles]
    total = len(roles) if status is not None else int(result.get("total") or 0)
    return ExcelExportService.build_file(
        rows,
        ROLE_EXPORT_HEADERS,
        filename_stem="角色权限",
        total=total,
        sheet_name="角色权限",
    )
