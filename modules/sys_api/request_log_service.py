from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from tortoise.expressions import Q

from models import ApiClient, ApiRequestLog
from modules.column_filter.service import ColumnFilterSpec, ColumnFilterValue, apply_column_filter_q
from modules.keyword_search.service import build_keyword_q, or_q

from .client_service import ApiClientService


class ApiRequestLogService:
    """API请求日志事务类"""

    @staticmethod
    def _format_time(value) -> str | None:
        if not value:
            return None
        return value.strftime("%Y-%m-%d %H:%M")

    @staticmethod
    async def create_log(
        *,
        client: ApiClient | None = None,
        client_id_text: str | None = None,
        method: str,
        path: str,
        status_code: int,
        ip_addr: str | None = None,
        user_agent: str | None = None,
        request_body: str | None = None,
        response_body: str | None = None,
        process_ms: int | None = None,
    ) -> None:
        await ApiRequestLog.create(
            client_id=client.id if client is not None else None,
            client_id_text=client_id_text or (client.client_id if client else None),
            method=method,
            path=path,
            status_code=status_code,
            ip_addr=ip_addr,
            user_agent=user_agent,
            request_body=request_body,
            response_body=response_body,
            process_ms=process_ms,
            created_at=datetime.now(),
        )

    @staticmethod
    async def search_logs(
        page: int = 1,
        page_size: int = 10,
        keyword: str | None = None,
        status_code: int | None = None,
        column_filters: Mapping[str, ColumnFilterValue] | None = None,
        column_filter_specs: Sequence[ColumnFilterSpec] = (),
    ) -> dict[str, Any]:
        query = Q()
        client_ids = await ApiClientService.ids_by_keyword(keyword)
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
        logs = (
            await ApiRequestLog.filter(query)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .order_by("-id")
        )
        client_map = await ApiClientService.map_by_ids([log.client_id for log in logs])

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
                    "created_at": ApiRequestLogService._format_time(log.created_at) or "-",
                }
            )

        return {
            "total": total,
            "logs": data,
        }

    @staticmethod
    async def get_log_detail(log_id: int) -> dict[str, Any] | None:
        log = await ApiRequestLog.filter(id=log_id).first()
        if not log:
            return None
        client_map = await ApiClientService.map_by_ids([log.client_id])
        client_row = client_map.get(int(log.client_id)) if log.client_id else None
        return {
            "id": log.id,
            "client_id": (client_row.get("client_id") if client_row else None) or log.client_id_text or "",
            "client_name": (client_row.get("name") if client_row else None) or "",
            "method": log.method,
            "path": log.path,
            "status_code": log.status_code,
            "ip_addr": log.ip_addr or "",
            "user_agent": log.user_agent or "",
            "process_ms": log.process_ms,
            "request_body": log.request_body or "",
            "response_body": log.response_body or "",
            "created_at": ApiRequestLogService._format_time(log.created_at) or "-",
        }
