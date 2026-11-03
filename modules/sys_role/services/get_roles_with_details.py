"""业务域事务用例：分页查询角色。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from modules.column_filter.services import ColumnFilterSpec, ColumnFilterValue

from .role_rows import collect_roles


async def get_roles_with_details(
    *,
    page: int = 1,
    page_size: int = 10,
    keyword: str = "",
    column_filters: Mapping[str, ColumnFilterValue] | None = None,
    column_filter_specs: Sequence[ColumnFilterSpec] = (),
) -> dict[str, Any]:
    """分页查询角色，并附带权限与用户关联展示数据。"""
    return await collect_roles(
        page=page,
        page_size=page_size,
        keyword=keyword,
        column_filters=column_filters,
        column_filter_specs=column_filter_specs,
    )
