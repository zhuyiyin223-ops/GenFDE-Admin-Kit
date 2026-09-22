"""登录页面控制器。"""

from __future__ import annotations

from fastapi import Request
from nicegui import app, ui

from models import OperationType
from modules.log_audit import write_user_log
from modules.permission.service import PermissionService
from modules.theme.service import ThemeService

from .service import LoginService


class LoginPageController:
    """登录与退出的页面状态和事件编排。"""

    def __init__(self, *, redirect_to: str = "/", request: Request | None = None) -> None:
        self.redirect_to = redirect_to
        self.request = request
        self.userid_input = None
        self.password_input = None

    async def try_login(self, _event: object = None) -> None:
        """校验账号并建立登录态。"""
        userid = str(getattr(self.userid_input, "value", None) or "").strip()
        password = str(getattr(self.password_input, "value", None) or "")
        if not userid or not password:
            ui.notify("请输入账号和密码", color="warning")
            return

        ip_addr = _client_ip(self.request)
        try:
            user = await LoginService.authenticate_user(userid=userid, password=password, ip_addr=ip_addr)
        except RuntimeError as exc:
            ui.notify(str(exc), color="negative")
            return

        if user is None:
            ui.notify("用户名或密码错误", color="negative")
            return

        theme = ThemeService.bind_to_user(int(user.id))
        app.storage.user.update(
            {
                "user_id": int(user.id),
                "userid": user.userid,
                "username": user.name or user.userid,
                "is_admin": user.is_admin,
                "authenticated": True,
                "alternative_id": user.alternative_id,
                "theme_key": theme.key,
            }
        )
        PermissionService.clear_user_permission_cache(int(user.id))
        target_path = await PermissionService.get_first_accessible_path(
            int(user.id),
            preferred_path=self.redirect_to if self.redirect_to.startswith("/") else None,
        )
        await write_user_log(
            user_id=int(user.id),
            module="登录",
            operation_type=OperationType.LOGIN,
            action="登录系统",
            note={"ip": ip_addr, "userid": user.userid},
        )
        ui.navigate.to(target_path)

    @staticmethod
    async def logout() -> None:
        """清除登录态并跳转登录页。"""
        user_id = app.storage.user.get("user_id")
        userid = app.storage.user.get("userid")
        if isinstance(user_id, int):
            await write_user_log(
                user_id=user_id,
                module="登录",
                operation_type=OperationType.LOGOUT,
                action="退出系统",
                note={"userid": userid},
            )
        ThemeService.clear_session_keep_theme()
        ui.navigate.to("/login")


def _client_ip(request: Request | None) -> str | None:
    """读取请求真实 IP，没有中间件结果时回退到直连地址。"""
    if request is None:
        return None
    real_ip = str(getattr(request.state, "real_ip", "") or "").strip()
    if real_ip:
        return real_ip
    if request.client is None:
        return None
    return request.client.host
