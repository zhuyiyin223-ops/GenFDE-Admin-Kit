"""真实 IP 中间件。"""

from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class RealIPMiddleware(BaseHTTPMiddleware):
    """从常见代理头中提取客户端真实 IP。"""

    async def dispatch(self, request: Request, call_next):
        request.state.real_ip = self._get_real_ip(request)
        return await call_next(request)

    @staticmethod
    def _get_real_ip(request: Request) -> str:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        return request.client.host if request.client else ""
