"""应用组件注册入口。"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _register_middlewares(application: Any) -> None:
    """按既有顺序注册函数式和类式中间件。"""
    from modules.middleware import AuthMiddleware, LoggingMiddleware, RealIPMiddleware
    from modules.middleware.api_request_log import api_request_log_middleware

    application.middleware("http")(api_request_log_middleware)
    application.add_middleware(LoggingMiddleware)
    application.add_middleware(AuthMiddleware)
    application.add_middleware(RealIPMiddleware)


def _register_api_routes(application: Any) -> None:
    """注册对外 API 路由。"""
    from apis.auth import router as auth_router
    from apis.health import router as health_router

    application.include_router(health_router)
    application.include_router(auth_router)


def _register_static_files(application: Any, project_root: Path) -> None:
    """挂载应用静态文件目录。"""
    application.add_static_files("/static", project_root / "static")


def configure_application(application: Any, project_root: Path) -> None:
    """完成页面、中间件、路由、静态资源和生命周期装配。"""
    from nicegui import run as nicegui_run

    from modules.application.lifecycle import create_data_directories, register_lifecycle
    from modules.application.log_setup import setup_logging
    from modules.routes import register_page_routes
    from settings import UI

    nicegui_run.process_pool_start_method = "spawn"
    application.colors(**UI.as_colors())
    setup_logging()
    create_data_directories(project_root)
    register_page_routes()
    _register_middlewares(application)
    _register_api_routes(application)
    _register_static_files(application, project_root)
    register_lifecycle(application)
