"""业务域事务用例：归档并清理操作日志。"""

from __future__ import annotations

import gzip
import json
from datetime import datetime, timedelta

from loguru import logger

from models import UserLog
from settings import PROJECT_ROOT

USER_LOG_ONLINE_RETENTION_DAYS = 90
USER_LOG_ARCHIVE_RETENTION_DAYS = 365
USER_LOG_ARCHIVE_BATCH_SIZE = 500
USER_LOG_ARCHIVE_DIR = PROJECT_ROOT / "data" / "archives" / "user_logs"


async def archive_and_cleanup_user_logs() -> dict[str, int]:
    """归档超过在线保留期的操作日志，并清理超过归档保留期的文件。"""
    archive_dir = USER_LOG_ARCHIVE_DIR
    archive_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    archive_before = now - timedelta(days=USER_LOG_ONLINE_RETENTION_DAYS)
    archive_path = archive_dir / f"user_logs_{now:%Y-%m-%d}.jsonl.gz"
    archived_count = 0

    while True:
        rows = await UserLog.filter(created_at__lt=archive_before).order_by("id").limit(
            USER_LOG_ARCHIVE_BATCH_SIZE
        ).values(
            "id",
            "operation_type",
            "module",
            "action",
            "execution_time",
            "before_change",
            "after_change",
            "note",
            "user_id",
            "created_at",
        )
        if not rows:
            break

        with gzip.open(archive_path, "at", encoding="utf-8") as archive_file:
            for row in rows:
                archive_file.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

        deleted_count = await UserLog.filter(id__in=[row["id"] for row in rows]).delete()
        if deleted_count <= 0:
            raise RuntimeError("操作日志归档完成但数据库记录未删除")
        archived_count += int(deleted_count)
        if len(rows) < USER_LOG_ARCHIVE_BATCH_SIZE:
            break

    archive_expire_at = now - timedelta(days=USER_LOG_ARCHIVE_RETENTION_DAYS)
    deleted_archive_count = 0
    for archive_file in archive_dir.glob("user_logs_*.jsonl.gz"):
        if archive_file.stat().st_mtime < archive_expire_at.timestamp():
            archive_file.unlink()
            deleted_archive_count += 1

    logger.info(
        "操作日志归档清理完成：归档并删除 {} 条，清理归档文件 {} 个",
        archived_count,
        deleted_archive_count,
    )
    return {
        "archived_count": archived_count,
        "deleted_archive_count": deleted_archive_count,
    }
