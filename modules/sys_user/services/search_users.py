"""业务域事务用例：分页查询用户。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from modules.column_filter.services import ColumnFilterSpec, ColumnFilterValue

from .user_rows import collect_users


async def search_users(
    *,
    page: int = 1,
    page_size: int = 10,
    keyword: str | None = None,
    status: bool | None = None,
    column_filters: Mapping[str, ColumnFilterValue] | None = None,
    column_filter_specs: Sequence[ColumnFilterSpec] = (),
) -> dict[str, Any]:
    """分页查询用户并附带角色信息，不处理 UI 排序状态。"""
    return await collect_users(
        page=page,
        page_size=page_size,
        keyword=keyword,
        status=status,
        column_filters=column_filters,
        column_filter_specs=column_filter_specs,
    )
