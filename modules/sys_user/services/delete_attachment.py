"""业务域事务用例：删除用户附件。"""

from __future__ import annotations

from loguru import logger

from models import UserAttachment

from .attachment_storage import delete_files, resolve_storage_path


async def delete_attachment(*, user_id: int, attachment_id: int) -> tuple[bool, str]:
    """删除指定用户的附件记录和本地文件。"""
    record = await UserAttachment.filter(
        id=int(attachment_id),
        user_id=int(user_id),
    ).first()
    if record is None:
        return False, "附件不存在或已被删除"

    file_path = resolve_storage_path(record.storage_path)
    await record.delete()
    if file_path is not None:
        try:
            await delete_files([file_path])
        except OSError:
            logger.exception(
                "附件记录已删，本地文件清理失败 attachment_id={} path={}",
                attachment_id,
                file_path,
            )
    return True, "附件已删除"
