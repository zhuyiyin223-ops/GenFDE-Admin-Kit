"""认证中间件。"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import Request
from fastapi.responses import RedirectResponse
from nicegui import app
from starlette.middleware.base import BaseHTTPMiddleware

from models import User
from modules.theme.service import ThemeService

UNRESTRICTED_ROUTES = {"/login", "/logout"}
UNRESTRICTED_PREFIXES = {"/static", "/_nicegui", "/api"}


class AuthMiddleware(BaseHTTPMiddleware):
    """限制未登录用户访问后台页面。"""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if self._is_unrestricted(path):
            return await call_next(request)

        if not app.storage.user.get("authenticated", False):
            return RedirectResponse(f"/login?redirect_to={quote(path, safe='/')}")

        user_id = app.storage.user.get("user_id")
        alternative_id = app.storage.user.get("alternative_id")
        if not isinstance(user_id, int) or not alternative_id:
            ThemeService.clear_session_keep_theme()
            return RedirectResponse("/login")

        is_active = await User.filter(
            id=user_id,
            is_active=True,
            alternative_id=str(alternative_id),
        ).exists()
        if not is_active:
            ThemeService.clear_session_keep_theme()
            return RedirectResponse("/login")

        return await call_next(request)

    @staticmethod
    def _is_unrestricted(path: str) -> bool:
        """判断请求路径是否无需登录。"""
        if path in UNRESTRICTED_ROUTES:
            return True
        return any(path.startswith(prefix) for prefix in UNRESTRICTED_PREFIXES)
