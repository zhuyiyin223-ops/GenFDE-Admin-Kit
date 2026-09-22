"""业务域：示例事项页面入口。对照 AGENTS.md「新增业务域」复制本页结构。"""

from __future__ import annotations

from nicegui import ui

from modules.layout import create_layout
from modules.list_page import event_row
from modules.permission.definitions import PermissionItem
from modules.permission.guard import check_permission, require_permission

from .page_controller import ExamplePageController
from .page_table import build_item_table


@require_permission(PermissionItem.EXAMPLE_QUERY.code)
async def example_item_page() -> None:
    """构建示例事项页面。"""
    controller = ExamplePageController()
    can_edit = await check_permission(PermissionItem.EXAMPLE_EDIT.code)
    list_page = controller.list_page

    with list_page.render_toolbar(title="示例事项"):
        if can_edit:
            ui.button(
                "新增事项",
                icon="add",
                color="primary",
                on_click=controller.open_add_dialog,
            ).classes("font-bold").props("rounded")

    list_page.mount(build_item_table(can_edit=can_edit))
    controller.add_dialog = ui.dialog()
    controller.edit_dialog = ui.dialog()
    controller.delete_dialog = ui.dialog()

    if can_edit:
        async def handle_edit_item(event_args):
            item = event_row(event_args)
            if item is not None:
                await controller.open_edit_dialog(item)
                return
            ui.notify("无法获取事项数据", type="negative")

        async def handle_delete_item(event_args):
            item = event_row(event_args)
            if item is not None:
                await controller.open_delete_dialog(item)
                return
            ui.notify("无法获取事项数据", type="negative")

        list_page.table.on("edit-item", handle_edit_item)
        list_page.table.on("delete-item", handle_delete_item)

    await list_page.initialize()
    await controller.update_table()


create_layout(example_item_page, path="/example/item")
