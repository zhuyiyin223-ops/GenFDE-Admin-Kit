"""业务域：客户端账号反查。非事务，令牌与请求日志查询共用，避免 N+1。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from models import ApiClient
from modules.keyword_search.services import build_keyword_q


async def ids_by_keyword(keyword: str | None) -> list[int]:
    """按账号或名称关键词反查客户端主键。"""
    client_q = build_keyword_q(("client_id", "name"), keyword, model=ApiClient)
    if client_q is None:
        return []
    return [int(pk) for pk in await ApiClient.filter(client_q).values_list("id", flat=True)]


async def map_by_ids(client_ids: Sequence[int | None]) -> dict[int, dict[str, Any]]:
    """按主键批量读取客户端账号与名称。"""
    unique_ids = list({int(client_id) for client_id in client_ids if client_id})
    if not unique_ids:
        return {}
    rows = await ApiClient.filter(id__in=unique_ids).values("id", "client_id", "name")
    return {int(row["id"]): row for row in rows if row.get("id") is not None}
