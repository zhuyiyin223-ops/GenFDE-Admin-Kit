"""sys_role 页面表格能力。"""

from __future__ import annotations

from typing import Any

from nicegui import ui

from modules.column_filter.service import (
    ColumnFilterKind,
    ColumnFilterSpec,
    ColumnFilterValueType,
    options_from_mapping,
)
from modules.keyword_search.service import STATUS_LABELS
from modules.list_page import ListPageSpec

ROLE_RELATION_PREVIEW_LENGTH = 24

ROLE_TABLE_COLUMNS = [
    {"name": "index", "label": "#", "field": "index"},
    {"name": "action", "label": "操作", "field": "action"},
    {"name": "is_active", "label": "状态", "field": "is_active", "sortable": True},
    {"name": "name", "label": "角色名称", "field": "name"},
    {"name": "permissions", "label": "关联权限", "field": "permissions"},
    {"name": "users", "label": "关联用户", "field": "users"},
    {"name": "create_at", "label": "创建时间", "field": "create_at"},
    {"name": "update_at", "label": "更新时间", "field": "update_at"},
]
ROLE_REQUIRED_COLUMN_NAMES = ("index", "action")
ROLE_COLUMN_FILTERS = (
    ColumnFilterSpec(
        name="is_active",
        label="状态",
        fields=("is_active",),
        kind=ColumnFilterKind.SELECT,
        value_type=ColumnFilterValueType.BOOL,
        options=options_from_mapping(STATUS_LABELS),
    ),
    ColumnFilterSpec(name="name", label="角色名称", fields=("name",)),
    ColumnFilterSpec(
        name="create_at",
        label="创建时间",
        fields=("created_at",),
        kind=ColumnFilterKind.DATE,
    ),
    ColumnFilterSpec(
        name="update_at",
        label="更新时间",
        fields=("updated_at",),
        kind=ColumnFilterKind.DATE,
    ),
)
ROLE_LIST_SPEC = ListPageSpec(
    page_code="sys_role",
    list_key="role_table",
    columns=ROLE_TABLE_COLUMNS,
    column_filters=ROLE_COLUMN_FILTERS,
    required_column_names=ROLE_REQUIRED_COLUMN_NAMES,
)


def is_role_active(role: dict[str, Any]) -> bool:
    """将角色状态统一归一化为布尔值。"""
    is_active_raw = role.get("is_active")
    if isinstance(is_active_raw, str):
        return is_active_raw == "正常"
    return bool(is_active_raw)


def _build_relation_preview(value: Any) -> str:
    """构建关联字段折叠预览文案，不负责 UI 渲染。"""
    text = str(value or "").strip()
    if not text or text == "-":
        return "-"
    if len(text) <= ROLE_RELATION_PREVIEW_LENGTH:
        return text
    return f"{text[:ROLE_RELATION_PREVIEW_LENGTH]}..."


def _normalize_relation_items(value: Any) -> list[str]:
    """归一化关联项列表，供数量和弹框展示复用。"""
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


def format_role_for_display(role: dict[str, Any], index: int) -> dict[str, Any]:
    """将 service 结果转换为角色表格展示行。"""
    permission_list = _normalize_relation_items(role.get("permission_list"))
    user_list = _normalize_relation_items(role.get("user_list"))
    permissions = role.get("permissions", "-") or "-"
    users = role.get("users", "-") or "-"
    return {
        "index": index,
        "id": role.get("id"),
        "name": role.get("name", ""),
        "permission_codes": role.get("permission_codes", []),
        "permission_list": permission_list,
        "permissions": permissions,
        "permissions_preview": _build_relation_preview(permissions),
        "permissions_count": len(permission_list),
        "permissions_expandable": bool(permission_list),
        "users_list": user_list,
        "users": users,
        "users_preview": _build_relation_preview(users),
        "users_count": len(user_list),
        "users_expandable": bool(user_list),
        "create_at": role.get("create_at", ""),
        "update_at": role.get("update_at", ""),
        "is_active": is_role_active(role),
        "action": "",
    }


def _bind_status_slot(table: Any) -> None:
    """挂载状态列通用 slot。"""
    table.add_slot(
        "body-cell-is_active",
        """
        <q-td key="is_active" :props="props">
            <q-badge :color="props.value ? 'green' : 'red'">
                {{ props.value ? '正常' : '禁用' }}
            </q-badge>
        </q-td>
        """,
    )


def _bind_relation_slot(table: Any, *, field_name: str) -> None:
    """挂载关联字段查看 slot，仅负责表格内触发查看事件。"""
    table.add_slot(
        f"body-cell-{field_name}",
        f"""
        <q-td key="{field_name}" :props="props" style="max-width: 320px;">
            <div class="flex items-center gap-2 no-wrap">
                <div class="text-body2" style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                    {{{{ props.row.{field_name}_preview }}}}
                </div>
                <q-badge
                    v-if="props.row.{field_name}_count"
                    color="grey-3"
                    text-color="blue-grey-8"
                    style="font-size: 12px;"
                >
                    {{{{ props.row.{field_name}_count }}}} 项
                </q-badge>
                <q-btn
                    v-if="props.row.{field_name}_expandable"
                    dense
                    flat
                    size="sm"
                    color="secondary"
                    label="查看"
                    @click="() => $parent.$emit('view-{field_name}', props.row)"
                />
            </div>
        </q-td>
        """,
    )


def build_role_table(*, can_edit: bool) -> Any:
    """创建角色表格并挂载 slot。"""
    table = ui.table(
        columns=ROLE_TABLE_COLUMNS,
        rows=[],
        row_key="id",
        column_defaults={"align": "left"},
    ).classes("w-full mt-2").props("dense flat bordered")
    _bind_status_slot(table)
    _bind_relation_slot(table, field_name="permissions")
    _bind_relation_slot(table, field_name="users")

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
                        @click="() => $parent.$emit('edit-role', props.row)"
                    />
                </div>
            </q-td>
            """,
        )
    else:
        table.add_slot("body-cell-action", '<q-td key="action" :props="props"><span>-</span></q-td>')
    return table
