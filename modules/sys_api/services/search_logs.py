"""业务域事务用例：分页查询 API 请求日志。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from tortoise.expressions import Q

from models import ApiRequestLog
from modules.column_filter.services import ColumnFilterSpec, ColumnFilterValue, apply_column_filter_q
from modules.keyword_search.services import build_keyword_q, or_q

from .client_lookup import ids_by_keyword, map_by_ids


def _format_time(value) -> str | None:
    if not value:
        return None
    return value.strftime("%Y-%m-%d %H:%M")


async def search_logs(
    page: int = 1,
    page_size: int = 10,
    keyword: str | None = None,
    status_code: int | None = None,
    column_filters: Mapping[str, ColumnFilterValue] | None = None,
    column_filter_specs: Sequence[ColumnFilterSpec] = (),
) -> dict[str, Any]:
    """按关键词、状态码和列筛选分页查询请求日志。"""
    query = Q()
    client_ids = await ids_by_keyword(keyword)
    keyword_q = or_q(
        build_keyword_q(
            (
                "client_id_text",
                "path",
                "ip_addr",
                "method",
                "status_code",
                "process_ms",
                "created_at",
            ),
            keyword,
            model=ApiRequestLog,
        ),
        Q(client_id__in=client_ids) if client_ids else None,
    )
    if keyword_q:
        query &= keyword_q

    if status_code is not None:
        query &= Q(status_code=int(status_code))
    query = apply_column_filter_q(query, column_filter_specs, column_filters)

    total = await ApiRequestLog.filter(query).count()
    logs = await ApiRequestLog.filter(query).offset((page - 1) * page_size).limit(page_size).order_by("-id")
    client_map = await map_by_ids([log.client_id for log in logs])

    data = []
    for log in logs:
        client_row = client_map.get(int(log.client_id)) if log.client_id else None
        data.append(
            {
                "id": log.id,
                "client_id": (client_row.get("client_id") if client_row else None) or log.client_id_text or "",
                "client_name": (client_row.get("name") if client_row else None) or "",
                "method": log.method,
                "path": log.path,
                "status_code": log.status_code,
                "ip_addr": log.ip_addr or "",
                "process_ms": log.process_ms,
                "created_at": _format_time(log.created_at) or "-",
            }
        )

    return {
        "total": total,
        "logs": data,
    }
