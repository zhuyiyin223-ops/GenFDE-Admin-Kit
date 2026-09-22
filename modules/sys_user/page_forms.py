"""用户账号表单与附件弹框相关能力。"""

from __future__ import annotations

import random
import secrets
import string
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from inspect import isawaitable
from typing import Any

from nicegui import ui

from modules.ui.attachment_display import build_attachment_display
from modules.ui.attachment_types import AttachmentItem, is_image_attachment
from modules.ui.attachment_upload import build_attachment_upload
from modules.ui.helpers import clear_element

from .service import USER_ATTACHMENT_MAX_FILES, USER_ATTACHMENT_MAX_SIZE, UserService

DEFAULT_PASSWORD_LENGTH = 6
PASSWORD_SPECIAL_CHARS = "!@#$%^&*"
PASSWORD_CHARS = string.ascii_letters + string.digits + PASSWORD_SPECIAL_CHARS


def _not_blank(value: Any) -> bool:
    return bool(str(value or "").strip())


def _max_len(max_len: int):
    return lambda value: len(str(value or "")) <= max_len


def is_password_policy_valid(password: str) -> bool:
    """复用 service 层密码规则，不在页面层重复维护细节。"""
    return UserService.is_password_policy_valid(password)


USERID_VALIDATION = {
    "不能为空": _not_blank,
    "长度不能超过32个字符": _max_len(32),
}

USERNAME_VALIDATION = {
    "不能为空": _not_blank,
    "长度不能超过32个字符": _max_len(32),
}

PASSWORD_VALIDATION = {
    "必须为6到16位": (
        lambda value: 6 <= len(str(value or "").strip()) <= 16 if value else True
    ),
    "需包含大小写字母、数字、特殊符号": (
        lambda value: is_password_policy_valid(str(value or "")) if value else True
    ),
}


def generate_password(length: int = DEFAULT_PASSWORD_LENGTH) -> str:
    """生成符合当前策略的密码，不负责写回 UI。"""
    length = DEFAULT_PASSWORD_LENGTH if length != DEFAULT_PASSWORD_LENGTH else length
    random_chars = []

    def pick_unique(pool: str) -> str:
        while True:
            char = secrets.choice(pool)
            if char not in random_chars:
                return char

    random_chars.append(pick_unique(string.ascii_uppercase))
    random_chars.append(pick_unique(string.ascii_lowercase))
    random_chars.append(pick_unique(string.digits))
    random_chars.append(pick_unique(PASSWORD_SPECIAL_CHARS))

    while len(random_chars) < length:
        random_chars.append(pick_unique(PASSWORD_CHARS))

    random.SystemRandom().shuffle(random_chars)
    return "".join(random_chars)


def normalize_int_ids(value: Any) -> list[int]:
    """将选择值归一化为整数列表，忽略非法值。"""
    if not value:
        return []
    values = value if isinstance(value, list) else [value]
    normalized_ids: list[int] = []
    for item in values:
        try:
            item_id = int(item)
        except (TypeError, ValueError):
            continue
        if item_id not in normalized_ids:
            normalized_ids.append(item_id)
    return normalized_ids


@dataclass
class UserFormRefs:
    """用户表单组件引用，仅用于页面层取值。"""

    userid: Any
    username: Any
    is_admin: Any
    role_select: Any
    password: Any = None
    is_active: Any = None
    reset_password: Any = None


@dataclass
class UserFormData:
    """用户表单归一化结果，仅负责 UI 输入到 service 参数的映射。"""

    userid: str
    username: str
    password: str
    is_admin: bool
    role_ids: list[int]
    is_active: bool = True
    reset_password: bool = False


def build_user_form(
    role_options: dict[int, str],
    *,
    initial: dict[str, Any] | None = None,
    include_password: bool,
    include_status_switch: bool = False,
    include_reset_password: bool = False,
    readonly_userid: bool = False,
    show_password_generator: bool = False,
) -> UserFormRefs:
    """构建用户表单，不处理保存动作和 service 调用。"""
    initial = initial or {}
    field_props = "dense outlined hide-bottom-space autocomplete=off"
    three_col_grid_classes = "grid w-full grid-cols-3 gap-3 max-[900px]:grid-cols-2 max-[640px]:grid-cols-1"

    def render_section_title(
        title: str,
        *,
        margin_top: str = "mt-5",
        include_switch: bool = False,
    ) -> Any:
        """渲染分区标题，并按需在标题后附加开关。"""
        title_switch = None
        with ui.row().classes(f"w-full items-center gap-2 mb-1 {margin_top}"):
            ui.element("div").classes("h-4 w-1 rounded-sm bg-primary")
            ui.label(title).classes("text-sm font-bold text-gray-700")
            if include_switch:
                title_switch = ui.switch().props("dense")
        return title_switch

    render_section_title("账号信息", margin_top="mt-0")

    reset_password_switch = None
    password_input = None
    is_active_checkbox = None
    with ui.element("div").classes(three_col_grid_classes):
        userid_input = ui.input(
            label="* 账号",
            placeholder="请输入账号",
            value=str(initial.get("userid") or ""),
            validation=USERID_VALIDATION,
        ).classes("w-full")
        userid_props = field_props
        if readonly_userid:
            userid_props += " readonly"
        userid_input.props(userid_props)

        username_input = ui.input(
            label="* 用户名",
            placeholder="请输入用户名",
            value=str(initial.get("username") or ""),
            validation=USERNAME_VALIDATION,
        ).classes("w-full").props(field_props)

        if include_status_switch:
            is_active_checkbox = ui.checkbox(
                "账号启用",
                value=bool(initial.get("is_active", True)),
            ).classes("self-center")

        if include_password and not include_reset_password:
            password_input = ui.input(
                label="* 密码",
                placeholder="请输入密码",
                value=str(initial.get("password") or ""),
                validation=PASSWORD_VALIDATION,
            ).classes("w-full").props(field_props)

            if show_password_generator:
                with password_input.add_slot("append"):
                    ui.button(
                        icon="refresh",
                        on_click=lambda: password_input.set_value(generate_password()),
                    ).props("flat dense round")

    render_section_title("权限与状态")
    with ui.element("div").classes(three_col_grid_classes):
        role_select = ui.select(
            options=role_options,
            label="角色",
            multiple=True,
            value=normalize_int_ids(initial.get("role_ids")),
        ).classes("w-full col-span-2 max-[640px]:col-span-1").props(
            "dense outlined use-chips hide-bottom-space autocomplete=off options-dense"
        )

        is_admin_checkbox = ui.checkbox(
            "该账号为管理员",
            value=bool(initial.get("is_admin", False)),
        ).classes("self-center")

    if include_password and include_reset_password:
        reset_password_switch = render_section_title("密码重置", include_switch=True)
        reset_password_switch.set_value(False)

        password_wrapper = ui.element("div").classes(three_col_grid_classes)
        password_wrapper.bind_visibility_from(reset_password_switch, "value")
        with password_wrapper:
            password_input = ui.input(
                label="* 新密码",
                placeholder="请输入新密码",
                value="",
                validation=PASSWORD_VALIDATION,
            ).classes("w-full").props(field_props)
            with password_input.add_slot("append"):
                ui.button(
                    icon="refresh",
                    on_click=lambda: password_input.set_value(generate_password()),
                ).props("flat dense round")

    return UserFormRefs(
        userid=userid_input,
        password=password_input,
        username=username_input,
        is_admin=is_admin_checkbox,
        role_select=role_select,
        is_active=is_active_checkbox,
        reset_password=reset_password_switch,
    )


