"""业务域：示例事项表格列、slot 与展示转换。"""

from __future__ import annotations

from typing import Any

from nicegui import ui

from modules.column_filter.service import (
    ColumnFilterKind,
    ColumnFilterSpec,
    ColumnFilterValueType,
    options_from_mapping,
)
from modules.list_page import ListPageSpec

from .service import DONE_LABELS

ITEM_TABLE_COLUMNS = [
    {"name": "index", "label": "#", "field": "index"},
    {"name": "action", "label": "操作", "field": "action"},
    {"name": "is_done", "label": "状态", "field": "is_done"},
    {"name": "title", "label": "标题", "field": "title"},
    {"name": "content", "label": "内容", "field": "content"},
    {"name": "created_at", "label": "创建时间", "field": "created_at"},
    {"name": "updated_at", "label": "更新时间", "field": "updated_at"},
]
ITEM_REQUIRED_COLUMN_NAMES = ("index", "action")
ITEM_COLUMN_FILTERS = (
    ColumnFilterSpec(
        name="is_done",
        label="状态",
        fields=("is_done",),
        kind=ColumnFilterKind.SELECT,
        value_type=ColumnFilterValueType.BOOL,
        options=options_from_mapping(DONE_LABELS),
    ),
    ColumnFilterSpec(name="title", label="标题", fields=("title",)),
    ColumnFilterSpec(name="content", label="内容", fields=("content",)),
    ColumnFilterSpec(
        name="created_at",
        label="创建时间",
        fields=("created_at",),
        kind=ColumnFilterKind.DATE,
    ),
    ColumnFilterSpec(
        name="updated_at",
        label="更新时间",
        fields=("updated_at",),
        kind=ColumnFilterKind.DATE,
    ),
)
ITEM_LIST_SPEC = ListPageSpec(
    page_code="example",
    list_key="item_table",
    columns=ITEM_TABLE_COLUMNS,
    column_filters=ITEM_COLUMN_FILTERS,
    required_column_names=ITEM_REQUIRED_COLUMN_NAMES,
)


def format_item_for_display(item: dict[str, Any], index: int) -> dict[str, Any]:
    """将 service 结果转为表格行。"""
    content = str(item.get("content") or "").strip()
    return {
        "index": index,
        "id": item.get("id"),
        "title": item.get("title") or "",
        "content": content,
        "content_preview": content if len(content) <= 40 else f"{content[:40]}...",
        "is_done": bool(item.get("is_done")),
        "created_at": item.get("created_at") or "",
        "updated_at": item.get("updated_at") or "",
        "action": "",
    }


def build_item_table(*, can_edit: bool) -> Any:
    """创建示例事项表格并挂载 slot。"""
    table = ui.table(
        columns=ITEM_TABLE_COLUMNS,
        rows=[],
        row_key="id",
        column_defaults={"align": "left"},
    ).classes("w-full mt-2").props("dense flat bordered")
    table.add_slot(
        "body-cell-is_done",
        """
        <q-td key="is_done" :props="props">
            <q-badge :color="props.value ? 'green' : 'grey'">
                {{ props.value ? '已完成' : '未完成' }}
            </q-badge>
        </q-td>
        """,
    )
    table.add_slot(
        "body-cell-content",
        """
        <q-td key="content" :props="props">
            <span>{{ props.row.content_preview || '-' }}</span>
        </q-td>
        """,
    )
    if can_edit:
        table.add_slot(
            "body-cell-action",
            """
            <q-td key="action" :props="props">
                <div class="row items-center no-wrap q-gutter-xs">
                    <q-btn
                        dense
                        unelevated
                        color="secondary"
                        icon="edit"
                        label="编辑"
                        size="sm"
                        @click="() => $parent.$emit('edit-item', props.row)"
                    />
                    <q-btn
                        dense
                        unelevated
                        color="negative"
                        icon="delete"
                        label="删除"
                        size="sm"
                        @click="() => $parent.$emit('delete-item', props.row)"
                    />
                </div>
            </q-td>
            """,
        )
    else:
        table.add_slot("body-cell-action", '<q-td key="action" :props="props"><span>-</span></q-td>')
    return table
