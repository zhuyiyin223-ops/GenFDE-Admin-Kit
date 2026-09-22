"""登录页面入口。"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import RedirectResponse
from nicegui import app, ui

from modules.layout.styles import apply_layout_styles

from .page_controller import LoginPageController
from .page_forms import LOGIN_PAGE_CSS, build_login_form


@ui.page("/login")
async def login_page(request: Request, redirect_to: str = "/") -> RedirectResponse | None:
    """构建登录页，不直接承载业务逻辑。"""
    if app.storage.user.get("authenticated", False):
        return RedirectResponse("/")

    apply_layout_styles()
    ui.add_head_html(LOGIN_PAGE_CSS)
    controller = LoginPageController(redirect_to=redirect_to, request=request)
    form_refs = build_login_form(on_submit=controller.try_login)
    controller.userid_input = form_refs.userid_input
    controller.password_input = form_refs.password_input
    return None


@ui.page("/logout")
async def logout_page() -> None:
    """退出登录。"""
    await LoginPageController.logout()
