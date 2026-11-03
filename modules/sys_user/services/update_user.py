"""业务域事务用例：更新用户账号并替换角色关系。"""

from __future__ import annotations

import uuid
from datetime import datetime

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


async def update_user(
    *,
    user_id: int,
    userid: str,
    name: str,
    is_admin: bool,
    role_ids: list[int],
    is_active: bool,
    reset_password: bool,
    new_password: str | None = None,
) -> tuple[bool, str]:
    """在单个事务中更新用户账号并替换角色关系。"""
    try:
        normalized_userid = _normalize_userid(userid)
        normalized_name = _normalize_name(name)
    except ValueError as exc:
        return False, str(exc)

    normalized_role_ids = _normalize_role_ids(role_ids)
    if not is_admin and not normalized_role_ids:
        return False, "非管理员账号必须分配至少一个角色"
    if reset_password and not is_password_policy_valid(str(new_password or "")):
        return False, "新密码必须为6到16位，包含大小写字母、数字、特殊符号"

    existing_user = await User.filter(userid=normalized_userid).exclude(id=user_id).first()
    if existing_user:
        return False, "该账号已被其他用户使用"

    try:
        async with in_transaction():
            user = await User.filter(id=user_id).first()
            if not user:
                return False, "用户不存在"

            previous_is_active = bool(user.is_active)
            user.userid = normalized_userid
            user.name = normalized_name
            user.is_admin = bool(is_admin)
            user.is_active = bool(is_active)
            if previous_is_active and not user.is_active:
                user.alternative_id = uuid.uuid4().hex
                user.disabled_at = datetime.now()
            elif not previous_is_active and user.is_active:
                user.disabled_at = None
            if reset_password:
                user.password_hash = PasswordService.hash_password(str(new_password or "").strip())
                user.alternative_id = uuid.uuid4().hex
            await user.save()
            await _replace_user_roles(int(user.id), normalized_role_ids)
    except Exception:
        logger.exception("更新用户失败 user_id={}", user_id)
        return False, "用户更新失败，请稍后重试"

    clear_user_permission_cache(int(user_id))
    status_text = (
        "禁用"
        if previous_is_active and not is_active
        else "启用"
        if not previous_is_active and is_active
        else ""
    )
    if status_text:
        return True, f"用户更新成功，账号已{status_text}"
    return True, "用户更新成功"
