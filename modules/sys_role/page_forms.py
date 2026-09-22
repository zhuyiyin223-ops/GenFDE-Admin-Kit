"""sys_role 页面表单能力。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nicegui import ui

from modules.permission.definitions import PermissionCategories, PermissionItem, PermissionType

ROLE_PERMISSION_CSS = """
<style>
.role-permission-wrap {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  column-gap: 10px;
  row-gap: 6px;
}
.role-permission-item {
  flex: 0 0 calc((100% - 50px) / 6);
  max-width: calc((100% - 50px) / 6);
}
.role-permission-wrap .q-checkbox {
  margin: 0 !important;
  width: 100%;
}
.role-permission-wrap .q-checkbox__label {
  display: block;
  font-size: 12px;
  line-height: 1.35;
  white-space: normal;
  word-break: break-word;
}
.role-permission-category-title {
  color: #111827 !important;
  font-size: 12px !important;
  font-weight: 700 !important;
  line-height: 1.4 !important;
}
body.body--dark .role-permission-wrap .q-checkbox__label,
body.body--dark .role-permission-category-title {
  color: rgba(241, 245, 249, 0.92) !important;
}
@media (max-width: 1200px) {
  .role-permission-item {
    flex-basis: calc((100% - 40px) / 5);
    max-width: calc((100% - 40px) / 5);
  }
}
@media (max-width: 900px) {
  .role-permission-item {
    flex-basis: calc((100% - 30px) / 4);
    max-width: calc((100% - 30px) / 4);
  }
}
@media (max-width: 700px) {
  .role-permission-item {
    flex-basis: calc((100% - 20px) / 3);
    max-width: calc((100% - 20px) / 3);
  }
}
</style>
"""


def _not_blank(value: Any) -> bool:
    return bool(str(value or "").strip())


def _max_len(max_len: int):
    return lambda value: len(str(value or "")) <= max_len


ROLE_NAME_VALIDATION = {
    "不能为空": _not_blank,
    "长度不能超过64个字符": _max_len(64),
}


def normalize_permission_codes(value: Any) -> list[str]:
    """将权限选择值归一化为权限编码列表，忽略空值。"""
    if not value:
        return []
    values = value if isinstance(value, list) else [value]
    return [str(item).strip() for item in values if str(item or "").strip()]


def group_permissions_by_category() -> list[tuple[str, list[PermissionItem]]]:
    """按权限分类顺序输出权限分组。"""
    grouped: dict[str, list[PermissionItem]] = {}
    for permission in PermissionItem:
        grouped.setdefault(permission.category.title, []).append(permission)

    ordered_groups: list[tuple[str, list[PermissionItem]]] = []
    for category in PermissionCategories.ORDER:
        if category.title in grouped:
            ordered_groups.append((category.title, grouped.pop(category.title)))

    for title in sorted(grouped.keys()):
        ordered_groups.append((title, grouped[title]))
    return ordered_groups


@dataclass
class RoleFormRefs:
    """角色表单组件引用，仅用于页面层取值。"""

    name: Any
    permission_checks: dict[str, Any]
    is_active: Any = None


def build_role_form(
    *,
    initial: dict[str, Any] | None = None,
    include_status_switch: bool,
    readonly_name: bool = False,
) -> RoleFormRefs:
    """构建角色表单，不处理保存动作和 service 调用。"""
    initial = initial or {}
    initial_permission_codes = set(normalize_permission_codes(initial.get("permission_codes")))

    is_active_switch = None
    with ui.element("div").classes("grid w-full grid-cols-3 gap-4 max-[640px]:grid-cols-1"):
        name_input = ui.input(
            label="* 角色名称",
            placeholder="请输入角色名称",
            value=str(initial.get("name", "")),
            validation=ROLE_NAME_VALIDATION,
        ).classes("w-full").props("dense outlined hide-bottom-space autocomplete=off")
        if readonly_name:
            name_input.props("readonly")

        if include_status_switch:
            with ui.row().classes("items-center gap-2 self-center"):
                ui.label("角色启用").classes("text-sm")
                is_active_switch = ui.switch(value=bool(initial.get("is_active", True))).props("dense")

    with ui.row().classes("w-full items-center justify-between mt-3"):
        ui.label("角色权限").classes("text-base font-bold")
        ui.label("注：M 代表菜单权限，F 代表功能权限").classes("text-[11px]")

    permission_checks: dict[str, Any] = {}
    with ui.card().classes("w-full max-h-[48vh] overflow-auto px-2 py-1").props("flat bordered"):
        groups = group_permissions_by_category()
        for index, (category, permissions) in enumerate(groups):
            ui.label(category).classes("role-permission-category-title mb-0.5")
            with ui.element("div").classes("w-full role-permission-wrap"):
                for permission in permissions:
                    permission_type = "(M)" if permission.permission_type == PermissionType.MENU else "(F)"
                    with ui.element("div").classes("role-permission-item"):
                        checkbox = ui.checkbox(
                            f"{permission.title}{permission_type}",
                            value=permission.code in initial_permission_codes,
                        ).props("dense size=xs").classes("text-xs")
                    permission_checks[permission.code] = checkbox

            if index < len(groups) - 1:
                ui.separator()

    return RoleFormRefs(
        name=name_input,
        permission_checks=permission_checks,
        is_active=is_active_switch,
    )
