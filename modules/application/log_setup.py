"""应用日志初始化。

将标准库 logging 转发到 loguru，并统一控制台 / 文件输出。
本模块只负责日志装配，不承载业务逻辑。
"""

from __future__ import annotations

import inspect
import logging
import sys
from typing import Any

from loguru import logger

from settings import LOG

_FILE_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {message}"
_CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level:<7}</level> | "
    "<level>{message}</level>"
)
_NOISY_LOGGERS = (
    "uvicorn.access",
    "watchfiles",
    "watchfiles.main",
    "asyncio",
    "tortoise",
)

_sinks_configured = False


class InterceptHandler(logging.Handler):
    """把标准库 logging 记录转发到 loguru。"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging() -> None:
    """配置 loguru，并把标准库日志接入同一通道。

    可重复调用：文件 sink 只装配一次；标准库拦截每次都会重装，
    避免 uvicorn 启动后重新占用 logging handlers。
    """
    global _sinks_configured
    if not _sinks_configured:
        _configure_sinks()
        _sinks_configured = True
    _intercept_stdlib_logging()


def _configure_sinks() -> None:
    """装配 loguru 控制台和文件输出。"""
    LOG.directory.mkdir(parents=True, exist_ok=True)
    logger.remove()

    logger.add(
        sys.stderr,
        level=LOG.level,
        format=_CONSOLE_FORMAT,
        backtrace=False,
        diagnose=False,
    )
    logger.add(
        str(LOG.app_file),
        level=LOG.level,
        format=_FILE_FORMAT,
        rotation=LOG.rotation,
        retention=LOG.retention,
        encoding="utf-8",
        enqueue=True,
        backtrace=False,
        diagnose=False,
        filter=_is_app_record,
    )
    logger.add(
        str(LOG.error_file),
        level="ERROR",
        format=_FILE_FORMAT,
        rotation=LOG.rotation,
        retention=LOG.retention,
        encoding="utf-8",
        enqueue=True,
        backtrace=False,
        diagnose=False,
        filter=_is_error_record,
    )
    logger.add(
        str(LOG.backup_file),
        level="INFO",
        format=_FILE_FORMAT,
        rotation=LOG.rotation,
        retention=LOG.retention,
        encoding="utf-8",
        enqueue=True,
        backtrace=False,
        diagnose=False,
        filter=_is_database_backup_record,
    )


def _is_database_backup_record(record: dict[str, Any]) -> bool:
    """只把数据库备份任务日志写入 database_backup.log。"""
    return record["extra"].get("logger_type") == "database_backup"


def _is_app_record(record: dict[str, Any]) -> bool:
    """全量日志排除备份专用通道，避免与 database_backup.log 重复。"""
    return record["extra"].get("logger_type") != "database_backup"


def _is_error_record(record: dict[str, Any]) -> bool:
    """只把 ERROR 及以上写入 error.log。"""
    return record["level"].no >= 40


def _intercept_stdlib_logging() -> None:
    """清空标准库 handler，统一转发到 loguru。"""
    intercept = InterceptHandler()
    logging.root.handlers = [intercept]
    logging.root.setLevel(logging.INFO)

    for name in list(logging.root.manager.loggerDict):
        std_logger = logging.getLogger(name)
        std_logger.handlers = []
        std_logger.propagate = True

    for name in _NOISY_LOGGERS:
        noisy_logger = logging.getLogger(name)
        noisy_logger.handlers = []
        noisy_logger.propagate = True
        noisy_logger.setLevel(logging.WARNING)
