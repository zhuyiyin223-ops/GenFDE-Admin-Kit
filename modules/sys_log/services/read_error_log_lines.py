"""业务域事务用例：读取错误日志尾部。"""

from __future__ import annotations

import asyncio
from collections import deque
from pathlib import Path

from settings import LOG


def _read_log_tail(*, file_path: Path, limit: int) -> list[str]:
    """读取日志文件尾部行，避免整文件读入内存。"""
    tail: deque[str] = deque(maxlen=max(1, int(limit)))
    with file_path.open("r", encoding="utf-8", errors="ignore") as file_obj:
        for line in file_obj:
            tail.append(line.rstrip("\n"))
    if not tail:
        return ["[空日志]"]
    lines = list(tail)
    lines.reverse()
    return lines


async def read_error_log_lines(limit: int = 500) -> list[str]:
    """读取错误日志末尾若干行并按新到旧返回。"""
    file_path = LOG.error_file
    if not file_path.exists():
        return [f"[日志文件不存在] {file_path}"]
    return await asyncio.to_thread(
        _read_log_tail,
        file_path=file_path,
        limit=limit,
    )
