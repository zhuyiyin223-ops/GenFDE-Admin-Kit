"""业务域事务用例：读取角色详情。"""

from __future__ import annotations

from typing import Any

from models import Role

from .role_rows import build_role_permission_map, build_role_user_map, serialize_role


async def get_role_by_id(role_id: int) -> dict[str, Any] | None:
    """获取角色详情。"""
    role = await Role.filter(id=role_id).first()
    if not role:
        return None
    permission_map = await build_role_permission_map([int(role.id)])
    user_map = await build_role_user_map([int(role.id)])
    return serialize_role(
        role,
        permission_codes=permission_map.get(int(role.id), []),
        user_names=user_map.get(int(role.id), []),
    )
