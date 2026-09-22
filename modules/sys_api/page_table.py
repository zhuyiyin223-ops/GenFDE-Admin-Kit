"""sys_api 页面表格相关能力。

本模块负责：
- 表格列定义与 slot 模板；
- 页面展示行格式化。

本模块不负责：
- 查询与保存业务；
- 页面权限与路由。
"""

from __future__ import annotations

from typing import Any

from nicegui import ui

from models import ApiClient
from modules.column_filter.service import (
    ColumnFilterKind,
    ColumnFilterOption,
    ColumnFilterSpec,
    ColumnFilterValueType,
    options_from_mapping,
    related_text_spec,
)
from modules.keyword_search.service import STATUS_LABELS
from modules.list_page import ListPageSpec

CLIENT_TABLE_COLUMNS = [
    {"name": "index", "label": "#", "field": "index"},
    {"name": "action", "label": "操作", "field": "action"},
    {"name": "client_id", "label": "账号", "field": "client_id"},
    {"name": "name", "label": "名称", "field": "name"},
    {"name": "is_active", "label": "状态", "field": "is_active", "sortable": True},
    {"name": "last_login_at", "label": "上次登录", "field": "last_login_at"},
    {"name": "last_ip", "label": "上次IP", "field": "last_ip"},
    {"name": "ip_whitelist", "label": "IP白名单", "field": "ip_whitelist"},
    {"name": "created_at", "label": "创建时间", "field": "created_at"},
    {"name": "updated_at", "label": "更新时间", "field": "updated_at"},
]

TOKEN_TABLE_COLUMNS = [
    {"name": "index", "label": "#", "field": "index"},
    {"name": "client_id", "label": "客户端账号", "field": "client_id"},
    {"name": "client_name", "label": "客户端名称", "field": "client_name"},
    {"name": "token_type", "label": "令牌类型", "field": "token_type"},
    {"name": "jti", "label": "令牌ID", "field": "jti"},
    {"name": "status", "label": "状态", "field": "status"},
    {"name": "expires_at", "label": "过期时间", "field": "expires_at"},
    {"name": "last_used_at", "label": "最近使用", "field": "last_used_at"},
    {"name": "revoked_at", "label": "撤销时间", "field": "revoked_at"},
    {"name": "created_at", "label": "创建时间", "field": "created_at"},
]

