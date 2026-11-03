"""业务域：用户附件本地存储。非事务，供读写用例复用路径边界校验。"""

from __future__ import annotations

import asyncio
import re
import uuid
from collections.abc import Sequence
from pathlib import Path

from models import UserAttachment
from modules.ui.attachment_types import (
    DEFAULT_ATTACHMENT_EXTENSIONS,
    AttachmentItem,
    is_allowed_attachment_name,
    validate_attachment_preview_content,
)
from settings import PROJECT_ROOT

USER_ATTACHMENT_ROOT = PROJECT_ROOT / "data" / "upload" / "user"
USER_ATTACHMENT_MAX_FILES = 6
USER_ATTACHMENT_MAX_SIZE = 10 * 1024 * 1024


def build_account_dir_name(*, user_id: int, userid: str) -> str:
    """生成稳定且不可越界的账号目录名。"""
    safe_userid = re.sub(r"[^\w.-]+", "_", str(userid or ""), flags=re.UNICODE).strip("._")
    account_name = safe_userid[:48] or "user"
    return f"{account_name}_{int(user_id)}"


def build_storage_name(original_name: str) -> str:
    """生成纯 UUID 本地文件名，原始名称仅保存在数据库中。"""
    suffix = Path(original_name).suffix.lower()[:16]
    return f"{uuid.uuid4().hex}{suffix}"


def validate_attachment(attachment: AttachmentItem) -> tuple[str, bytes]:
    """校验附件内容并返回安全的原文件名。"""
    original_name = Path(str(attachment.file_name or "").replace("\\", "/")).name.strip()
    if not original_name:
        raise ValueError("附件文件名不能为空")
    if len(original_name) > 255:
        raise ValueError(f"附件文件名过长：{original_name[:30]}...")
    if not is_allowed_attachment_name(original_name, DEFAULT_ATTACHMENT_EXTENSIONS):
        raise ValueError(f"{original_name} 的文件格式不支持")

    content = attachment.content
    if not content:
        raise ValueError(f"{original_name} 没有可保存的文件内容")
    if len(content) > USER_ATTACHMENT_MAX_SIZE:
        raise ValueError(f"{original_name} 超过 10.00 MB，无法保存")
    validate_attachment_preview_content(original_name, content)
    return original_name, content


def serialize_attachment(record: UserAttachment) -> AttachmentItem:
    """将用户附件记录转换为通用展示对象。"""
    attachment_id = int(record.id)
    content_url = f"/sys/user/attachments/{attachment_id}/content"
    return AttachmentItem(
        attachment_id=attachment_id,
        file_name=str(record.original_name or "未命名附件"),
        content_type=str(record.content_type or "application/octet-stream"),
        size=int(record.file_size or 0),
        thumbnail_url=content_url,
        preview_url=content_url,
        download_url=f"{content_url}?download=true",
    )


def resolve_storage_path(storage_path: str | None) -> Path | None:
    """解析数据库相对路径，并限制文件只能位于用户上传目录。"""
    if not storage_path:
        return None
    upload_root = USER_ATTACHMENT_ROOT.resolve()
    file_path = (PROJECT_ROOT / storage_path).resolve()
    if not file_path.is_relative_to(upload_root):
        return None
    return file_path


def delete_files_sync(file_paths: list[Path]) -> None:
    """同步删除文件，并清理已经为空的账号目录。"""
    parent_dirs: set[Path] = set()
    for file_path in file_paths:
        parent_dirs.add(file_path.parent)
        file_path.unlink(missing_ok=True)
    for parent_dir in parent_dirs:
        try:
            parent_dir.rmdir()
        except OSError:
            continue


async def delete_files(file_paths: Sequence[Path]) -> None:
    """删除指定本地文件，并清理已经为空的账号目录。"""
    if not file_paths:
        return
    await asyncio.to_thread(delete_files_sync, list(file_paths))
