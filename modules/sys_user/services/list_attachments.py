"""业务域事务用例：查询用户附件。"""

from __future__ import annotations

from models import UserAttachment
from modules.ui.attachment_types import AttachmentItem

from .attachment_storage import serialize_attachment


async def list_attachments(user_id: int) -> list[AttachmentItem]:
    """查询指定用户的附件，并转换为通用展示数据。"""
    records = await UserAttachment.filter(user_id=int(user_id)).order_by("id")
    return [serialize_attachment(record) for record in records]
