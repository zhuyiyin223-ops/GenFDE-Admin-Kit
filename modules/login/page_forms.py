"""登录页面表单。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from nicegui import ui

from settings import APP, PROJECT_ROOT

LOGIN_ILLUSTRATION_PATH = PROJECT_ROOT / "static" / "login.svg"

LOGIN_PAGE_CSS = """
<style>
    .login-shell {
        width: min(460px, calc(100vw - 32px));
        border-radius: 26px;
        border: 1px solid var(--ng-surface-border);
        background: var(--ng-surface);
    }
    .login-brand-img {
        width: min(390px, 100%);
        height: 184px;
        color: var(--q-primary);
    }
    .login-brand-img svg {
        width: 100%;
        height: 100%;
        display: block;
    }
    .login-subtitle {
        color: var(--ng-ui-text-tertiary);
        font-size: 11px;
        letter-spacing: 0.18em;
        text-transform: uppercase;
    }
    @media (max-width: 640px) {
        .login-shell {
            width: min(100vw - 20px, 430px);
            border-radius: 22px;
        }
        .login-brand-img {
            width: min(320px, 100%);
            height: 150px;
        }
    }
</style>
"""


@dataclass
class LoginFormRefs:
    """登录表单控件引用。"""

    userid_input: Any
    password_input: Any


def build_login_form(*, on_submit: Callable[..., Any]) -> LoginFormRefs:
    """构建登录表单，不负责校验和提交。"""
    with ui.column().classes("w-full min-h-screen items-center justify-center p-6"):
        with ui.column().classes("login-shell w-full p-8 gap-6"):
            with ui.column().classes("w-full items-center"):
                _build_login_illustration()
                ui.label(APP.title).classes("text-xl font-bold text-center mt-1")
                ui.label("ADMIN FDE FRAMEWORK STARTER").classes("login-subtitle")

            with ui.column().classes("w-full gap-4"):
                userid_input = (
                    ui.input("账号")
                    .on("keydown.enter", on_submit)
                    .classes("w-full")
                    .props("dense outlined autocomplete=off")
                )
                password_input = (
                    ui.input("密码", password=True, password_toggle_button=True)
                    .on("keydown.enter", on_submit)
                    .classes("w-full")
                    .props("dense outlined autocomplete=off")
                )
                ui.button("登录", on_click=on_submit).classes("w-full h-12 font-bold mt-2").props(
                    "unelevated no-caps color=primary"
                )

    return LoginFormRefs(userid_input=userid_input, password_input=password_input)


def _build_login_illustration() -> None:
    """内联登录插画，描边跟随当前主题主色。"""
    svg = LOGIN_ILLUSTRATION_PATH.read_text(encoding="utf-8").replace("#21325B", "currentColor")
    ui.html(svg, sanitize=False).classes("login-brand-img")
