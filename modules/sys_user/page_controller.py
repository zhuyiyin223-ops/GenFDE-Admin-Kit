"""sys_user 页面控制器。"""

from __future__ import annotations

from typing import Any

from nicegui import app, ui

from models import OperationType
from modules.excel.page_component import download_excel, set_export_loading
from modules.list_page import DEFAULT_PAGE_SIZE, ListPageFacade
from modules.log_audit import write_user_log
from modules.permission.definitions import PermissionItem
from modules.permission.guard import check_permission
from modules.ui.attachment_types import AttachmentItem
from modules.ui.helpers import clear_element

from .page_forms import (
    UserFormRefs,
    build_form_initial,
    build_user_form,
    collect_form_data,
    is_password_policy_valid,
    render_user_attachment_dialog,
    render_user_attachment_preview,
)
from .page_table import USER_LIST_SPEC, format_user_for_display
from .service import UserAttachmentService, UserService

DEFAULT_STATUS = None


async def load_role_options(*, include_role_ids: list[int] | None = None) -> dict[int, str]:
    """加载角色选项，仅返回页面构建所需数据。"""
    try:
        return await UserService.get_role_options(include_role_ids=include_role_ids)
    except Exception as exc:
        ui.notify(f"加载角色数据失败: {exc!s}", type="negative")
        return {}


