"""业务域事务用例：分页查询 API 令牌。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from tortoise.expressions import Q

from models import ApiToken
from modules.column_filter.services import ColumnFilterSpec, ColumnFilterValue, apply_column_filter_q
from modules.keyword_search.services import build_keyword_q, or_q, split_keywords

from .client_lookup import ids_by_keyword, map_by_ids


def _format_time(value) -> str | None:
    if not value:
        return None
    return value.strftime("%Y-%m-%d %H:%M")


def _format_token_type(token_type: str | None) -> str:
    if token_type == "access":
        return "访问令牌"
    if token_type == "refresh":
        return "刷新令牌"
    return token_type or "-"


def _compute_status(token: ApiToken, now: datetime) -> str:
    if token.revoked_at:
        return "已撤销"
    if token.expires_at and token.expires_at <= now:
        return "已过期"
    return "有效"


def _status_keyword_q(keyword: str | None, now: datetime) -> Q | None:
    """按令牌状态展示文案匹配计算字段。"""
    combined: Q | None = None
    for term in split_keywords(keyword):
        folded = term.casefold()
        part: Q | None = None
        if folded in "有效":
            part = or_q(
                part,
                Q(revoked_at__isnull=True) & (Q(expires_at__isnull=True) | Q(expires_at__gt=now)),
            )
        if folded in "已撤销":
            part = or_q(part, Q(revoked_at__isnull=False))
        if folded in "已过期":
            part = or_q(part, Q(revoked_at__isnull=True) & Q(expires_at__lte=now))
        combined = or_q(combined, part)
    return combined


async def search_tokens(
    page: int = 1,
    page_size: int = 10,
    keyword: str | None = None,
    token_type: str | None = None,
    status: str | None = None,
    column_filters: Mapping[str, ColumnFilterValue] | None = None,
    column_filter_specs: Sequence[ColumnFilterSpec] = (),
) -> dict[str, Any]:
    """按关键词、类型、状态和列筛选分页查询令牌。"""
    now = datetime.now()
    query = Q()
    client_ids = await ids_by_keyword(keyword)
    keyword_q = or_q(
        build_keyword_q(
            (
                "jti",
                "expires_at",
                "last_used_at",
                "revoked_at",
                "created_at",
            ),
            keyword,
            model=ApiToken,
            labels={"token_type": {"access": "访问令牌", "refresh": "刷新令牌"}},
        ),
        Q(client_id__in=client_ids) if client_ids else None,
        _status_keyword_q(keyword, now),
    )
    if keyword_q:
        query &= keyword_q

    if token_type:
        query &= Q(token_type=token_type)

    if status == "active":
        query &= Q(revoked_at__isnull=True) & Q(expires_at__gt=now)
    elif status == "revoked":
        query &= Q(revoked_at__isnull=False)
    elif status == "expired":
        query &= Q(expires_at__lte=now)
    query = apply_column_filter_q(query, column_filter_specs, column_filters)

    total = await ApiToken.filter(query).count()
    tokens = await ApiToken.filter(query).offset((page - 1) * page_size).limit(page_size).order_by("-id")
    client_map = await map_by_ids([token.client_id for token in tokens])

    data = []
    for token in tokens:
        client_row = client_map.get(int(token.client_id)) if token.client_id else None
        data.append(
            {
                "id": token.id,
                "client_id": (client_row.get("client_id") if client_row else None) or "",
                "client_name": (client_row.get("name") if client_row else None) or "-",
                "token_type": _format_token_type(token.token_type),
                "jti": token.jti,
                "status": _compute_status(token, now),
                "expires_at": _format_time(token.expires_at) or "-",
                "last_used_at": _format_time(token.last_used_at) or "-",
                "revoked_at": _format_time(token.revoked_at) or "-",
                "created_at": _format_time(token.created_at) or "-",
            }
        )

    return {
        "total": total,
        "tokens": data,
    }
