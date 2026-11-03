"""业务域事务用例：读取用户附件文件。"""

from __future__ import annotations

import asyncio
from pathlib import Path

from models import UserAttachment

from .attachment_storage import resolve_storage_path


async def get_attachment_file(attachment_id: int) -> tuple[UserAttachment, Path] | None:
    """读取附件记录并返回经过目录边界校验的本地路径。"""
    record = await UserAttachment.filter(id=int(attachment_id)).first()
    if record is None:
        return None
    file_path = resolve_storage_path(record.storage_path)
    if file_path is None or not await asyncio.to_thread(file_path.is_file):
        return None
    return record, file_path
