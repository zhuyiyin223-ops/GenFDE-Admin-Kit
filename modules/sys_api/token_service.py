from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from tortoise.expressions import Q

from models import ApiToken
from modules.column_filter.service import ColumnFilterSpec, ColumnFilterValue, apply_column_filter_q
from modules.keyword_search.service import build_keyword_q, or_q, split_keywords

from .client_service import ApiClientService


class ApiTokenService:
    """API令牌日志事务类"""

    @staticmethod
    def _format_time(value) -> str | None:
        if not value:
            return None
        return value.strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def _format_token_type(token_type: str | None) -> str:
        if token_type == "access":
            return "访问令牌"
        if token_type == "refresh":
            return "刷新令牌"
        return token_type or "-"

    @staticmethod
    def _compute_status(token: ApiToken, now) -> str:
        if token.revoked_at:
            return "已撤销"
        if token.expires_at and token.expires_at <= now:
            return "已过期"
        return "有效"

    @staticmethod
    def _status_keyword_q(keyword: str | None, now) -> Q | None:
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

    @staticmethod
    async def search_tokens(
        page: int = 1,
        page_size: int = 10,
        keyword: str | None = None,
        token_type: str | None = None,
        status: str | None = None,
        column_filters: Mapping[str, ColumnFilterValue] | None = None,
        column_filter_specs: Sequence[ColumnFilterSpec] = (),
    ) -> dict[str, Any]:
        now = datetime.now()
        query = Q()
        client_ids = await ApiClientService.ids_by_keyword(keyword)
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
            ApiTokenService._status_keyword_q(keyword, now),
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
        tokens = (
            await ApiToken.filter(query)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .order_by("-id")
        )
        client_map = await ApiClientService.map_by_ids([token.client_id for token in tokens])

        data = []
        for token in tokens:
            client_row = client_map.get(int(token.client_id)) if token.client_id else None
            data.append(
                {
                    "id": token.id,
                    "client_id": (client_row.get("client_id") if client_row else None) or "",
                    "client_name": (client_row.get("name") if client_row else None) or "-",
                    "token_type": ApiTokenService._format_token_type(token.token_type),
                    "jti": token.jti,
                    "status": ApiTokenService._compute_status(token, now),
                    "expires_at": ApiTokenService._format_time(token.expires_at) or "-",
                    "last_used_at": ApiTokenService._format_time(token.last_used_at) or "-",
                    "revoked_at": ApiTokenService._format_time(token.revoked_at) or "-",
                    "created_at": ApiTokenService._format_time(token.created_at) or "-",
                }
            )

        return {
            "total": total,
            "tokens": data,
        }
