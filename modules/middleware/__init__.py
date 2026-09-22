"""装配层：认证、请求日志、真实 IP 等请求链。"""

from __future__ import annotations

from typing import Any

__all__ = ["AuthMiddleware", "LoggingMiddleware", "RealIPMiddleware"]


def __getattr__(name: str) -> Any:
    """延迟导入中间件实现，避免包初始化阶段循环依赖。"""
    if name == "AuthMiddleware":
        from .auth import AuthMiddleware

        return AuthMiddleware
    if name == "LoggingMiddleware":
        from .logger import LoggingMiddleware

        return LoggingMiddleware
    if name == "RealIPMiddleware":
        from .real_ip import RealIPMiddleware

        return RealIPMiddleware
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
