"""业务域事务用例：创建用户账号并关联角色。"""

from __future__ import annotations

import uuid

from loguru import logger
from tortoise.transactions import in_transaction

from models import User, UserRole
from modules.password.services import PasswordService
from modules.permission.services import clear_user_permission_cache

from .check_password_policy import is_password_policy_valid


def _normalize_userid(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("账号不能为空")
    if len(text) > 32:
        raise ValueError("账号长度不能超过32个字符")
    return text


def _normalize_name(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("用户名不能为空")
    if len(text) > 32:
        raise ValueError("用户名长度不能超过32个字符")
    return text


def _normalize_role_ids(role_ids: list[int] | None) -> list[int]:
    """归一化角色 ID 列表。"""
    normalized_ids: list[int] = []
    for role_id in role_ids or []:
        try:
            role_id_int = int(role_id)
        except (TypeError, ValueError):
            continue
        if role_id_int > 0 and role_id_int not in normalized_ids:
            normalized_ids.append(role_id_int)
    return normalized_ids


async def _replace_user_roles(user_id: int, role_ids: list[int]) -> None:
    """覆盖保存用户角色关系。"""
    await UserRole.filter(user_id=user_id).delete()
    if role_ids:
        await UserRole.bulk_create(
            [UserRole(user_id=user_id, role_id=role_id) for role_id in role_ids]
        )


async def create_user(
    *,
    userid: str,
    password: str,
    name: str,
    role_ids: list[int],
    is_admin: bool,
) -> tuple[bool, str, User | None]:
    """在单个事务中创建用户账号并关联角色。"""
    try:
        normalized_userid = _normalize_userid(userid)
        normalized_name = _normalize_name(name)
    except ValueError as exc:
        return False, str(exc), None

    if await User.filter(userid=normalized_userid).exists():
        return False, "该账号已存在", None
    if not is_password_policy_valid(str(password or "")):
        return False, "密码必须为6到16位，包含大小写字母、数字、特殊符号", None

    normalized_role_ids = _normalize_role_ids(role_ids)
    if not is_admin and not normalized_role_ids:
        return False, "非管理员账号必须分配至少一个角色", None

    try:
        async with in_transaction():
            user = await User.create(
                userid=normalized_userid,
                password_hash=PasswordService.hash_password(str(password).strip()),
                name=normalized_name,
                is_admin=bool(is_admin),
                is_active=True,
                alternative_id=uuid.uuid4().hex,
                login_count=0,
            )
            await _replace_user_roles(int(user.id), normalized_role_ids)
    except Exception:
        logger.exception("创建用户失败 userid={}", normalized_userid)
        return False, "用户创建失败，请稍后重试", None

    clear_user_permission_cache()
    return True, "用户创建成功", user
