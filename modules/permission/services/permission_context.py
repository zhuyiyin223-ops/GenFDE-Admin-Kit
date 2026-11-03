"""系统能力：用户权限上下文的加载与菜单路径。非事务，鉴权用例共用。"""

from __future__ import annotations

from dataclasses import dataclass

from nicegui import app

from models import Role, RolePermission, User, UserRole
from modules.permission.definitions import PermissionItem

CACHE_KEY = "permission_context"


@dataclass(frozen=True)
class UserPermissionContext:
    """用户权限上下文。"""

    user_id: int
    is_admin: bool
    role_ids: tuple[int, ...]
    permission_codes: tuple[str, ...]

    def has_permission(self, permission_code: str) -> bool:
        """判断是否拥有指定权限。"""
        return self.is_admin or permission_code in self.permission_codes

    def to_cache_dict(self) -> dict[str, object]:
        """转换为用户存储中的缓存结构。"""
        return {
            "user_id": self.user_id,
            "is_admin": self.is_admin,
            "role_ids": list(self.role_ids),
            "permission_codes": list(self.permission_codes),
        }

    @classmethod
    def from_cache_dict(cls, raw_data: object) -> UserPermissionContext | None:
        """从用户存储缓存恢复权限上下文。"""
        if not isinstance(raw_data, dict):
            return None
        user_id = raw_data.get("user_id")
        if not isinstance(user_id, int):
            return None
        role_ids_raw = raw_data.get("role_ids", [])
        permissions_raw = raw_data.get("permission_codes", [])
        role_ids = tuple(item for item in role_ids_raw if isinstance(item, int)) if isinstance(role_ids_raw, list) else ()
        permission_codes = (
            tuple(item for item in permissions_raw if isinstance(item, str))
            if isinstance(permissions_raw, list)
            else ()
        )
        return cls(
            user_id=user_id,
            is_admin=bool(raw_data.get("is_admin", False)),
            role_ids=role_ids,
            permission_codes=permission_codes,
        )


def accessible_menu_links(permission_codes: list[str]) -> list[str]:
    """按菜单顺序返回可访问路径。"""
    result: list[str] = []
    permission_set = set(permission_codes)
    for category in PermissionItem.get_menu_structure():
        items = category.get("items", [])
        if not isinstance(items, list):
            continue
        for item in items:
            permission = str(item.get("permission") or "").strip()
            link = str(item.get("link") or "").strip()
            if link and (not permission or permission in permission_set):
                result.append(link)
    return result


async def load_user_permission_context(user_id: int) -> UserPermissionContext:
    """读取用户权限上下文，命中会话缓存时不再查库。"""
    cached = UserPermissionContext.from_cache_dict(app.storage.user.get(CACHE_KEY))
    if cached is not None and cached.user_id == int(user_id):
        return cached

    user = await User.get_or_none(id=user_id)
    if user is None:
        context = UserPermissionContext(user_id=int(user_id), is_admin=False, role_ids=(), permission_codes=())
        app.storage.user[CACHE_KEY] = context.to_cache_dict()
        return context

    if user.is_admin:
        context = UserPermissionContext(
            user_id=int(user.id),
            is_admin=True,
            role_ids=(),
            permission_codes=tuple(PermissionItem.all_codes()),
        )
        app.storage.user[CACHE_KEY] = context.to_cache_dict()
        return context

    active_role_ids = list(await Role.filter(is_active=True).values_list("id", flat=True))
    role_ids = (
        list(await UserRole.filter(user_id=int(user.id), role_id__in=active_role_ids).values_list("role_id", flat=True))
        if active_role_ids
        else []
    )
    permission_codes = (
        list(await RolePermission.filter(role_id__in=role_ids).values_list("permission_code", flat=True))
        if role_ids
        else []
    )
    context = UserPermissionContext(
        user_id=int(user.id),
        is_admin=False,
        role_ids=tuple(int(role_id) for role_id in role_ids),
        permission_codes=tuple(PermissionItem.normalize_codes(permission_codes)),
    )
    app.storage.user[CACHE_KEY] = context.to_cache_dict()
    return context
