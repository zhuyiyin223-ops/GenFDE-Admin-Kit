"""业务域事务用例：创建角色并保存权限。"""

from __future__ import annotations

import re
import uuid

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


def _build_role_code(name: str) -> str:
    """为模板角色生成稳定可读的角色编码。"""
    base = re.sub(r"[^a-z0-9_]+", "_", str(name or "").strip().lower()).strip("_")
    if not base or not re.match(r"^[a-z]", base):
        base = f"role_{uuid.uuid4().hex[:8]}"
    return base[:64]


async def _ensure_unique_code(name: str) -> str:
    """生成不重复的角色编码。"""
    base_code = _build_role_code(name)
    code = base_code
    index = 1
    while await Role.filter(code=code).exists():
        suffix = f"_{index}"
        code = f"{base_code[: 64 - len(suffix)]}{suffix}"
        index += 1
    return code


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


async def create_role(*, name: str, permission_codes: list[str]) -> Role:
    """在单个事务中创建角色并保存权限。"""
    normalized_name = _normalize_name(name)
    if await Role.filter(name=normalized_name).exists():
        raise ValueError("角色名称已存在")
    normalized_permissions = PermissionItem.normalize_codes(permission_codes)

    async with in_transaction():
        role = await Role.create(
            name=normalized_name,
            code=await _ensure_unique_code(normalized_name),
            description=None,
            is_active=True,
        )
        await _replace_role_permissions(int(role.id), normalized_permissions)

    clear_user_permission_cache()
    return role
