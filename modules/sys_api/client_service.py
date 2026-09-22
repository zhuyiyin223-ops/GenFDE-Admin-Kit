from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from tortoise.expressions import Q

from models import ApiClient
from modules.column_filter.service import ColumnFilterSpec, ColumnFilterValue, apply_column_filter_q
from modules.keyword_search.service import STATUS_LABELS, build_keyword_q
from modules.password.service import PasswordService


class ApiClientService:
    """API客户端账号事务类"""

    IP_WHITELIST_MAX_LEN = 1024

    @staticmethod
    def _normalize_ip_whitelist(value: str | None) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        for sep in ("\n", "\r", "\t", ";", "，"):
            text = text.replace(sep, ",")
        parts = [part.strip() for part in text.split(",") if part.strip()]
        return ",".join(parts) if parts else None

    @staticmethod
    async def create_client(
            client_id: str,
            client_secret: str,
            name: str | None = None,
            ip_whitelist: str | None = None,
            is_active: bool = True,
    ) -> tuple[bool, str, ApiClient | None]:
        client_id = (client_id or "").strip()
        if not client_id:
            return False, "账号不能为空", None

        existing = await ApiClient.filter(client_id=client_id).first()
        if existing:
            return False, "该账号已存在", None

        normalized_whitelist = ApiClientService._normalize_ip_whitelist(ip_whitelist)
        if normalized_whitelist and len(normalized_whitelist) > ApiClientService.IP_WHITELIST_MAX_LEN:
            return False, "IP白名单长度过长", None

        client = await ApiClient.create(
            client_id=client_id,
            name=(name or "").strip() or None,
            password_hash=PasswordService.hash_password(client_secret),
            is_active=bool(is_active),
            ip_whitelist=normalized_whitelist,
        )
        return True, "创建成功", client

    @staticmethod
    async def update_client(
            client_id: int,
            *,
            name: str | None = None,
            is_active: bool | None = None,
            new_secret: str | None = None,
            ip_whitelist: str | None = None,
    ) -> tuple[bool, str]:
        client = await ApiClient.filter(id=client_id).first()
        if not client:
            return False, "客户端不存在"

        if name is not None:
            client.name = (name or "").strip() or None
        if is_active is not None:
            client.is_active = bool(is_active)
        if new_secret:
            client.password_hash = PasswordService.hash_password(new_secret)
        if ip_whitelist is not None:
            normalized_whitelist = ApiClientService._normalize_ip_whitelist(ip_whitelist)
            if normalized_whitelist and len(normalized_whitelist) > ApiClientService.IP_WHITELIST_MAX_LEN:
                return False, "IP白名单长度过长"
            client.ip_whitelist = normalized_whitelist

        client.updated_at = datetime.now()
        await client.save()
        return True, "更新成功"

    @staticmethod
    async def get_client_detail(client_id: int) -> dict[str, Any] | None:
        client = await ApiClient.filter(id=client_id).first()
        if not client:
            return None

        return {
            "id": client.id,
            "client_id": client.client_id,
            "name": client.name,
            "is_active": client.is_active,
            "last_login_at": client.last_login_at.strftime('%Y-%m-%d %H:%M') if client.last_login_at else None,
            "last_ip": client.last_ip,
            "ip_whitelist": client.ip_whitelist,
            "created_at": client.created_at.strftime('%Y-%m-%d %H:%M'),
            "updated_at": client.updated_at.strftime('%Y-%m-%d %H:%M') if client.updated_at else None,
        }

    @staticmethod
    async def search_clients(
            page: int = 1,
            page_size: int = 10,
            keyword: str | None = None,
            status: bool | None = None,
            column_filters: Mapping[str, ColumnFilterValue] | None = None,
            column_filter_specs: Sequence[ColumnFilterSpec] = (),
    ) -> dict[str, Any]:
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
            data.append({
                "id": client.id,
                "client_id": client.client_id,
                "name": client.name,
                "is_active": client.is_active,
                "last_login_at": client.last_login_at.strftime('%Y-%m-%d %H:%M') if client.last_login_at else None,
                "last_ip": client.last_ip or "",
                "ip_whitelist": client.ip_whitelist or "",
                "created_at": client.created_at.strftime('%Y-%m-%d %H:%M'),
                "updated_at": client.updated_at.strftime('%Y-%m-%d %H:%M') if client.updated_at else None,
            })

        return {
            "total": total,
            "clients": data,
        }

    @staticmethod
    async def authenticate_client(client_id: str, client_secret: str) -> ApiClient | None:
        client = await ApiClient.filter(client_id=client_id, is_active=True).first()
        if not client:
            return None

        if PasswordService.verify_password(client_secret, client.password_hash):
            return client
        return None

    @staticmethod
    async def get_active_client_by_client_id(client_id: object) -> ApiClient | None:
        """按客户端标识查询启用的 API 客户端。"""
        normalized_client_id = str(client_id or "").strip()
        if not normalized_client_id:
            return None
        return await ApiClient.filter(client_id=normalized_client_id, is_active=True).first()

    @staticmethod
    async def ids_by_keyword(keyword: str | None) -> list[int]:
        """按账号或名称关键词反查客户端主键。"""
        client_q = build_keyword_q(("client_id", "name"), keyword, model=ApiClient)
        if client_q is None:
            return []
        return [int(pk) for pk in await ApiClient.filter(client_q).values_list("id", flat=True)]

    @staticmethod
    async def map_by_ids(client_ids: Sequence[int | None]) -> dict[int, dict[str, Any]]:
        """按主键批量读取客户端账号与名称。"""
        unique_ids = list({int(client_id) for client_id in client_ids if client_id})
        if not unique_ids:
            return {}
        rows = await ApiClient.filter(id__in=unique_ids).values("id", "client_id", "name")
        return {int(row["id"]): row for row in rows if row.get("id") is not None}
