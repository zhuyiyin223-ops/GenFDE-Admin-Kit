"""装配层：数据库备份。

本模块负责执行 PostgreSQL 压缩备份与过期文件清理。
不负责调度注册、业务数据同步和页面交互。
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse

from loguru import logger

from settings import PROJECT_ROOT, TORTOISE_ORM

from .timezone import scheduler_tz

BACKUP_RETENTION_DAYS = 3
MIN_FREE_BYTES = 8 * 1024**3
BACKUP_FILE_PREFIX = "db_backup_"
BACKUP_FILE_SUFFIX = ".dump"
LEGACY_BACKUP_SUFFIXES = (".sql", ".sql.gz")
MANAGED_BACKUP_SUFFIXES = (
    BACKUP_FILE_SUFFIX,
    f"{BACKUP_FILE_SUFFIX}.tmp",
    *LEGACY_BACKUP_SUFFIXES,
)

backup_dir = PROJECT_ROOT / "data" / "backups"
backup_dir.mkdir(parents=True, exist_ok=True)

backup_logger = logger.bind(logger_type="database_backup")


@dataclass(frozen=True)
class PostgresDumpTarget:
    """pg_dump 所需的连接参数。"""

    host: str
    port: str
    username: str
    password: str
    database: str


def _parse_postgres_dump_target(database_url: str) -> PostgresDumpTarget | None:
    """从数据库 URL 解析 pg_dump 连接参数。"""
    parsed = urlparse(database_url)
    scheme = parsed.scheme.split("+", 1)[0].lower()
    if scheme not in {"postgres", "postgresql"}:
        return None

    database = unquote(parsed.path.lstrip("/"))
    if not database:
        return None

    return PostgresDumpTarget(
        host=parsed.hostname or "localhost",
        port=str(parsed.port or 5432),
        username=unquote(parsed.username or ""),
        password=unquote(parsed.password or ""),
        database=database,
    )


def _is_managed_backup_file(filename: str) -> bool:
    """判断是否为备份任务产出的文件。"""
    return filename.startswith(BACKUP_FILE_PREFIX) and filename.endswith(MANAGED_BACKUP_SUFFIXES)


def _ensure_enough_disk_space(target_dir: Path) -> None:
    """备份前检查磁盘剩余空间，避免把系统盘写满。"""
    usage = shutil.disk_usage(target_dir)
    if usage.free >= MIN_FREE_BYTES:
        return
    raise OSError(f"磁盘剩余空间不足，free_bytes={usage.free}，required_bytes={MIN_FREE_BYTES}")


def _build_pg_dump_command(target: PostgresDumpTarget, output_path: Path) -> list[str]:
    """构建自定义压缩格式的 pg_dump 命令。"""
    command = [
        "pg_dump",
        "-h",
        target.host,
        "-p",
        target.port,
        "-d",
        target.database,
        "--format=custom",
        "--compress=6",
        "--no-password",
        "--file",
        str(output_path),
    ]
    if target.username:
        command.extend(["-U", target.username])
    return command


def _remove_file_quietly(path: Path) -> None:
    """删除临时或不完整备份文件，忽略文件已不存在的情况。"""
    path.unlink(missing_ok=True)


def _dump_database(target: PostgresDumpTarget, backup_path: Path) -> None:
    """将数据库备份到目标文件，失败时清理不完整临时文件。"""
    tmp_path = backup_path.with_name(f"{backup_path.name}.tmp")
    command = _build_pg_dump_command(target, tmp_path)
    env = os.environ.copy()
    if target.password:
        env["PGPASSWORD"] = target.password

    backup_logger.info("正在备份数据库 {} 到 {}", target.database, backup_path)
    try:
        subprocess.run(
            command,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        tmp_path.replace(backup_path)
    except (OSError, subprocess.CalledProcessError):
        _remove_file_quietly(tmp_path)
        raise


def database_backup(database_url: str | None = None) -> None:
    """执行数据库备份任务。

    使用 `pg_dump` 自定义压缩格式备份 PostgreSQL，
    避免明文 SQL 把文本字段膨胀数倍。
    不负责调度控制、远程上传和备份恢复。
    """
    try:
        backup_logger.info("开始执行数据库备份任务")

        if database_url is None:
            connections = TORTOISE_ORM.get("connections", {})
            database_url = connections.get("default", "")

        if not database_url:
            backup_logger.error("未提供数据库连接信息")
            return

        target = _parse_postgres_dump_target(database_url)
        if target is None:
            backup_logger.warning("未检测到 PostgreSQL 数据库配置，跳过备份")
            return

        cleanup_old_backups(backup_dir, days=BACKUP_RETENTION_DAYS)
        _ensure_enough_disk_space(backup_dir)

        timestamp = datetime.now(scheduler_tz).strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"{BACKUP_FILE_PREFIX}{timestamp}{BACKUP_FILE_SUFFIX}"
        _dump_database(target, backup_path)
        backup_logger.info(
            "数据库备份成功：{}，size_bytes={}",
            backup_path,
            backup_path.stat().st_size,
        )
        cleanup_old_backups(backup_dir, days=BACKUP_RETENTION_DAYS)
    except subprocess.CalledProcessError as exc:
        backup_logger.error("数据库备份失败：{}", (exc.stderr or "未知错误").strip())
    except OSError as exc:
        backup_logger.error("执行数据库备份任务时出错：{}", exc)
    finally:
        backup_logger.info("数据库备份任务执行完毕")


def cleanup_old_backups(
    backup_directory: str | Path,
    days: int = BACKUP_RETENTION_DAYS,
) -> None:
    """清理过期压缩备份，并删除会占满磁盘的历史明文 SQL 备份。"""
    try:
        backup_logger.info("开始清理 {} 天前的备份文件", days)
        cutoff_date = datetime.now(scheduler_tz) - timedelta(days=days)
        deleted_count = 0

        for file_path in Path(backup_directory).iterdir():
            if not file_path.is_file() or not _is_managed_backup_file(file_path.name):
                continue

            is_legacy_or_tmp = file_path.name.endswith((*LEGACY_BACKUP_SUFFIXES, ".tmp"))
            file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=scheduler_tz)
            if not is_legacy_or_tmp and file_mtime >= cutoff_date:
                continue

            file_path.unlink()
            backup_logger.info("已删除旧备份文件：{}", file_path.name)
            deleted_count += 1

        backup_logger.info("旧备份文件清理完成，删除数量：{}", deleted_count)
    except OSError as exc:
        backup_logger.error("清理旧备份文件时出错：{}", exc)
