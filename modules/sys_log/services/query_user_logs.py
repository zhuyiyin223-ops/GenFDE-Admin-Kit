"""业务域事务用例：分页查询操作日志。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from modules.column_filter.services import ColumnFilterSpec, ColumnFilterValue

from .log_query import collect_user_logs


async def query_user_logs(
    page: int = 1,
    page_size: int = 10,
    keyword: str = "",
    date_range: str = "",
    operation_type: int | None = None,
    column_filters: Mapping[str, ColumnFilterValue] | None = None,
    column_filter_specs: Sequence[ColumnFilterSpec] = (),
) -> dict[str, Any]:
    """分页查询操作日志。"""
    return await collect_user_logs(
        page=page,
        page_size=page_size,
        keyword=keyword,
        date_range=date_range,
        operation_type=operation_type,
        column_filters=column_filters,
        column_filter_specs=column_filter_specs,
    )
