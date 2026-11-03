"""业务域事务用例：读取用户详情。"""

from __future__ import annotations

from typing import Any

from models import User

from .user_rows import build_user_role_map, count_attachments_by_user_ids, serialize_user


async def get_user_detail(user_id: int) -> dict[str, Any] | None:
    """获取用户详情，不做页面层处理。"""
    user = await User.filter(id=user_id).first()
    if not user:
        return None
    user_role_map = await build_user_role_map([int(user.id)])
    attachment_count_map = await count_attachments_by_user_ids([int(user.id)])
    return serialize_user(
        user,
        user_role_map.get(int(user.id), {"role_ids": [], "role_names": []}),
        attachment_count=attachment_count_map.get(int(user.id), 0),
    )
