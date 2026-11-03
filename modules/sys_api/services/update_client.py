"""业务域事务用例：更新 API 客户端。"""

from __future__ import annotations

from datetime import datetime

from models import ApiClient
from modules.password.services import PasswordService

_IP_WHITELIST_MAX_LEN = 1024


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


async def update_client(
    client_id: int,
    *,
    name: str | None = None,
    is_active: bool | None = None,
    new_secret: str | None = None,
    ip_whitelist: str | None = None,
) -> tuple[bool, str]:
    """更新 API 客户端名称、状态、密钥或 IP 白名单。"""
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
        normalized_whitelist = _normalize_ip_whitelist(ip_whitelist)
        if normalized_whitelist and len(normalized_whitelist) > _IP_WHITELIST_MAX_LEN:
            return False, "IP白名单长度过长"
        client.ip_whitelist = normalized_whitelist

    client.updated_at = datetime.now()
    await client.save()
    return True, "更新成功"
