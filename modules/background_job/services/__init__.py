"""系统能力：后台任务执行与进度状态。"""

from .job import (
    BackgroundJob,
    ProgressFunc,
    shutdown_background_jobs,
)

__all__ = [
    "BackgroundJob",
    "ProgressFunc",
    "shutdown_background_jobs",
]
