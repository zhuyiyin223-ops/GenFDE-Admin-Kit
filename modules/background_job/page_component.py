"""系统能力：后台任务进度条。"""

from __future__ import annotations

from nicegui import ui

from .service import BackgroundJob


def bind_job_progress(
    job: BackgroundJob,
    *,
    show_value: bool = True,
    indeterminate: bool = False,
) -> ui.linear_progress:
    """把线性进度条绑定到任务状态；任务未运行时隐藏。"""
    bar = ui.linear_progress(show_value=show_value).props("instant-feedback")
    if indeterminate:
        bar.props("indeterminate")
    else:
        bar.bind_value_from(job, "progress")
    bar.bind_visibility_from(job, "is_running")
    return bar
