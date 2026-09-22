"""装配层：定时任务闭集注册。

对照 ``routes.py``。平台运维任务（库备份）实现放本包；
业务任务只注册并调用所属域 service，不纳入同一事务、不依赖其 page。
触发时刻来自 settings.CRON，不在本模块硬编码。
新增业务定时任务：命令写在所属域 service，再在本文件注册；不要为此新建业务域。
"""

from collections.abc import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from modules.sys_log.service import LogService
from settings import CRON

from .database_backup import database_backup
from .timezone import scheduler_tz

scheduler = AsyncIOScheduler(timezone=scheduler_tz)


def _add_daily_job(*, func: Callable[..., object], at: str, job_id: str) -> None:
    """按每日 HH:MM 注册单实例 cron 任务。"""
    hour, minute = (int(part) for part in at.split(":"))
    scheduler.add_job(
        func=func,
        trigger="cron",
        hour=hour,
        minute=minute,
        timezone=scheduler_tz,
        id=job_id,
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )


async def _archive_and_cleanup_user_logs() -> None:
    """调用系统日志域的归档命令；失败不影响调度器。"""
    try:
        await LogService.archive_and_cleanup_user_logs()
    except Exception:
        logger.exception("操作日志归档清理任务执行失败")


_add_daily_job(func=database_backup, at=CRON.database_backup_at, job_id="database_backup")
_add_daily_job(
    func=_archive_and_cleanup_user_logs,
    at=CRON.user_log_archive_at,
    job_id="user_log_archive_cleanup",
)
