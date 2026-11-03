"""业务域事务用例：保存用户附件。"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path

from models import UserAttachment
from modules.ui.attachment_types import AttachmentItem
from settings import PROJECT_ROOT

from .attachment_storage import (
    USER_ATTACHMENT_MAX_FILES,
    USER_ATTACHMENT_ROOT,
    build_account_dir_name,
    build_storage_name,
    delete_files,
    validate_attachment,
)


async def save_attachments(
    *,
    user_id: int,
    userid: str,
    attachments: Sequence[AttachmentItem],
) -> list[Path]:
    """将待提交附件保存到用户目录并批量创建记录。"""
    pending_attachments = list(attachments)
    if not pending_attachments:
        return []
    if len(pending_attachments) > USER_ATTACHMENT_MAX_FILES:
        raise ValueError(f"用户附件最多上传 {USER_ATTACHMENT_MAX_FILES} 个")

    target_dir = USER_ATTACHMENT_ROOT / build_account_dir_name(user_id=user_id, userid=userid)
    await asyncio.to_thread(target_dir.mkdir, parents=True, exist_ok=True)

    written_paths: list[Path] = []
    records: list[UserAttachment] = []
    try:
        for attachment in pending_attachments:
            original_name, content = validate_attachment(attachment)
            storage_name = build_storage_name(original_name)
            file_path = target_dir / storage_name
            await asyncio.to_thread(file_path.write_bytes, content)
            written_paths.append(file_path)
            records.append(
                UserAttachment(
                    original_name=original_name,
                    storage_name=storage_name,
                    content_type=str(attachment.content_type or "application/octet-stream")[:128],
                    file_size=len(content),
                    storage_path=file_path.relative_to(PROJECT_ROOT).as_posix(),
                    user_id=int(user_id),
                )
            )
        await UserAttachment.bulk_create(records)
    except Exception:
        await delete_files(written_paths)
        raise
    return written_paths
