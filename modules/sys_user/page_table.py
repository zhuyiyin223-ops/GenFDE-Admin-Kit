"""sys_user 页面表格相关能力。"""

from __future__ import annotations

from typing import Any

from nicegui import ui

from models import Role, UserRole
from modules.column_filter.service import (
    ColumnFilterKind,
    ColumnFilterRelation,
    ColumnFilterSpec,
    ColumnFilterValueType,
    options_from_mapping,
)
from modules.keyword_search.service import STATUS_LABELS, YES_NO_LABELS
from modules.list_page import ListPageSpec

USER_TABLE_COLUMNS = [
    {"name": "index", "label": "#", "field": "index"},
    {"name": "action", "label": "操作", "field": "action"},
    {"name": "is_active", "label": "状态", "field": "is_active", "sortable": True},
    {"name": "userid", "label": "账号", "field": "userid"},
    {"name": "name", "label": "姓名", "field": "name"},
    {"name": "is_admin", "label": "管理员", "field": "is_admin"},
    {"name": "roles", "label": "角色", "field": "roles"},
    {"name": "attachments", "label": "附件", "field": "attachments"},
    {"name": "login_count", "label": "登录次数", "field": "login_count"},
    {"name": "last_active_at", "label": "最近活跃时间", "field": "last_active_at", "sortable": True},
    {"name": "ip_addr", "label": "登录IP", "field": "ip_addr"},
    {"name": "create_at", "label": "创建于", "field": "create_at"},
    {"name": "disabled_at", "label": "禁用于", "field": "disabled_at"},
]
USER_REQUIRED_COLUMN_NAMES = ("index", "action")
USER_COLUMN_FILTERS = (
    ColumnFilterSpec(
        name="is_active",
        label="状态",
        fields=("is_active",),
        kind=ColumnFilterKind.SELECT,
        value_type=ColumnFilterValueType.BOOL,
        options=options_from_mapping(STATUS_LABELS),
    ),
    ColumnFilterSpec(name="userid", label="账号", fields=("userid",)),
    ColumnFilterSpec(name="name", label="姓名", fields=("name",)),
    ColumnFilterSpec(
        name="is_admin",
        label="管理员",
        fields=("is_admin",),
        kind=ColumnFilterKind.SELECT,
        value_type=ColumnFilterValueType.BOOL,
        options=options_from_mapping(YES_NO_LABELS),
    ),
    ColumnFilterSpec(
        name="roles",
        label="角色",
        relation=ColumnFilterRelation(
            through_model=UserRole,
            owner_fk="user_id",
            related_fields=("name",),
            related_model=Role,
            related_fk="role_id",
        ),
    ),
    ColumnFilterSpec(
        name="login_count",
        label="登录次数",
        fields=("login_count",),
        kind=ColumnFilterKind.NUMBER,
    ),
    ColumnFilterSpec(name="ip_addr", label="登录IP", fields=("ip_addr",)),
    ColumnFilterSpec(
        name="last_active_at",
        label="最近活跃时间",
        fields=("last_active_at",),
        kind=ColumnFilterKind.DATE,
    ),
    ColumnFilterSpec(
        name="create_at",
        label="创建于",
        fields=("created_at",),
        kind=ColumnFilterKind.DATE,
    ),
    ColumnFilterSpec(
        name="disabled_at",
        label="禁用于",
        fields=("disabled_at",),
        kind=ColumnFilterKind.DATE,
    ),
)
USER_LIST_SPEC = ListPageSpec(
    page_code="sys_user",
    list_key="user_table",
    columns=USER_TABLE_COLUMNS,
    column_filters=USER_COLUMN_FILTERS,
    required_column_names=USER_REQUIRED_COLUMN_NAMES,
    column_name_aliases={"last_login_at": "last_active_at"},
)


def format_user_for_display(user: dict[str, Any], index: int) -> dict[str, Any]:
    """将 service 结果转换为表格展示行。"""
    return {
        "index": index,
        "id": user["id"],
        "userid": user["userid"],
        "name": user["name"],
        "is_admin": bool(user.get("is_admin", False)),
        "roles": ", ".join(user.get("role_names", [])) if user.get("role_names") else "-",
        "role_ids": user.get("role_ids", []),
        "attachment_count": int(user.get("attachment_count") or 0),
        "is_active": bool(user.get("is_active", False)),
        "login_count": user.get("login_count", 0),
        "last_active_at": user.get("last_active_at") or "",
        "ip_addr": user.get("ip_addr") or "",
        "create_at": user.get("create_at") or "",
        "disabled_at": user.get("disabled_at") or "",
        "action": "",
    }


def build_user_table(*, can_edit: bool) -> Any:
    """创建用户表格并挂载 slot。"""
    table = ui.table(
        columns=USER_TABLE_COLUMNS,
        rows=[],
        row_key="id",
        column_defaults={"align": "left"},
    ).classes("w-full mt-2").props("dense flat bordered")

    table.add_slot("body-cell-is_admin", """
        <q-td key="is_admin" :props="props">
            <q-badge :color="props.value ? 'blue' : 'grey'">
                {{ props.value ? '是' : '否' }}
            </q-badge>
        </q-td>
    """)

    table.add_slot("body-cell-is_active", """
        <q-td key="is_active" :props="props">
            <q-badge :color="props.value ? 'green' : 'red'">
                {{ props.value ? '正常' : '禁用' }}
            </q-badge>
        </q-td>
    """)

    table.add_slot(
        "body-cell-attachments",
        """
        <q-td key="attachments" :props="props">
          <q-btn v-if="props.row.attachment_count" dense flat no-caps color="secondary"
            :label="`查看 ${props.row.attachment_count} 个`"
            @click="() => $parent.$emit('preview-user-attachments', props.row)" />
          <span v-else class="text-grey-5">-</span>
        </q-td>
        """,
    )

    if can_edit:
        table.add_slot("body-cell-action", """
            <q-td key="action" :props="props">
                <div class="row items-center no-wrap q-gutter-xs">
                    <q-btn
                        dense
                        unelevated
                        color="secondary"
                        icon="edit"
                        label="编辑"
                        size="sm"
                        @click="() => $parent.$emit('edit-user', props.row)"
                    />
                    <q-btn
                        dense
                        unelevated
                        color="secondary"
                        icon="attach_file"
                        label="附件"
                        size="sm"
                        @click="() => $parent.$emit('manage-user-attachments', props.row)"
                    />
                </div>
            </q-td>
        """)
    else:
        table.add_slot("body-cell-action", """
            <q-td key="action" :props="props">
                <span class="text-grey-6">-</span>
            </q-td>
        """)

    return table