REQUEST_LOG_TABLE_COLUMNS = [
    {"name": "index", "label": "#", "field": "index"},
    {"name": "action", "label": "操作", "field": "action"},
    {"name": "client_id", "label": "客户端账号", "field": "client_id"},
    {"name": "client_name", "label": "客户端名称", "field": "client_name"},
    {"name": "method", "label": "方法", "field": "method"},
    {"name": "path", "label": "路径", "field": "path"},
    {"name": "status_code", "label": "状态", "field": "status_code"},
    {"name": "ip_addr", "label": "IP", "field": "ip_addr"},
    {"name": "process_ms", "label": "耗时(ms)", "field": "process_ms"},
    {"name": "created_at", "label": "时间", "field": "created_at"},
]
CLIENT_REQUIRED_COLUMN_NAMES = ("index", "action")
TOKEN_REQUIRED_COLUMN_NAMES = ("index",)
REQUEST_LOG_REQUIRED_COLUMN_NAMES = ("index", "action")
TOKEN_TYPE_FILTER_LABELS = {"access": "访问令牌", "refresh": "刷新令牌"}
HTTP_METHOD_OPTIONS = tuple(
    ColumnFilterOption(method, method)
    for method in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")
)
CLIENT_COLUMN_FILTERS = (
    ColumnFilterSpec(name="client_id", label="账号", fields=("client_id",)),
    ColumnFilterSpec(name="name", label="名称", fields=("name",)),
    ColumnFilterSpec(
        name="is_active",
        label="状态",
        fields=("is_active",),
        kind=ColumnFilterKind.SELECT,
        value_type=ColumnFilterValueType.BOOL,
        options=options_from_mapping(STATUS_LABELS),
    ),
    ColumnFilterSpec(name="last_ip", label="上次IP", fields=("last_ip",)),
    ColumnFilterSpec(name="ip_whitelist", label="IP白名单", fields=("ip_whitelist",)),
    ColumnFilterSpec(
        name="last_login_at",
        label="上次登录",
        fields=("last_login_at",),
        kind=ColumnFilterKind.DATE,
    ),
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
TOKEN_COLUMN_FILTERS = (
    related_text_spec(
        name="client_id",
        label="客户端账号",
        related_model=ApiClient,
        related_fields=("client_id",),
        owner_field="client_id",
    ),
    related_text_spec(
        name="client_name",
        label="客户端名称",
        related_model=ApiClient,
        related_fields=("name",),
        owner_field="client_id",
    ),
    ColumnFilterSpec(
        name="token_type",
        label="令牌类型",
        fields=("token_type",),
        kind=ColumnFilterKind.SELECT,
        value_type=ColumnFilterValueType.STR,
        options=options_from_mapping(TOKEN_TYPE_FILTER_LABELS),
    ),
    ColumnFilterSpec(name="jti", label="令牌ID", fields=("jti",)),
    ColumnFilterSpec(
        name="expires_at",
        label="过期时间",
        fields=("expires_at",),
        kind=ColumnFilterKind.DATE,
    ),
    ColumnFilterSpec(
        name="last_used_at",
        label="最近使用",
        fields=("last_used_at",),
        kind=ColumnFilterKind.DATE,
    ),
    ColumnFilterSpec(
        name="revoked_at",
        label="撤销时间",
        fields=("revoked_at",),
        kind=ColumnFilterKind.DATE,
    ),
    ColumnFilterSpec(
        name="created_at",
        label="创建时间",
        fields=("created_at",),
        kind=ColumnFilterKind.DATE,
    ),
)
REQUEST_LOG_COLUMN_FILTERS = (
    ColumnFilterSpec(name="client_id", label="客户端账号", fields=("client_id_text",)),
    related_text_spec(
        name="client_name",
        label="客户端名称",
        related_model=ApiClient,
        related_fields=("name",),
        owner_field="client_id",
    ),
    ColumnFilterSpec(
        name="method",
        label="方法",
        fields=("method",),
        kind=ColumnFilterKind.SELECT,
        value_type=ColumnFilterValueType.STR,
        options=HTTP_METHOD_OPTIONS,
    ),
    ColumnFilterSpec(name="path", label="路径", fields=("path",)),
    ColumnFilterSpec(
        name="status_code",
        label="状态",
        fields=("status_code",),
        kind=ColumnFilterKind.NUMBER,
    ),
    ColumnFilterSpec(name="ip_addr", label="IP", fields=("ip_addr",)),
    ColumnFilterSpec(
        name="process_ms",
        label="耗时(ms)",
        fields=("process_ms",),
        kind=ColumnFilterKind.NUMBER,
    ),
    ColumnFilterSpec(
        name="created_at",
        label="时间",
        fields=("created_at",),
        kind=ColumnFilterKind.DATE,
    ),
)
CLIENT_LIST_SPEC = ListPageSpec(
    page_code="sys_api",
    list_key="client_table",
    columns=CLIENT_TABLE_COLUMNS,
    column_filters=CLIENT_COLUMN_FILTERS,
    required_column_names=CLIENT_REQUIRED_COLUMN_NAMES,
)
TOKEN_LIST_SPEC = ListPageSpec(
    page_code="sys_api",
    list_key="token_table",
    columns=TOKEN_TABLE_COLUMNS,
    column_filters=TOKEN_COLUMN_FILTERS,
    required_column_names=TOKEN_REQUIRED_COLUMN_NAMES,
)
REQUEST_LOG_LIST_SPEC = ListPageSpec(
    page_code="sys_api",
    list_key="request_log_table",
    columns=REQUEST_LOG_TABLE_COLUMNS,
    column_filters=REQUEST_LOG_COLUMN_FILTERS,
    required_column_names=REQUEST_LOG_REQUIRED_COLUMN_NAMES,
)


def format_client_for_display(client: dict[str, Any], index: int) -> dict[str, Any]:
    """将客户端数据转换为表格展示行。"""
    return {
        "index": index,
        "id": client["id"],
        "client_id": client["client_id"],
        "name": client.get("name") or "-",
        "is_active": bool(client.get("is_active", False)),
        "last_login_at": client.get("last_login_at") or "-",
        "last_ip": client.get("last_ip") or "-",
        "ip_whitelist": client.get("ip_whitelist") or "-",
        "created_at": client.get("created_at"),
        "updated_at": client.get("updated_at") or "-",
        "action": "",
    }


def format_token_for_display(token: dict[str, Any], index: int) -> dict[str, Any]:
    """将令牌日志数据转换为表格展示行。"""
    return {**token, "index": index}


def format_request_log_for_display(log: dict[str, Any], index: int) -> dict[str, Any]:
    """将请求日志数据转换为表格展示行。"""
    return {**log, "index": index}


def build_client_table(*, can_edit: bool) -> Any:
    """创建客户端管理表格并挂载 slot。"""
    table = ui.table(
        columns=CLIENT_TABLE_COLUMNS,
        rows=[],
        row_key="id",
        column_defaults={"align": "left"},
    ).classes("w-full mt-2").props("dense flat bordered")

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

    if can_edit:
        table.add_slot(
            "body-cell-action",
            """
            <q-td key="action" :props="props">
                <q-btn
                    dense
                    unelevated
                    color="secondary"
                    icon="edit"
                    label="编辑"
                    size="sm"
                    @click="() => $parent.$emit('edit-client', props.row)"
                />
            </q-td>
            """,
        )
    else:
        table.add_slot(
            "body-cell-action",
            """
            <q-td key="action" :props="props">
                <span class="text-grey-6">-</span>
            </q-td>
            """,
        )
    return table


def build_token_table() -> Any:
    """创建令牌日志表格并挂载 slot。"""
    table = ui.table(
        columns=TOKEN_TABLE_COLUMNS,
        rows=[],
        row_key="id",
        column_defaults={"align": "left"},
    ).classes("w-full mt-2").props("dense flat bordered")

    table.add_slot(
        "body-cell-status",
        """
        <q-td key="status" :props="props">
            <q-badge :color="props.value === '有效' ? 'green' : (props.value === '已撤销' ? 'red' : 'orange')">
                {{ props.value }}
            </q-badge>
        </q-td>
        """,
    )
    return table


def build_request_log_table() -> Any:
    """创建请求日志表格并挂载 slot。"""
    table = ui.table(
        columns=REQUEST_LOG_TABLE_COLUMNS,
        rows=[],
        row_key="id",
        column_defaults={"align": "left"},
    ).classes("w-full mt-2").props("dense flat bordered")

    table.add_slot(
        "body-cell-action",
        """
        <q-td key="action" :props="props">
            <q-btn
                dense
                unelevated
                color="secondary"
                icon="article"
                label="日志详情"
                size="sm"
                @click="() => $parent.$emit('view-log', props.row)"
            />
        </q-td>
        """,
    )
    return table
