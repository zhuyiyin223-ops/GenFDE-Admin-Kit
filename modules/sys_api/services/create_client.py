"""业务域事务用例：创建 API 客户端。"""

from __future__ import annotations

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


async def create_client(
    client_id: str,
    client_secret: str,
    name: str | None = None,
    ip_whitelist: str | None = None,
    is_active: bool = True,
) -> tuple[bool, str, ApiClient | None]:
    """创建 API 客户端账号。"""
    client_id = (client_id or "").strip()
    if not client_id:
        return False, "账号不能为空", None

    existing = await ApiClient.filter(client_id=client_id).first()
    if existing:
        return False, "该账号已存在", None

    normalized_whitelist = _normalize_ip_whitelist(ip_whitelist)
    if normalized_whitelist and len(normalized_whitelist) > _IP_WHITELIST_MAX_LEN:
        return False, "IP白名单长度过长", None

    client = await ApiClient.create(
        client_id=client_id,
        name=(name or "").strip() or None,
        password_hash=PasswordService.hash_password(client_secret),
        is_active=bool(is_active),
        ip_whitelist=normalized_whitelist,
    )
    return True, "创建成功", client
