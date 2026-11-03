"""业务域事务用例：删除角色及关联关系。"""

from __future__ import annotations

from tortoise.transactions import in_transaction

from models import Role, RolePermission, UserRole
from modules.permission.services import clear_user_permission_cache


async def delete_role(role_id: int) -> None:
    """在单个事务中删除角色及其关联关系。"""
    role = await Role.get_or_none(id=role_id)
    if role is None:
        raise ValueError("角色不存在")
    async with in_transaction():
        await RolePermission.filter(role_id=role_id).delete()
        await UserRole.filter(role_id=role_id).delete()
        await role.delete()
    clear_user_permission_cache()
