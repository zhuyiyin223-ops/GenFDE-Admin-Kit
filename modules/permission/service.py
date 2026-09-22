"""权限服务层。"""

from __future__ import annotations

from dataclasses import dataclass

from nicegui import app

from models import Role, RolePermission, User, UserRole
from modules.permission.definitions import PermissionItem


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


class PermissionService:
    """权限事务服务。"""

    CACHE_KEY = "permission_context"

    @staticmethod
    def clear_user_permission_cache(user_id: int | None = None) -> None:
        """清理当前浏览器会话中的权限缓存。"""
        cached = UserPermissionContext.from_cache_dict(app.storage.user.get(PermissionService.CACHE_KEY))
        if user_id is None or cached is None or cached.user_id == int(user_id):
            app.storage.user.pop(PermissionService.CACHE_KEY, None)

    @staticmethod
    async def get_user_permission_context(user_id: int) -> UserPermissionContext:
        """读取用户权限上下文。"""
        cached = UserPermissionContext.from_cache_dict(app.storage.user.get(PermissionService.CACHE_KEY))
        if cached is not None and cached.user_id == int(user_id):
            return cached

        user = await User.get_or_none(id=user_id)
        if user is None:
            context = UserPermissionContext(user_id=int(user_id), is_admin=False, role_ids=(), permission_codes=())
            app.storage.user[PermissionService.CACHE_KEY] = context.to_cache_dict()
            return context

        if user.is_admin:
            context = UserPermissionContext(
                user_id=int(user.id),
                is_admin=True,
                role_ids=(),
                permission_codes=tuple(PermissionItem.all_codes()),
            )
            app.storage.user[PermissionService.CACHE_KEY] = context.to_cache_dict()
            return context

        active_role_ids = list(await Role.filter(is_active=True).values_list("id", flat=True))
        role_ids = list(
            await UserRole.filter(user_id=int(user.id), role_id__in=active_role_ids).values_list("role_id", flat=True)
        ) if active_role_ids else []
        permission_codes = list(
            await RolePermission.filter(role_id__in=role_ids).values_list("permission_code", flat=True)
        ) if role_ids else []
        context = UserPermissionContext(
            user_id=int(user.id),
            is_admin=False,
            role_ids=tuple(int(role_id) for role_id in role_ids),
            permission_codes=tuple(PermissionItem.normalize_codes(permission_codes)),
        )
        app.storage.user[PermissionService.CACHE_KEY] = context.to_cache_dict()
        return context

    @staticmethod
    async def get_cached_user_permissions(user_id: int | None) -> list[str]:
        """返回用户权限编码列表。"""
        if user_id is None:
            return []
        context = await PermissionService.get_user_permission_context(int(user_id))
        return list(context.permission_codes)

    @staticmethod
    async def has_permission(user_id: int | None, permission_code: str) -> bool:
        """判断用户是否拥有指定权限。"""
        if user_id is None:
            return False
        context = await PermissionService.get_user_permission_context(int(user_id))
        return context.has_permission(permission_code)

    @staticmethod
    def _get_accessible_menu_links(permission_codes: list[str]) -> list[str]:
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

    @staticmethod
    async def get_first_accessible_path(user_id: int, preferred_path: str | None = None) -> str:
        """返回登录后首个可访问页面。"""
        permissions = await PermissionService.get_cached_user_permissions(user_id)
        links = PermissionService._get_accessible_menu_links(permissions)
        normalized_preferred_path = str(preferred_path or "").strip()
        if normalized_preferred_path in links:
            return normalized_preferred_path
        return links[0] if links else "/"
