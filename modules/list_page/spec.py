"""系统能力：列表页声明。列、筛选与装配开关集中在一处。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from modules.column_filter.service import ColumnFilterSpec

DEFAULT_PAGE_SIZE = 10


def default_page_size_options(page_size: int = DEFAULT_PAGE_SIZE) -> list[int]:
    """默认每页条数选项：1 倍到 5 倍。"""
    safe_size = max(1, int(page_size))
    return [safe_size * multiplier for multiplier in range(1, 6)]


@dataclass(frozen=True)
class ListPageSpec:
    """一张列表的列、筛选与装配声明。

    attach_column_filters 默认 True，mount / bind_table 时自动给可筛列挂表头筛选。
    关掉后仍保留芯片、方案与列设置，只是不往表格表头装配触发器。
    """

    page_code: str
    list_key: str
    columns: Sequence[dict[str, Any]]
    column_filters: Sequence[ColumnFilterSpec] = ()
    required_column_names: Sequence[str] = ()
    default_visible_column_names: Sequence[str] | None = None
    default_page_size: int = DEFAULT_PAGE_SIZE
    page_size_options: Sequence[int] | None = None
    attach_column_filters: bool = True
    column_name_aliases: Mapping[str, str] | None = None
    initial_filter_values: Mapping[str, Any] | None = None

    def allowed_column_names(self) -> list[str]:
        """列偏好允许的列名。"""
        return [str(column["name"]) for column in self.columns]

    def resolved_visible_column_names(self) -> list[str]:
        """默认可见列；未声明时展示全部列。"""
        if self.default_visible_column_names is not None:
            return [str(name) for name in self.default_visible_column_names]
        return self.allowed_column_names()

    def resolved_page_size_options(self) -> list[int]:
        """分页条数选项。"""
        if self.page_size_options is not None:
            return [int(size) for size in self.page_size_options]
        return default_page_size_options(self.default_page_size)
