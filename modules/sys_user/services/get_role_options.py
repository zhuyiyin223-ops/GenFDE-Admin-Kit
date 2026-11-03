"""业务域事务用例：读取可选角色。"""

from __future__ import annotations

from tortoise.expressions import Q

from models import Role


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


async def get_role_options(*, include_role_ids: list[int] | None = None) -> dict[int, str]:
    """读取可选角色，编辑时允许带出已停用但已关联的角色。"""
    include_ids = _normalize_role_ids(include_role_ids)
    query = Q(is_active=True)
    if include_ids:
        query |= Q(id__in=include_ids)
    roles = await Role.filter(query).order_by("id")
    return {int(role.id): role.name for role in roles}
