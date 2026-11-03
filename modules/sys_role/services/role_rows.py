"""业务域：角色列表行组装。非事务，供查询与导出复用，避免 N+1。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from tortoise.expressions import Q

from models import Role, RolePermission, User, UserRole
from modules.column_filter.services import ColumnFilterSpec, ColumnFilterValue, apply_column_filter_q
from modules.keyword_search.services import STATUS_LABELS, build_keyword_q, or_q, split_keywords
from modules.permission.definitions import PermissionItem


async def role_ids_q_by_permission_keyword(keyword: str | None) -> Q | None:
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


async def role_ids_q_by_user_keyword(keyword: str | None) -> Q | None:
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


async def build_role_permission_map(role_ids: list[int]) -> dict[int, list[str]]:
    """构建角色权限编码映射。"""
    if not role_ids:
        return {}
    rows = await RolePermission.filter(role_id__in=role_ids).values("role_id", "permission_code")
    grouped: dict[int, list[str]] = {role_id: [] for role_id in role_ids}
    for row in rows:
        grouped.setdefault(int(row["role_id"]), []).append(str(row["permission_code"]))
    return {role_id: PermissionItem.normalize_codes(codes) for role_id, codes in grouped.items()}


async def build_role_user_map(role_ids: list[int]) -> dict[int, list[str]]:
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


def serialize_role(role: Role, *, permission_codes: list[str], user_names: list[str]) -> dict[str, Any]:
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


def to_export_row(role: dict[str, Any]) -> dict[str, Any]:
    """将序列化角色行转为导出字段。"""
    return {
        "name": role.get("name") or "",
        "is_active": "正常" if role.get("is_active") else "禁用",
        "permissions": role.get("permissions") or "-",
        "users": role.get("users") or "-",
        "create_at": role.get("create_at") or "",
        "update_at": role.get("update_at") or "",
    }


async def collect_roles(
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
        await role_ids_q_by_permission_keyword(keyword),
        await role_ids_q_by_user_keyword(keyword),
    )
    if keyword_q:
        query &= keyword_q
    query = apply_column_filter_q(query, column_filter_specs, column_filters)

    total = await Role.filter(query).count()
    roles = await Role.filter(query).offset((page - 1) * page_size).limit(page_size).order_by("-id")
    role_ids = [int(role.id) for role in roles]
    permission_map = await build_role_permission_map(role_ids)
    user_map = await build_role_user_map(role_ids)
    return {
        "roles": [
            serialize_role(
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
