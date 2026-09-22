"""装配层：应用生命周期管理。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from tortoise.contrib.fastapi import RegisterTortoise

from modules.application.database import (
    apply_migrations,
    ensure_database,
    ensure_initial_migrations,
    ensure_migrations_package,
)
from modules.application.log_setup import setup_logging
from modules.cron_job import scheduler
from modules.event_hub import EventHub
from modules.login.service import LoginService
from settings import ADMIN, APP, SECRETS, TORTOISE_ORM

RUNTIME_DATA_DIRECTORIES = (
    "data",
    "data/backups",
    "data/archives/user_logs",
    "data/upload",
)


def create_data_directories(project_root: Path) -> None:
    """同步创建应用运行期依赖的数据目录。"""
    for relative_path in RUNTIME_DATA_DIRECTORIES:
        (project_root / relative_path).mkdir(parents=True, exist_ok=True)


class ApplicationLifecycle:
    """统一管理 ORM、默认管理员和调度器的启停顺序。"""

    def __init__(self, application: Any) -> None:
        """绑定 NiceGUI 应用并创建 ORM 注册器。"""
        self.orm = RegisterTortoise(app=application, config=TORTOISE_ORM)

    async def startup(self) -> None:
        """develop 下建库并迁移，再初始化 ORM、默认管理员和调度器。"""
        setup_logging()
        EventHub.bind_loop(asyncio.get_running_loop())
        if APP.env == "develop":
            await ensure_database(SECRETS.database_url)
            ensure_migrations_package()
        await self.orm.init_orm()
        if APP.env == "develop":
            await ensure_initial_migrations()
            await apply_migrations()
        await LoginService.ensure_admin_user(
            userid=ADMIN.userid,
            password=SECRETS.admin_password,
            name=ADMIN.name,
        )
        if not scheduler.running:
            scheduler.start()

    async def shutdown(self) -> None:
        """先停止调度器与后台任务 Manager，解绑事件循环，再关闭 ORM 连接。"""
        from modules.background_job.service import shutdown_background_jobs

        if scheduler.running:
            scheduler.shutdown()
        shutdown_background_jobs()
        EventHub.bind_loop(None)
        await self.orm.close_orm()


def register_lifecycle(application: Any) -> ApplicationLifecycle:
    """注册应用启动和关闭回调，并返回生命周期对象。

    启动挂在 uvicorn 会等待的 lifespan 上，ORM 就绪后才开始接请求。
    NiceGUI 的 ``on_startup`` 不等待协程，热重载后请求会碰到尚未绑定连接的模型。
    关闭仍走 ``on_shutdown``，NiceGUI 停机时会等待该协程。
    """
    lifecycle = ApplicationLifecycle(application)
    _bind_awaited_startup(application, lifecycle.startup)
    application.on_shutdown(lifecycle.shutdown)
    return lifecycle


def _bind_awaited_startup(application: Any, startup: Callable[[], Awaitable[None]]) -> None:
    """把启动协程插进现有 lifespan，在向外宣告启动完成之前执行完。"""
    original = application.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app: Any):
        async with original(app) as state:
            await startup()
            yield state

    application.router.lifespan_context = lifespan