class UserPageController:
    """用户查询、新增、编辑与附件管理控制器。"""

    def __init__(self) -> None:
        """初始化页面状态，不负责创建具体 UI 组件。"""
        self.list_page = ListPageFacade(
            spec=USER_LIST_SPEC,
            on_refresh=self.update_table,
            on_scheme_reset=self._on_scheme_reset,
        )
        self.status: bool | None = DEFAULT_STATUS
        self.add_dialog = None
        self.edit_dialog = None
        self.attachment_dialog = None

    def _on_scheme_reset(self) -> None:
        """方案套用时清掉域内额外筛选。"""
        self.status = DEFAULT_STATUS

    @staticmethod
    async def search_users(
            page: int = 1,
            page_size: int = DEFAULT_PAGE_SIZE,
            keyword: str | None = None,
            status: bool | None = None,
            column_filters: Any = None,
            column_filter_specs: Any = (),
    ) -> dict[str, Any]:
        """透传用户查询到 service，不在页面层拼装查询逻辑。"""
        result = await UserService.search_users(
            page=page,
            page_size=page_size,
            keyword=keyword,
            status=status,
            column_filters=column_filters,
            column_filter_specs=column_filter_specs,
        )
        await write_user_log(
            user_id=int(app.storage.user.get("user_id") or 0),
            module="用户账号查询",
            operation_type=OperationType.READ,
            action="查询用户账号",
            note={"keyword": keyword, "status": status},
        )
        return result

    @staticmethod
    def _render_user_dialog(
            dialog: Any,
            *,
            title: str,
            role_options: dict[int, str],
            on_save: Any,
            initial: dict[str, Any] | None = None,
            include_password: bool,
            include_status_switch: bool = False,
            include_reset_password: bool = False,
            readonly_userid: bool = False,
            show_password_generator: bool = False,
    ) -> None:
        """渲染用户弹窗内容，不负责打开弹窗或加载数据。"""
        clear_element(dialog)
        with dialog, ui.card().classes(
                "max-h-[92vh] w-[980px] max-w-[96vw] overflow-y-auto rounded-2xl shadow-xl"
        ):
            with ui.column().classes("w-full gap-3 p-6 max-[640px]:p-4"):
                with ui.row().classes("w-full items-start justify-between gap-3"):
                    with ui.column().classes("gap-0.5"):
                        ui.label(title).classes("text-xl font-bold")
                    ui.button(icon="close", on_click=dialog.close).props("flat round dense")

                form = build_user_form(
                    role_options,
                    initial=initial,
                    include_password=include_password,
                    include_status_switch=include_status_switch,
                    include_reset_password=include_reset_password,
                    readonly_userid=readonly_userid,
                    show_password_generator=show_password_generator,
                )

                with ui.row().classes("w-full justify-end items-center gap-3 pt-5 mt-1"):
                    ui.button("保存", icon="save", on_click=lambda: on_save(form)).props(
                        "rounded unelevated no-caps"
                    ).classes("px-5 mt-1")

    async def export_to_excel(self) -> None:
        """按当前筛选导出用户账号并触发下载。"""
        if not await check_permission(PermissionItem.SYS_USER_EXPORT.code):
            ui.notify("没有导出权限", type="negative")
            return
        set_export_loading(self.list_page.export_button, True)
        try:
            excel_file = await UserService.export_users(
                keyword=self.list_page.search_state.keyword,
                status=self.status,
                **self.list_page.filter_kwargs(),
            )
            if not download_excel(excel_file):
                return
            await write_user_log(
                user_id=int(app.storage.user.get("user_id") or 0),
                module="用户账号",
                operation_type=OperationType.EXPORT,
                action="导出用户账号",
                note={"keyword": self.list_page.search_state.keyword, "status": self.status},
            )
        except Exception as exc:
            ui.notify(f"导出失败: {exc}", type="negative")
        finally:
            set_export_loading(self.list_page.export_button, False)

    async def save_new_user(self, form: UserFormRefs) -> None:
        """保存新增用户，不在这里构建弹窗。"""
        form_data = collect_form_data(form)
        if not form_data.userid or not form_data.username or not form_data.password:
            ui.notify("请填写必填字段：账号、用户名和密码", type="negative")
            return
        if not is_password_policy_valid(form_data.password):
            ui.notify("密码必须为6到16位，包含大小写字母、数字、特殊符号", type="negative")
            return
        if not form_data.is_admin and not form_data.role_ids:
            ui.notify("非管理员账号必须分配至少一个角色", type="negative")
            return

        success, message, user = await UserService.create_user(
            userid=form_data.userid,
            password=form_data.password,
            name=form_data.username,
            role_ids=form_data.role_ids,
            is_admin=form_data.is_admin,
        )
        if not success:
            ui.notify(message, type="negative")
            return

        ui.notify("用户创建成功", type="positive")
        await write_user_log(
            user_id=int(app.storage.user.get("user_id") or 0),
            module="用户账号",
            operation_type=OperationType.CREATE,
            action="新增用户账号",
            after_change={
                "id": int(user.id) if user else None,
                "userid": form_data.userid,
                "name": form_data.username,
            },
        )
        self.add_dialog.close()
        await self.update_table()

    async def save_edit_user(self, form: UserFormRefs, user_id: int) -> None:
        """保存编辑用户，不在这里查询用户详情。"""
        form_data = collect_form_data(form)
        if not form_data.userid or not form_data.username:
            ui.notify("请填写必填字段：账号和用户名", type="negative")
            return
        if not form_data.is_admin and not form_data.role_ids:
            ui.notify("非管理员账号必须分配至少一个角色", type="negative")
            return
        if form_data.reset_password and not form_data.password:
            ui.notify("已开启重置密码，请输入新密码", type="negative")
            return
        if form_data.reset_password and not is_password_policy_valid(form_data.password):
            ui.notify("新密码必须为6到16位，包含大小写字母、数字、特殊符号", type="negative")
            return

        success, message = await UserService.update_user(
            user_id=user_id,
            userid=form_data.userid,
            name=form_data.username,
            is_admin=form_data.is_admin,
            role_ids=form_data.role_ids,
            is_active=form_data.is_active,
            reset_password=form_data.reset_password,
            new_password=form_data.password if form_data.reset_password else None,
        )
        if not success:
            ui.notify(message, type="negative")
            return

        ui.notify(message, type="positive")
        await write_user_log(
            user_id=int(app.storage.user.get("user_id") or 0),
            module="用户账号",
            operation_type=OperationType.UPDATE,
            action="编辑用户账号",
            after_change={
                "id": user_id,
                "userid": form_data.userid,
                "name": form_data.username,
            },
        )
        self.edit_dialog.close()
        await self.update_table()

    async def upload_user_attachments(
            self,
            *,
            user_id: int,
            userid: str,
            attachments: list[AttachmentItem],
    ) -> bool:
        """保存附件管理弹框中新选择的附件，并刷新列表数量。"""
        try:
            await UserAttachmentService.save_attachments(
                user_id=user_id,
                userid=userid,
                attachments=attachments,
            )
        except ValueError as exc:
            ui.notify(str(exc), type="negative")
            return False
        except Exception:
            ui.notify("附件上传失败，请检查存储目录及数据库结构", type="negative")
            return False

        await write_user_log(
            user_id=int(app.storage.user.get("user_id") or 0),
            module="用户账号",
            operation_type=OperationType.UPLOAD,
            action="上传用户附件",
            after_change={
                "user_id": user_id,
                "attachment_count": len(attachments),
                "file_names": [attachment.file_name for attachment in attachments],
            },
        )
        await self.update_table()
        return True

    async def open_add_dialog(self) -> None:
        """打开新增用户弹窗，不负责保存实现。"""
        if not self.add_dialog:
            self.add_dialog = ui.dialog()

        role_options = await load_role_options()
        self._render_user_dialog(
            self.add_dialog,
            title="新增账号",
            role_options=role_options,
            include_password=True,
            show_password_generator=True,
            on_save=self.save_new_user,
        )
        self.add_dialog.open()

    async def open_edit_dialog(self, row: dict[str, Any]) -> None:
        """打开编辑用户弹窗，不负责权限检查。"""
        if not row or not row.get("id"):
            ui.notify("无法获取用户信息", type="negative")
            return

        user_id = int(row["id"])
        user_detail = await UserService.get_user_detail(user_id)
        if not user_detail:
            ui.notify("用户不存在", type="negative")
            return

        if not self.edit_dialog:
            self.edit_dialog = ui.dialog()

        role_options = await load_role_options(include_role_ids=user_detail.get("role_ids", []))
        self._render_user_dialog(
            self.edit_dialog,
            title="编辑账号",
            role_options=role_options,
            initial=build_form_initial(user_detail),
            include_password=True,
            include_status_switch=True,
            include_reset_password=True,
            readonly_userid=True,
            on_save=lambda form: self.save_edit_user(form, user_id),
        )
        self.edit_dialog.open()

    async def open_attachment_dialog(self, row: dict[str, Any]) -> None:
        """打开仅负责上传的用户附件弹框。"""
        if not row or not row.get("id"):
            ui.notify("无法获取用户信息", type="negative")
            return

        user_id = int(row["id"])
        userid = str(row.get("userid") or "")
        username = str(row.get("name") or "")

        if not self.attachment_dialog:
            self.attachment_dialog = ui.dialog()

        render_user_attachment_dialog(
            self.attachment_dialog,
            userid=userid,
            username=username,
            on_upload=lambda items: self.upload_user_attachments(
                user_id=user_id,
                userid=userid,
                attachments=items,
            ),
        )
        self.attachment_dialog.open()

    async def open_attachment_preview(self, row: dict[str, Any]) -> None:
        """打开当前用户的附件查看。"""
        if not row or not row.get("id"):
            ui.notify("无法获取用户信息", type="negative")
            return

        try:
            attachments = await UserAttachmentService.list_attachments(int(row["id"]))
        except Exception:
            ui.notify("附件加载失败，请确认数据库迁移已执行", type="negative")
            return
        render_user_attachment_preview(attachments)

    async def update_table(self) -> None:
        """按当前查询状态刷新表格和分页器。"""
        current_page, page_size = self.list_page.page_and_size()
        result = await self.search_users(
            page=current_page,
            page_size=page_size,
            keyword=self.list_page.search_state.keyword,
            status=self.status,
            **self.list_page.filter_kwargs(),
        )
        users = result.get("users", [])
        self.list_page.apply_items(
            users if isinstance(users, list) else [],
            total=int(result.get("total", 0)),
            row_mapper=format_user_for_display,
        )
