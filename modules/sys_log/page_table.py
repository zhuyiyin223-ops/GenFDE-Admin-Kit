"""系统日志页面表格与展示辅助。"""

from __future__ import annotations

from typing import Any

from nicegui import ui

from models import User
from modules.column_filter.service import (
    ColumnFilterKind,
    ColumnFilterSpec,
    ColumnFilterValueType,
    options_from_mapping,
    related_text_spec,
)
from modules.list_page import ListPageSpec

from .service import LogService

OPERATION_LOG_COLUMNS = [
    {"name": "index", "label": "#", "field": "index"},
    {"name": "user_name", "label": "姓名", "field": "user_name"},
    {"name": "user_id", "label": "账号", "field": "user_id"},
    {"name": "operation_type", "label": "操作类型", "field": "operation_type"},
    {"name": "module", "label": "模块", "field": "module"},
    {"name": "action", "label": "动作", "field": "action"},
    {"name": "execution_time", "label": "耗时", "field": "execution_time"},
    {"name": "created_at", "label": "时间", "field": "created_at"},
]
OPERATION_REQUIRED_COLUMN_NAMES = ("index",)
OPERATION_COLUMN_FILTERS = (
    related_text_spec(
        name="user_name",
        label="姓名",
        related_model=User,
        related_fields=("name",),
        owner_field="user_id",
    ),
    related_text_spec(
        name="user_id",
        label="账号",
        related_model=User,
        related_fields=("userid",),
        owner_field="user_id",
    ),
    ColumnFilterSpec(
        name="operation_type",
        label="操作类型",
        fields=("operation_type",),
        kind=ColumnFilterKind.SELECT,
        value_type=ColumnFilterValueType.INT,
        options=options_from_mapping(LogService.OPERATION_TYPE_LABELS),
    ),
    ColumnFilterSpec(name="module", label="模块", fields=("module",)),
    ColumnFilterSpec(name="action", label="动作", fields=("action",)),
    ColumnFilterSpec(
        name="execution_time",
        label="耗时",
        fields=("execution_time",),
        kind=ColumnFilterKind.NUMBER,
    ),
    ColumnFilterSpec(
        name="created_at",
        label="时间",
        fields=("created_at",),
        kind=ColumnFilterKind.DATE,
    ),
)
OPERATION_LIST_SPEC = ListPageSpec(
    page_code="sys_log",
    list_key="operation_table",
    columns=OPERATION_LOG_COLUMNS,
    column_filters=OPERATION_COLUMN_FILTERS,
    required_column_names=OPERATION_REQUIRED_COLUMN_NAMES,
    page_size_options=(10, 15, 20, 25),
    initial_filter_values={"created_at": {"kind": ColumnFilterKind.DATE, "shortcut": "last_3_days"}},
)


def build_operation_table() -> Any:
    """创建操作日志表格组件。"""
    return ui.table(
        columns=OPERATION_LOG_COLUMNS,
        rows=[],
        row_key="id",
        column_defaults={"align": "left"},
    ).classes("w-full").props("dense flat bordered")


def render_colored_log_lines(container: Any, lines: list[str]) -> None:
    """按日志级别渲染日志文本。"""
    container.clear()
    with container:
        for line in lines:
            ui.label(line).classes(f"whitespace-pre-wrap break-all font-mono text-xs {_line_classes(line)}")


def _line_classes(line: str) -> str:
    """根据日志级别返回文本样式。"""
    upper_line = str(line).upper()
    if "CRITICAL" in upper_line or "ERROR" in upper_line or "TRACEBACK" in upper_line:
        return "text-red text-bold"
    if "WARNING" in upper_line:
        return "text-orange"
    if "SUCCESS" in upper_line:
        return "text-green"
    if "INFO" in upper_line or "DEBUG" in upper_line:
        return "text-blue"
    return "text-gray-800"
