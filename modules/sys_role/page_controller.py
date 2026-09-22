"""sys_role 页面控制器。"""

from __future__ import annotations

from typing import Any

from nicegui import app, ui

from models import OperationType
from modules.excel.page_component import download_excel, set_export_loading
from modules.list_page import DEFAULT_PAGE_SIZE, ListPageFacade
from modules.log_audit import write_user_log
from modules.permission.definitions import PermissionItem
from modules.permission.guard import check_permission
from modules.ui.helpers import clear_element

from .page_forms import RoleFormRefs, build_role_form
from .page_table import ROLE_LIST_SPEC, format_role_for_display
from .service import RoleService

DEFAULT_STATUS = None


class RolePageController:
    """角色权限维护控制器。"""

    def __init__(self) -> None:
        """初始化页面状态，不负责创建具体 UI 组件。"""
        self.list_page = ListPageFacade(
            spec=ROLE_LIST_SPEC,
            on_refresh=self.update_role_table,
            on_scheme_reset=self._on_scheme_reset,
        )
        self.status: bool | None = DEFAULT_STATUS
        self.role_add_dialog = None
        self.role_edit_dialog = None
        self.role_relation_dialog = None

    def _on_scheme_reset(self) -> None:
        """方案套用时清掉域内额外筛选。"""
        self.status = DEFAULT_STATUS

    @staticmethod
    def _normalize_relation_items(value: Any) -> list[str]:
        """归一化弹框展示项，不处理业务查询。"""
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item or "").strip()]

    @staticmethod
    def _render_relation_dialog(
        dialog: Any,
        *,
        title: str,
        field_label: str,
        items: list[str],
    ) -> None:
        """渲染关联详情弹框，仅负责只读展示。"""
        clear_element(dialog)
        count = len(items)
        with dialog, ui.card().classes("w-[960px] max-w-[96vw] min-h-[300px] rounded-2xl shadow-xl"):
            with ui.column().classes("w-full gap-5 p-8 max-[640px]:p-5"):
                with ui.row().classes("w-full items-start justify-between gap-3"):
                    with ui.column().classes("gap-1"):
                        ui.label(title).classes("text-2xl font-bold")
                        ui.label(f"共 {count} 项{field_label}").classes("text-lg text-grey-7")
                    ui.button(icon="close", on_click=dialog.close).props("flat round dense").classes("text-primary")
                with ui.row().classes("w-full gap-3"):
                    for item in items:
                        ui.label(item).classes("px-4 py-2 rounded-lg bg-grey-2 text-base text-blue-grey-9")

    def open_role_relation_dialog(self, role_row: dict[str, Any], *, field_name: str) -> None:
        """打开角色关联详情弹框，不负责表格事件绑定。"""
        field_label = "权限" if field_name == "permissions" else "用户"
        items = self._normalize_relation_items(
            role_row.get("permission_list" if field_name == "permissions" else "users_list")
        )
        if not items:
            ui.notify(f"当前角色暂无关联{field_label}", type="warning")
            return
        title = str(role_row.get("name") or "角色")
        self._render_relation_dialog(
            self.role_relation_dialog,
            title=title,
            field_label=field_label,
            items=items,
        )
        self.role_relation_dialog.open()

    async def search_roles(
        self,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        keyword: str = "",
    ) -> dict[str, Any]:
        """透传角色查询到 service，不在页面层拼装业务逻辑。"""
        result = await RoleService.get_roles_with_details(
            page=page,
            page_size=page_size,
            keyword=keyword,
            **self.list_page.filter_kwargs(),
        )
        await write_user_log(
            user_id=int(app.storage.user.get("user_id") or 0),
            module="角色权限查询",
            operation_type=OperationType.READ,
            action="查询角色权限",
            note={"keyword": keyword},
        )
        return result

    async def export_to_excel(self) -> None:
        """按当前筛选导出角色并触发下载。"""
        if not await check_permission(PermissionItem.SYS_ROLE_EXPORT.code):
            ui.notify("没有导出权限", type="negative")
            return
        set_export_loading(self.list_page.export_button, True)
        try:
            excel_file = await RoleService.export_roles(
                keyword=self.list_page.search_state.keyword,
                status=self.status,
                **self.list_page.filter_kwargs(),
            )
            if not download_excel(excel_file):
                return
            await write_user_log(
                user_id=int(app.storage.user.get("user_id") or 0),
                module="角色权限",
                operation_type=OperationType.EXPORT,
                action="导出角色权限",
                note={
                    "keyword": self.list_page.search_state.keyword,
                    "status": self.status,
                },
            )
        except Exception as exc:
            ui.notify(f"导出失败: {exc}", type="negative")
        finally:
            set_export_loading(self.list_page.export_button, False)

    @staticmethod
    def _collect_selected_permissions(form: RoleFormRefs) -> list[str]:
        """收集已勾选权限。"""
        return [code for code, checkbox in form.permission_checks.items() if checkbox.value]

    async def _render_role_dialog(
        self,
        dialog: Any,
        *,
        title: str,
        on_save: Any,
        initial: dict[str, Any],
        include_status_switch: bool,
        readonly_name: bool = False,
    ) -> RoleFormRefs:
        """渲染角色弹窗内容，不负责打开弹窗。"""
        clear_element(dialog)
        with dialog, ui.card().classes("w-[1120px] max-w-[98vw] max-h-[92vh] overflow-auto rounded-2xl shadow-xl"):
            with ui.column().classes("w-full gap-3 p-6 max-[640px]:p-4"):
                with ui.row().classes("w-full items-center justify-between gap-3"):
                    ui.label(title).classes("text-xl font-bold")
                    ui.button(icon="close", on_click=dialog.close).props("flat round dense")
                form = build_role_form(
                    initial=initial,
                    include_status_switch=include_status_switch,
                    readonly_name=readonly_name,
                )
                with ui.row().classes("w-full justify-end items-center gap-3 pt-5 mt-1"):
                    ui.button("保存", icon="save", on_click=lambda: on_save(form)).props(
                        "rounded unelevated no-caps"
                    ).classes("px-5 mt-1")
        return form

    async def save_new_role(self, form: RoleFormRefs) -> None:
        """保存新增角色。"""
        role_name = str(form.name.value or "").strip()
        if not role_name:
            ui.notify("请填写必填字段：角色名称", type="negative")
            return

        try:
            role = await RoleService.create_role(
                name=role_name,
                permission_codes=self._collect_selected_permissions(form),
            )
        except Exception as exc:
            ui.notify(f"角色创建失败: {exc!s}", type="negative")
            return

        ui.notify(f'角色 "{role.name}" 创建成功', type="positive")
        await write_user_log(
            user_id=int(app.storage.user.get("user_id") or 0),
            module="角色权限",
            operation_type=OperationType.CREATE,
            action="新增角色",
            after_change={"id": int(role.id), "name": role.name},
        )
        self.role_add_dialog.close()
        await self.update_role_table()

    async def save_edit_role(self, form: RoleFormRefs, role_id: int) -> None:
        """保存编辑角色。"""
        role_name = str(form.name.value or "").strip()
        if not role_name:
            ui.notify("请填写必填字段：角色名称", type="negative")
            return

        is_active = bool(form.is_active.value) if form.is_active is not None else True
        try:
            role = await RoleService.update_role(
                role_id=role_id,
                name=role_name,
                permission_codes=self._collect_selected_permissions(form),
                is_active=is_active,
            )
        except Exception as exc:
            ui.notify(f"角色更新失败: {exc!s}", type="negative")
            return

        ui.notify(f'角色 "{role.name}" 更新成功', type="positive")
        await write_user_log(
            user_id=int(app.storage.user.get("user_id") or 0),
            module="角色权限",
            operation_type=OperationType.UPDATE,
            action="编辑角色",
            after_change={"id": int(role.id), "name": role.name, "is_active": is_active},
        )
        self.role_edit_dialog.close()
        await self.update_role_table()

    async def open_add_dialog(self) -> None:
        """打开新增角色弹窗。"""
        if not self.role_add_dialog:
            self.role_add_dialog = ui.dialog()
        await self._render_role_dialog(
            self.role_add_dialog,
            title="新增角色",
            on_save=self.save_new_role,
            initial={},
            include_status_switch=False,
        )
        self.role_add_dialog.open()

    async def open_edit_dialog(self, row: dict[str, Any]) -> None:
        """打开编辑角色弹窗。"""
        if not row or not row.get("id"):
            ui.notify("无法获取角色信息", type="negative")
            return

        role_id = int(row["id"])
        role_detail = await RoleService.get_role_by_id(role_id)
        if not role_detail:
            ui.notify("角色不存在", type="negative")
            return

        if not self.role_edit_dialog:
            self.role_edit_dialog = ui.dialog()

        await self._render_role_dialog(
            self.role_edit_dialog,
            title="编辑角色",
            on_save=lambda form: self.save_edit_role(form, role_id),
            initial=role_detail,
            include_status_switch=True,
            readonly_name=True,
        )
        self.role_edit_dialog.open()

    async def update_role_table(self) -> None:
        """刷新角色表格与分页。"""
        if not self.list_page.is_mounted:
            return
        current_page, page_size = self.list_page.page_and_size()
        result = await self.search_roles(
            page=current_page,
            page_size=page_size,
            keyword=self.list_page.search_state.keyword,
        )
        roles = result.get("roles", [])
        self.list_page.apply_items(
            roles if isinstance(roles, list) else [],
            total=int(result.get("total", 0)),
            row_mapper=format_role_for_display,
        )
