"""业务域：用户列表行组装。非事务，供查询与导出复用，避免 N+1。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from tortoise.expressions import Q

from models import Role, User, UserAttachment, UserRole
from modules.column_filter.services import ColumnFilterSpec, ColumnFilterValue, apply_column_filter_q
from modules.keyword_search.services import STATUS_LABELS, YES_NO_LABELS, build_keyword_q, or_q


async def user_ids_q_by_role_keyword(keyword: str | None) -> Q | None:
    """按角色名称关键词反查用户 ID。"""
    role_q = build_keyword_q(("name",), keyword, model=Role)
    if role_q is None:
        return None
    role_ids = [int(pk) for pk in await Role.filter(role_q).values_list("id", flat=True)]
    if not role_ids:
        return None
    user_ids = [
        int(pk)
        for pk in await UserRole.filter(role_id__in=role_ids).values_list("user_id", flat=True)
    ]
    if not user_ids:
        return None
    return Q(id__in=user_ids)


async def build_user_role_map(user_ids: list[int]) -> dict[int, dict[str, list[Any]]]:
    """构建用户角色映射。"""
    if not user_ids:
        return {}
    relation_rows = await UserRole.filter(user_id__in=user_ids).values("user_id", "role_id")
    role_ids = sorted({int(row["role_id"]) for row in relation_rows})
    roles = await Role.filter(id__in=role_ids).values("id", "name") if role_ids else []
    role_name_map = {int(role["id"]): str(role["name"]) for role in roles}
    result: dict[int, dict[str, list[Any]]] = {
        user_id: {"role_ids": [], "role_names": []}
        for user_id in user_ids
    }
    for row in relation_rows:
        user_id = int(row["user_id"])
        role_id = int(row["role_id"])
        result.setdefault(user_id, {"role_ids": [], "role_names": []})
        result[user_id]["role_ids"].append(role_id)
        result[user_id]["role_names"].append(role_name_map.get(role_id, str(role_id)))
    return result


async def count_attachments_by_user_ids(user_ids: list[int]) -> dict[int, int]:
    """批量统计用户附件数量。"""
    if not user_ids:
        return {}
    rows = await UserAttachment.filter(user_id__in=user_ids).values("user_id")
    counts = {int(user_id): 0 for user_id in user_ids}
    for row in rows:
        user_id = int(row["user_id"])
        counts[user_id] = counts.get(user_id, 0) + 1
    return counts


def serialize_user(
    user: User,
    role_data: dict[str, list[Any]],
    *,
    attachment_count: int = 0,
) -> dict[str, Any]:
    """序列化用户行。"""
    return {
        "id": int(user.id),
        "userid": user.userid,
        "name": user.name,
        "is_admin": bool(user.is_admin),
        "is_active": bool(user.is_active),
        "role_ids": role_data.get("role_ids", []),
        "role_names": role_data.get("role_names", []),
        "attachment_count": int(attachment_count or 0),
        "login_count": int(user.login_count or 0),
        "last_active_at": user.last_active_at.strftime("%Y-%m-%d %H:%M") if user.last_active_at else "",
        "ip_addr": user.ip_addr or "",
        "create_at": user.created_at.strftime("%Y-%m-%d %H:%M") if user.created_at else "",
        "disabled_at": user.disabled_at.strftime("%Y-%m-%d %H:%M") if user.disabled_at else "",
    }


def to_export_row(user: dict[str, Any]) -> dict[str, Any]:
    """将序列化用户行转为导出字段。"""
    return {
        "userid": user.get("userid") or "",
        "name": user.get("name") or "",
        "is_admin": "是" if user.get("is_admin") else "否",
        "roles": "、".join(user.get("role_names") or []) or "-",
        "is_active": "正常" if user.get("is_active") else "禁用",
        "login_count": user.get("login_count") or 0,
        "last_active_at": user.get("last_active_at") or "",
        "ip_addr": user.get("ip_addr") or "",
        "create_at": user.get("create_at") or "",
        "disabled_at": user.get("disabled_at") or "",
    }


async def collect_users(
    *,
    page: int = 1,
    page_size: int = 10,
    keyword: str | None = None,
    status: bool | None = None,
    column_filters: Mapping[str, ColumnFilterValue] | None = None,
    column_filter_specs: Sequence[ColumnFilterSpec] = (),
) -> dict[str, Any]:
    """分页查询用户并附带角色与附件数量。"""
    page = max(1, int(page or 1))
    page_size = max(1, int(page_size or 10))

    query = Q()
    keyword_q = or_q(
        build_keyword_q(
            (
                "userid",
                "name",
                "ip_addr",
                "login_count",
                "last_active_at",
                "created_at",
                "disabled_at",
            ),
            keyword,
            model=User,
            labels={"is_active": STATUS_LABELS, "is_admin": YES_NO_LABELS},
        ),
        await user_ids_q_by_role_keyword(keyword),
    )
    if keyword_q:
        query &= keyword_q
    if status is not None:
        query &= Q(is_active=bool(status))
    query = apply_column_filter_q(query, column_filter_specs, column_filters)

    total = await User.filter(query).count()
    users = await User.filter(query).offset((page - 1) * page_size).limit(page_size).order_by("-id")
    user_ids = [int(user.id) for user in users]
    user_role_map = await build_user_role_map(user_ids)
    attachment_count_map = await count_attachments_by_user_ids(user_ids)
    return {
        "users": [
            serialize_user(
                user,
                user_role_map.get(int(user.id), {"role_ids": [], "role_names": []}),
                attachment_count=attachment_count_map.get(int(user.id), 0),
            )
            for user in users
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
