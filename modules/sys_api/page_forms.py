"""sys_api 页面表单相关能力。

本模块负责：
- 客户端表单构建；
- 表单输入归一化；
- 表单初始值转换。

本模块不负责：
- 业务持久化；
- 页面路由和权限控制；
- 表格与分页渲染。
"""

from __future__ import annotations

import secrets
import string
from dataclasses import dataclass
from typing import Any

from nicegui import ui

DEFAULT_PASSWORD_LENGTH = 20
PASSWORD_CHARS = string.ascii_letters + string.digits + "!@#$%^&*"


def _not_blank(value: Any) -> bool:
    return bool(str(value or "").strip())


def _max_len(max_len: int):
    return lambda value: len(str(value or "")) <= max_len


CLIENT_ID_VALIDATION = {
    "不能为空": _not_blank,
    "长度不能超过64个字符": _max_len(64),
}

NAME_VALIDATION = {
    "长度不能超过64个字符": _max_len(64),
}

IP_WHITELIST_VALIDATION = {
    "长度不能超过1024个字符": _max_len(1024),
}

PASSWORD_VALIDATION = {
    "密码至少8位": lambda value: len(str(value or "")) >= 8 if value else True,
}


def generate_password(length: int = DEFAULT_PASSWORD_LENGTH) -> str:
    """生成客户端密码，不负责写回 UI。"""
    return "".join(secrets.choice(PASSWORD_CHARS) for _ in range(length))


def _initial_text(initial: dict[str, Any] | None, key: str) -> str:
    return str((initial or {}).get(key) or "")


def _initial_bool(initial: dict[str, Any] | None, key: str, default: bool = False) -> bool:
    return bool((initial or {}).get(key, default))


def _build_password_input(field_props: str) -> Any:
    """构建密码输入框，右侧提供随机生成。"""
    password_input = ui.input(
        label="* 密码",
        placeholder="请输入密码",
        password=False,
        validation=PASSWORD_VALIDATION,
    ).classes("w-full").props(field_props)
    with password_input.add_slot("append"):
        ui.button(
            icon="refresh",
            on_click=lambda: password_input.set_value(generate_password()),
        ).props("flat dense round")
    return password_input


@dataclass
class ClientFormRefs:
    """客户端表单组件引用。"""

    client_id: Any
    name: Any
    password: Any = None
    ip_whitelist: Any = None
    is_active: Any = None
    reset_password: Any = None


@dataclass
class ClientFormData:
    """客户端表单归一化结果。"""

    client_id: str
    name: str
    password: str
    ip_whitelist: str
    is_active: bool
    reset_password: bool


def build_client_form(
        *,
        initial: dict[str, Any] | None = None,
        include_password: bool,
        include_status_switch: bool = False,
        include_reset_password: bool = False,
        readonly_client_id: bool = False,
) -> ClientFormRefs:
    """构建客户端表单，不处理保存动作和 service 调用。"""
    initial = initial or {}
    field_props = "dense outlined hide-bottom-space autocomplete=off"
    switch_props = "size=md autocomplete=off"

    with ui.column().classes("w-full gap-3"):
        client_id_input = ui.input(
            label="* 账号",
            placeholder="请输入账号",
            value=_initial_text(initial, "client_id"),
            validation=CLIENT_ID_VALIDATION,
        ).classes("w-full")
        client_props = field_props
        if readonly_client_id:
            client_props += " readonly"
        client_id_input.props(client_props)

        name_input = ui.input(
            label="名称",
            placeholder="请输入名称",
            value=_initial_text(initial, "name"),
            validation=NAME_VALIDATION,
        ).classes("w-full").props(field_props)

        reset_password_switch = None
        password_input = None
        if include_password and not include_reset_password:
            password_input = _build_password_input(field_props)

        ip_whitelist_input = ui.textarea(
            label="IP白名单",
            placeholder="多个IP用逗号或换行分隔，支持CIDR，如 10.0.0.0/24",
            value=_initial_text(initial, "ip_whitelist"),
            validation=IP_WHITELIST_VALIDATION,
        ).classes("w-full").props("dense outlined rows=3 hide-bottom-space autocomplete=off")

        is_active_switch = None
        show_reset_password = include_password and include_reset_password
        if include_status_switch or show_reset_password:
            with ui.row().classes("w-full items-center gap-4"):
                if include_status_switch:
                    is_active_switch = ui.switch(
                        "启用",
                        value=_initial_bool(initial, "is_active", True),
                    ).props(switch_props)
                if show_reset_password:
                    reset_password_switch = ui.switch("重置密码", value=False).props(switch_props)
        if show_reset_password:
            password_wrapper = ui.column().classes("w-full gap-2")
            password_wrapper.bind_visibility_from(reset_password_switch, "value")
            with password_wrapper:
                password_input = _build_password_input(field_props)

    return ClientFormRefs(
        client_id=client_id_input,
        name=name_input,
        password=password_input,
        ip_whitelist=ip_whitelist_input,
        is_active=is_active_switch,
        reset_password=reset_password_switch,
    )


def collect_client_form_data(form: ClientFormRefs) -> ClientFormData:
    """收集并归一化客户端表单值。"""
    return ClientFormData(
        client_id=str(form.client_id.value or "").strip(),
        name=str(form.name.value or "").strip(),
        password=str(form.password.value or "").strip() if form.password else "",
        ip_whitelist=str(form.ip_whitelist.value or "").strip() if form.ip_whitelist else "",
        is_active=bool(form.is_active.value) if form.is_active else True,
        reset_password=bool(form.reset_password.value) if form.reset_password else False,
    )
