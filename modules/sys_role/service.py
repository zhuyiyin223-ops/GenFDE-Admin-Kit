"""角色权限服务层。"""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from models import Role, RolePermission, User, UserRole
from modules.column_filter.service import ColumnFilterSpec, ColumnFilterValue, apply_column_filter_q
from modules.excel.service import ExcelExportService, ExcelFile
from modules.keyword_search.service import STATUS_LABELS, build_keyword_q, or_q, split_keywords
from modules.permission.definitions import PermissionItem
from modules.permission.service import PermissionService

ROLE_EXPORT_HEADERS = {
    "name": "角色名称",
    "is_active": "状态",
    "permissions": "关联权限",
    "users": "关联用户",
    "create_at": "创建时间",
    "update_at": "更新时间",
}


class RoleService:
    """角色权限数据服务。"""

    @staticmethod
    def _normalize_name(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("请填写角色名称")
        if len(text) > 64:
            raise ValueError("角色名称不能超过 64 个字符")
        return text

    @staticmethod
    def _build_role_code(name: str) -> str:
        """为模板角色生成稳定可读的角色编码。"""
        base = re.sub(r"[^a-z0-9_]+", "_", str(name or "").strip().lower()).strip("_")
        if not base or not re.match(r"^[a-z]", base):
            base = f"role_{uuid.uuid4().hex[:8]}"
        code = base[:64]
        return code

    @staticmethod
    async def _ensure_unique_code(name: str) -> str:
        """生成不重复的角色编码。"""
        base_code = RoleService._build_role_code(name)
        code = base_code
        index = 1
        while await Role.filter(code=code).exists():
            suffix = f"_{index}"
            code = f"{base_code[:64 - len(suffix)]}{suffix}"
            index += 1
        return code

    @staticmethod
    def _normalize_permissions(permission_codes: list[str] | None) -> list[str]:
        """归一化权限编码，兼容已废弃的细分权限。"""
        return PermissionItem.normalize_codes(permission_codes)

    @staticmethod
    async def get_roles_with_details(
        *,
        page: int = 1,
        page_size: int = 10,
        keyword: str = "",
        column_filters: Mapping[str, ColumnFilterValue] | None = None,
        column_filter_specs: Sequence[ColumnFilterSpec] = (),
    ) -> dict[str, Any]:
        """分页查询角色，并附带权限与用户关联展示数据。"""
        page = max(1, int(page or 1))
        page_size = max(1, int(page_size or 10))
        query = Q()
        keyword_q = or_q(
            build_keyword_q(
                ("name", "code", "description", "created_at", "updated_at"),
                keyword,
                model=Role,
                labels={"is_active": STATUS_LABELS},
            ),
            await RoleService._role_ids_q_by_permission_keyword(keyword),
            await RoleService._role_ids_q_by_user_keyword(keyword),
        )
        if keyword_q:
            query &= keyword_q
        query = apply_column_filter_q(query, column_filter_specs, column_filters)

        total = await Role.filter(query).count()
        roles = await Role.filter(query).offset((page - 1) * page_size).limit(page_size).order_by("-id")
        role_ids = [int(role.id) for role in roles]
        permission_map = await RoleService._build_role_permission_map(role_ids)
        user_map = await RoleService._build_role_user_map(role_ids)

        return {
            "roles": [
                RoleService._serialize_role(
                    role,
                    permission_codes=permission_map.get(int(role.id), []),
                    user_names=user_map.get(int(role.id), []),
                )
                for role in roles
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    async def export_roles(
        *,
        keyword: str = "",
        status: bool | None = None,
        column_filters: Mapping[str, ColumnFilterValue] | None = None,
        column_filter_specs: Sequence[ColumnFilterSpec] = (),
    ) -> ExcelFile:
        """按当前筛选导出角色，不处理浏览器下载。"""
        result = await RoleService.get_roles_with_details(
            page=1,
            page_size=ExcelExportService.MAX_ROWS,
            keyword=keyword,
            column_filters=column_filters,
            column_filter_specs=column_filter_specs,
        )
        roles = list(result.get("roles") or [])
        if status is not None:
            roles = [role for role in roles if bool(role.get("is_active")) == bool(status)]
        rows = [RoleService._to_export_row(role) for role in roles]
        total = len(roles) if status is not None else int(result.get("total") or 0)
        return ExcelExportService.build_file(
            rows,
            ROLE_EXPORT_HEADERS,
            filename_stem="角色权限",
            total=total,
            sheet_name="角色权限",
        )

    @staticmethod
    async def get_role_by_id(role_id: int) -> dict[str, Any] | None:
        """获取角色详情。"""
        role = await Role.filter(id=role_id).first()
        if not role:
            return None
        permission_map = await RoleService._build_role_permission_map([int(role.id)])
        user_map = await RoleService._build_role_user_map([int(role.id)])
        return RoleService._serialize_role(
            role,
            permission_codes=permission_map.get(int(role.id), []),
            user_names=user_map.get(int(role.id), []),
        )

    @staticmethod
    async def create_role(*, name: str, permission_codes: list[str]) -> Role:
        """创建角色并保存权限。"""
        normalized_name = RoleService._normalize_name(name)
        if await Role.filter(name=normalized_name).exists():
            raise ValueError("角色名称已存在")
        normalized_permissions = RoleService._normalize_permissions(permission_codes)

        async with in_transaction():
            role = await Role.create(
                name=normalized_name,
                code=await RoleService._ensure_unique_code(normalized_name),
                description=None,
                is_active=True,
            )
            await RoleService._replace_role_permissions(int(role.id), normalized_permissions)

        PermissionService.clear_user_permission_cache()
        return role

    @staticmethod
    async def update_role(
        *,
        role_id: int,
        name: str,
        permission_codes: list[str],
        is_active: bool,
    ) -> Role:
        """更新角色和权限。"""
        normalized_name = RoleService._normalize_name(name)
        existing_role = await Role.filter(name=normalized_name).exclude(id=role_id).first()
        if existing_role:
            raise ValueError("角色名称已存在")
        role = await Role.get_or_none(id=role_id)
        if role is None:
            raise ValueError("角色不存在")

        role.name = normalized_name
        role.is_active = bool(is_active)
        normalized_permissions = RoleService._normalize_permissions(permission_codes)

        async with in_transaction():
            await role.save()
            await RoleService._replace_role_permissions(int(role.id), normalized_permissions)

        PermissionService.clear_user_permission_cache()
        return role

    @staticmethod
    async def delete_role(role_id: int) -> None:
        """删除角色。"""
        role = await Role.get_or_none(id=role_id)
        if role is None:
            raise ValueError("角色不存在")
        async with in_transaction():
            await RolePermission.filter(role_id=role_id).delete()
            await UserRole.filter(role_id=role_id).delete()
            await role.delete()
        PermissionService.clear_user_permission_cache()

    @staticmethod
    async def _role_ids_q_by_permission_keyword(keyword: str | None) -> Q | None:
        """按权限名称或编码关键词反查角色 ID。"""
        terms = split_keywords(keyword)
        if not terms:
            return None
        name_map = PermissionItem.get_name_map()
        matching_codes = [
            code
            for code, title in name_map.items()
            if any(
                term.casefold() in str(title).casefold() or term.casefold() in str(code).casefold()
                for term in terms
            )
        ]
        if not matching_codes:
            return None
        role_ids = [
            int(pk)
            for pk in await RolePermission.filter(permission_code__in=matching_codes).values_list(
                "role_id",
                flat=True,
            )
        ]
        if not role_ids:
            return None
        return Q(id__in=role_ids)

    @staticmethod
    async def _role_ids_q_by_user_keyword(keyword: str | None) -> Q | None:
        """按关联用户账号或姓名关键词反查角色 ID。"""
        user_q = build_keyword_q(("userid", "name"), keyword, model=User)
        if user_q is None:
            return None
        user_ids = [int(pk) for pk in await User.filter(user_q).values_list("id", flat=True)]
        if not user_ids:
            return None
        role_ids = [
            int(pk)
            for pk in await UserRole.filter(user_id__in=user_ids).values_list("role_id", flat=True)
        ]
        if not role_ids:
            return None
        return Q(id__in=role_ids)

    @staticmethod
    async def _build_role_permission_map(role_ids: list[int]) -> dict[int, list[str]]:
        """构建角色权限编码映射。"""
        if not role_ids:
            return {}
        rows = await RolePermission.filter(role_id__in=role_ids).values("role_id", "permission_code")
        grouped: dict[int, list[str]] = {role_id: [] for role_id in role_ids}
        for row in rows:
            grouped.setdefault(int(row["role_id"]), []).append(str(row["permission_code"]))
        return {role_id: PermissionItem.normalize_codes(codes) for role_id, codes in grouped.items()}

    @staticmethod
    async def _build_role_user_map(role_ids: list[int]) -> dict[int, list[str]]:
        """构建角色关联用户姓名映射。"""
        if not role_ids:
            return {}
        relation_rows = await UserRole.filter(role_id__in=role_ids).values("role_id", "user_id")
        user_ids = sorted({int(row["user_id"]) for row in relation_rows})
        users = await User.filter(id__in=user_ids).values("id", "name", "userid") if user_ids else []
        user_name_map = {
            int(user["id"]): str(user.get("name") or user.get("userid") or user["id"])
            for user in users
        }
        result: dict[int, list[str]] = {role_id: [] for role_id in role_ids}
        for row in relation_rows:
            role_id = int(row["role_id"])
            user_id = int(row["user_id"])
            result.setdefault(role_id, []).append(user_name_map.get(user_id, str(user_id)))
        return result

    @staticmethod
    def _serialize_role(role: Role, *, permission_codes: list[str], user_names: list[str]) -> dict[str, Any]:
        """序列化角色行。"""
        permission_name_map = PermissionItem.get_name_map()
        permission_names = [permission_name_map.get(code, code) for code in permission_codes]
        return {
            "id": int(role.id),
            "name": role.name,
            "code": role.code,
            "description": role.description or "",
            "permission_codes": permission_codes,
            "permission_list": permission_names,
            "permissions": "、".join(permission_names) if permission_names else "-",
            "user_list": user_names,
            "users": "、".join(user_names) if user_names else "-",
            "is_active": bool(role.is_active),
            "create_at": role.created_at.strftime("%Y-%m-%d %H:%M") if role.created_at else "",
            "update_at": role.updated_at.strftime("%Y-%m-%d %H:%M") if role.updated_at else "",
        }

    @staticmethod
    def _to_export_row(role: dict[str, Any]) -> dict[str, Any]:
        """将序列化角色行转为导出字段。"""
        return {
            "name": role.get("name") or "",
            "is_active": "正常" if role.get("is_active") else "禁用",
            "permissions": role.get("permissions") or "-",
            "users": role.get("users") or "-",
            "create_at": role.get("create_at") or "",
            "update_at": role.get("update_at") or "",
        }

    @staticmethod
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
