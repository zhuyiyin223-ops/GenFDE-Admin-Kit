"""装配层：开发环境建库、生成初始迁移并执行。"""

from __future__ import annotations

import asyncio
import importlib
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg
from loguru import logger
from tortoise import Tortoise
from tortoise.connection import get_connection
from tortoise.migrations.autodetector import MigrationAutodetector
from tortoise.migrations.executor import MigrationExecutor

from settings import PROJECT_ROOT, SECRETS, TORTOISE_ORM

_DB_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MIGRATIONS_ROOT = PROJECT_ROOT / "migrations"
_MIGRATIONS_APP = _MIGRATIONS_ROOT / "models"


def _admin_dsn(database_url: str) -> tuple[str, str]:
    """把业务库 URL 拆成维护库 DSN 和目标库名。"""
    parsed = urlsplit(database_url)
    name = parsed.path.lstrip("/")
    if not name or not _DB_NAME_RE.fullmatch(name):
        raise RuntimeError(f"DATABASE_URL 库名不合法：{name or '(空)'}")
    admin = urlunsplit((parsed.scheme, parsed.netloc, "/postgres", parsed.query, parsed.fragment))
    return admin, name


def _migration_files() -> list[Path]:
    """已生成的迁移文件（不含 __init__.py）。"""
    if not _MIGRATIONS_APP.is_dir():
        return []
    return [
        path
        for path in _MIGRATIONS_APP.iterdir()
        if path.is_file() and path.suffix == ".py" and path.name != "__init__.py"
    ]


def ensure_migrations_package() -> None:
    """确保 migrations.models 包存在，供 Tortoise 加载。"""
    for directory in (_MIGRATIONS_ROOT, _MIGRATIONS_APP):
        directory.mkdir(parents=True, exist_ok=True)
        init_path = directory / "__init__.py"
        if not init_path.exists():
            init_path.write_text("", encoding="utf-8")
    importlib.invalidate_caches()


async def ensure_database(database_url: str) -> None:
    """库不存在则创建；PostgreSQL 服务本身需已启动。"""
    admin_dsn, name = _admin_dsn(database_url)
    conn = await asyncpg.connect(admin_dsn)
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", name)
        if exists:
            return
        await conn.execute(f'CREATE DATABASE "{name}"')
        logger.info("已创建数据库 {}", name)
    finally:
        await conn.close()


async def ensure_initial_migrations() -> None:
    """尚无迁移文件时，按当前模型生成初始迁移。须在 ORM 初始化之后调用。"""
    if _migration_files():
        return
    apps = Tortoise.apps
    if apps is None:
        raise RuntimeError("ORM 未初始化，无法生成迁移")
    writers = await MigrationAutodetector(apps, TORTOISE_ORM["apps"]).changes()
    if not writers:
        raise RuntimeError("当前模型没有可生成的初始迁移")
    for writer in writers:
        path = writer.write()
        logger.info("已生成迁移 {}", path)
    importlib.invalidate_caches()


async def apply_migrations() -> None:
    """执行尚未应用的迁移。须在 ORM 初始化之后调用。"""
    executor = MigrationExecutor(get_connection("default"), TORTOISE_ORM["apps"])
    await executor.migrate()


async def bootstrap_develop_database() -> None:
    """建库、生成初始迁移并执行；供命令行单独初始化。"""
    await ensure_database(SECRETS.database_url)
    ensure_migrations_package()
    await Tortoise.init(config=TORTOISE_ORM)
    try:
        await ensure_initial_migrations()
        await apply_migrations()
        logger.info("数据库已就绪")
    finally:
        await Tortoise.close_connections()


if __name__ == "__main__":
    from modules.application.log_setup import setup_logging

    setup_logging()
    asyncio.run(bootstrap_develop_database())