def collect_form_data(form: UserFormRefs) -> UserFormData:
    """归一化表单输入，不负责业务校验和持久化。"""
    return UserFormData(
        userid=str(form.userid.value or "").strip(),
        username=str(form.username.value or "").strip(),
        password=str(form.password.value or "").strip() if form.password else "",
        is_admin=bool(form.is_admin.value),
        role_ids=normalize_int_ids(form.role_select.value),
        is_active=bool(form.is_active.value) if form.is_active is not None else True,
        reset_password=bool(form.reset_password.value) if form.reset_password is not None else False,
    )


def build_form_initial(user_detail: dict[str, Any]) -> dict[str, Any]:
    """将用户详情转换为表单初始值。"""
    return {
        "userid": user_detail["userid"],
        "username": user_detail["name"],
        "is_admin": user_detail["is_admin"],
        "is_active": user_detail["is_active"],
        "role_ids": user_detail["role_ids"],
    }


def render_user_attachment_dialog(
    dialog: Any,
    *,
    userid: str,
    username: str,
    on_upload: Callable[[list[AttachmentItem]], Any],
) -> None:
    """构建仅负责上传的用户附件弹框。"""
    clear_element(dialog)
    with dialog, ui.card().classes(
        "max-h-[92vh] w-[760px] max-w-[96vw] overflow-y-auto rounded-2xl shadow-xl"
    ):
        with ui.column().classes("w-full gap-3 p-6 max-[640px]:p-4"):
            with ui.row().classes("w-full items-center justify-between gap-3"):
                ui.label("附件管理").classes("text-xl font-bold")
                ui.button(icon="close", on_click=dialog.close).props("flat round dense")

            with ui.element("div").classes(
                "grid w-full grid-cols-3 gap-3 max-[640px]:grid-cols-1"
            ):
                ui.input(label="账号", value=userid).classes("w-full").props(
                    "dense outlined readonly hide-bottom-space autocomplete=off"
                )
                ui.input(label="用户名", value=username).classes("w-full").props(
                    "dense outlined readonly hide-bottom-space autocomplete=off"
                )

            async def handle_upload(items: list[AttachmentItem]) -> bool:
                """提交新增附件，成功后由上传组件清空待提交列表。"""
                upload_result = on_upload(items)
                if isawaitable(upload_result):
                    upload_result = await upload_result
                return bool(upload_result)

            build_attachment_upload(
                title="上传附件",
                max_files=USER_ATTACHMENT_MAX_FILES,
                max_file_size=USER_ATTACHMENT_MAX_SIZE,
                full_width=True,
                on_submit=handle_upload,
            )


def render_user_attachment_preview(attachments: Sequence[AttachmentItem]) -> None:
    """按签单扫描模块的方式打开附件查看。"""
    if not attachments:
        ui.notify("当前账号暂无附件", type="warning")
        return

    image_attachments = [item for item in attachments if is_image_attachment(item)]
    if image_attachments and len(image_attachments) == len(attachments):
        with ui.element("div").classes("hidden"):
            attachment_display = build_attachment_display(
                title="用户附件",
                items=attachments,
                show_title=False,
                show_empty=False,
                full_width=True,
            )
        attachment_display.open_image_lightbox()
        return

    with ui.dialog() as dialog, ui.card().classes(
        "max-h-[92vh] w-[900px] max-w-[96vw] overflow-y-auto rounded-2xl shadow-xl"
    ):
        with ui.column().classes("w-full gap-3 p-6 max-[640px]:p-4"):
            with ui.row().classes("w-full items-center justify-between gap-3"):
                ui.label("查看附件").classes("text-xl font-bold")
                ui.button(icon="close", on_click=dialog.close).props("flat round dense")
            build_attachment_display(
                title="用户附件",
                items=attachments,
                show_title=False,
                show_empty=True,
                full_width=True,
            )
    dialog.open()
