"""请求日志中间件。"""

from __future__ import annotations

import time

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


_SKIP_PREFIXES = ("/_nicegui/", "/static/")
_SKIP_PATHS = {"/favicon.ico"}


class LoggingMiddleware(BaseHTTPMiddleware):
    """记录请求耗时和异常。"""

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path in _SKIP_PATHS or path.startswith(_SKIP_PREFIXES):
            return await call_next(request)

        started_at = time.perf_counter()
        real_ip = getattr(request.state, "real_ip", None) or (
            request.client.host if request.client else "-"
        )
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = _elapsed_ms(started_at)
            logger.exception("{} {} 失败 {}ms {}", request.method, path, elapsed_ms, real_ip)
            raise

        elapsed_ms = _elapsed_ms(started_at)
        message = "{} {} {} {}ms {}"
        args = (request.method, path, response.status_code, elapsed_ms, real_ip)
        if response.status_code >= 500:
            logger.error(message, *args)
        elif response.status_code >= 400:
            logger.warning(message, *args)
        else:
            logger.info(message, *args)
        return response


def _elapsed_ms(started_at: float) -> int:
    """计算已耗时毫秒。"""
    return int((time.perf_counter() - started_at) * 1000)
