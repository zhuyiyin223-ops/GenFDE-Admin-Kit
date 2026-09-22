"""角色权限页面入口。"""

from __future__ import annotations

from nicegui import ui

from modules.layout import create_layout
from modules.list_page import event_row
from modules.permission.definitions import PermissionItem
from modules.permission.guard import check_permission, require_permission

from .page_controller import RolePageController
from .page_forms import ROLE_PERMISSION_CSS
from .page_table import build_role_table


@require_permission(PermissionItem.SYS_ROLE_QUERY.code)
async def sys_role_query_page() -> None:
    """构建角色权限页面，不直接承载业务逻辑。"""
    ui.add_head_html(ROLE_PERMISSION_CSS)

    controller = RolePageController()
    can_edit = await check_permission(PermissionItem.SYS_ROLE_EDIT.code)
    can_export = await check_permission(PermissionItem.SYS_ROLE_EXPORT.code)
    list_page = controller.list_page

    with list_page.render_toolbar(
        title="角色权限",
        on_export=controller.export_to_excel if can_export else None,
    ):
        if can_edit:
            ui.button(
                "新增角色",
                icon="add",
                color="primary",
                on_click=controller.open_add_dialog,
            ).classes("font-bold").props("rounded")

    list_page.mount(build_role_table(can_edit=can_edit))
    controller.role_add_dialog = ui.dialog()
    controller.role_edit_dialog = ui.dialog()
    controller.role_relation_dialog = ui.dialog()

    if can_edit:
        async def handle_edit_role(event_args):
            """处理角色编辑事件，不负责权限鉴权。"""
            role_data = event_row(event_args)
            if role_data is not None:
                await controller.open_edit_dialog(role_data)
                return
            ui.notify("无法获取角色数据", type="negative")

        list_page.table.on("edit-role", handle_edit_role)

    def handle_view_permissions(event_args):
        """处理关联权限查看事件，不负责数据查询。"""
        role_data = event_row(event_args)
        if role_data is not None:
            controller.open_role_relation_dialog(role_data, field_name="permissions")
            return
        ui.notify("无法获取权限数据", type="negative")

    def handle_view_users(event_args):
        """处理关联用户查看事件，不负责数据查询。"""
        role_data = event_row(event_args)
        if role_data is not None:
            controller.open_role_relation_dialog(role_data, field_name="users")
            return
        ui.notify("无法获取用户数据", type="negative")

    list_page.table.on("view-permissions", handle_view_permissions)
    list_page.table.on("view-users", handle_view_users)

    await list_page.initialize()
    await controller.update_role_table()


create_layout(sys_role_query_page, path="/sys/role")
