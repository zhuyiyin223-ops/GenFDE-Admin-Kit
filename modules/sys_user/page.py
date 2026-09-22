"""用户账号页面与附件访问入口。"""

from __future__ import annotations

from fastapi import HTTPException
from nicegui import app, ui
from starlette.responses import FileResponse

from modules.layout import create_layout
from modules.list_page import event_row
from modules.permission.definitions import PermissionItem
from modules.permission.guard import check_permission, require_permission

from .page_controller import UserPageController
from .page_table import build_user_table
from .service import UserAttachmentService


@app.get("/sys/user/attachments/{attachment_id}/content")
async def get_user_attachment_content(
    attachment_id: int,
    download: bool = False,
) -> FileResponse:
    """向有用户查看权限的登录账号返回附件内容。"""
    if not await check_permission(PermissionItem.SYS_USER_QUERY.code):
        raise HTTPException(status_code=403, detail="没有查看用户附件的权限")

    attachment_file = await UserAttachmentService.get_attachment_file(attachment_id)
    if attachment_file is None:
        raise HTTPException(status_code=404, detail="附件不存在")

    record, file_path = attachment_file
    return FileResponse(
        file_path,
        media_type=str(record.content_type or "application/octet-stream"),
        filename=str(record.original_name or file_path.name),
        content_disposition_type="attachment" if download else "inline",
    )


@require_permission(PermissionItem.SYS_USER_QUERY.code)
async def user_query_page() -> None:
    """构建用户账号页面，不直接承载业务逻辑。"""
    controller = UserPageController()
    can_edit = await check_permission(PermissionItem.SYS_USER_EDIT.code)
    can_export = await check_permission(PermissionItem.SYS_USER_EXPORT.code)
    list_page = controller.list_page

    with list_page.render_toolbar(
        title="用户账号",
        on_export=controller.export_to_excel if can_export else None,
    ):
        if can_edit:
            ui.button(
                "新增账号",
                icon="add",
                color="primary",
                on_click=controller.open_add_dialog,
            ).classes("font-bold").props("rounded")

    list_page.mount(build_user_table(can_edit=can_edit))
    controller.add_dialog = ui.dialog()
    controller.edit_dialog = ui.dialog()
    controller.attachment_dialog = ui.dialog()

    async def handle_preview_attachments(event_args):
        """打开当前用户的附件查看。"""
        user_data = event_row(event_args)
        if user_data is not None:
            await controller.open_attachment_preview(user_data)
            return
        ui.notify("无法获取用户数据", type="negative")

    list_page.table.on("preview-user-attachments", handle_preview_attachments)

    if can_edit:
        async def handle_edit_user(event_args):
            user_data = event_row(event_args)
            if user_data is not None:
                await controller.open_edit_dialog(user_data)
                return
            ui.notify("无法获取用户数据", type="negative")

        async def handle_user_attachments(event_args):
            """打开当前用户的附件上传弹框。"""
            user_data = event_row(event_args)
            if user_data is not None:
                await controller.open_attachment_dialog(user_data)
                return
            ui.notify("无法获取用户数据", type="negative")

        list_page.table.on("edit-user", handle_edit_user)
        list_page.table.on("manage-user-attachments", handle_user_attachments)

    await list_page.initialize()
    await controller.update_table()


create_layout(user_query_page, path="/sys/user")
