"""业务域事务用例：分页查询 API 客户端。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from tortoise.expressions import Q

from models import ApiClient
from modules.column_filter.services import ColumnFilterSpec, ColumnFilterValue, apply_column_filter_q
from modules.keyword_search.services import STATUS_LABELS, build_keyword_q


async def search_clients(
    page: int = 1,
    page_size: int = 10,
    keyword: str | None = None,
    status: bool | None = None,
    column_filters: Mapping[str, ColumnFilterValue] | None = None,
    column_filter_specs: Sequence[ColumnFilterSpec] = (),
) -> dict[str, Any]:
    """按关键词、状态和列筛选分页查询客户端。"""
    query = Q()
    keyword_q = build_keyword_q(
        (
            "client_id",
            "name",
            "last_ip",
            "ip_whitelist",
            "last_login_at",
            "created_at",
            "updated_at",
        ),
        keyword,
        model=ApiClient,
        labels={"is_active": STATUS_LABELS},
    )
    if keyword_q:
        query &= keyword_q

    if status is not None:
        query &= Q(is_active=bool(status))
    query = apply_column_filter_q(query, column_filter_specs, column_filters)

    total = await ApiClient.filter(query).count()
    clients = await ApiClient.filter(query).offset((page - 1) * page_size).limit(page_size).order_by("-id")

    data = []
    for client in clients:
        data.append(
            {
                "id": client.id,
                "client_id": client.client_id,
                "name": client.name,
                "is_active": client.is_active,
                "last_login_at": client.last_login_at.strftime("%Y-%m-%d %H:%M") if client.last_login_at else None,
                "last_ip": client.last_ip or "",
                "ip_whitelist": client.ip_whitelist or "",
                "created_at": client.created_at.strftime("%Y-%m-%d %H:%M"),
                "updated_at": client.updated_at.strftime("%Y-%m-%d %H:%M") if client.updated_at else None,
            }
        )

    return {
        "total": total,
        "clients": data,
    }
