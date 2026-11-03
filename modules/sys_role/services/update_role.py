"""业务域事务用例：更新角色并替换权限。"""

from __future__ import annotations

from tortoise.transactions import in_transaction

from models import Role, RolePermission
from modules.permission.definitions import PermissionItem
from modules.permission.services import clear_user_permission_cache


def _normalize_name(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("请填写角色名称")
    if len(text) > 64:
        raise ValueError("角色名称不能超过 64 个字符")
    return text


async def _replace_role_permissions(role_id: int, permission_codes: list[str]) -> None:
    """覆盖保存角色权限。"""
    await RolePermission.filter(role_id=role_id).delete()
    if permission_codes:
        await RolePermission.bulk_create(
            [
                RolePermission(role_id=role_id, permission_code=permission_code)
                for permission_code in permission_codes
            ]
        )


async def update_role(
    *,
    role_id: int,
    name: str,
    permission_codes: list[str],
    is_active: bool,
) -> Role:
    """在单个事务中更新角色并替换权限。"""
    normalized_name = _normalize_name(name)
    existing_role = await Role.filter(name=normalized_name).exclude(id=role_id).first()
    if existing_role:
        raise ValueError("角色名称已存在")
    role = await Role.get_or_none(id=role_id)
    if role is None:
        raise ValueError("角色不存在")

    role.name = normalized_name
    role.is_active = bool(is_active)
    normalized_permissions = PermissionItem.normalize_codes(permission_codes)

    async with in_transaction():
        await role.save()
        await _replace_role_permissions(int(role.id), normalized_permissions)

    clear_user_permission_cache()
    return role
