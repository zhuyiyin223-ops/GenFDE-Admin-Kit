"""业务域事务用例：为客户端签发访问令牌和刷新令牌。"""

from __future__ import annotations

from typing import Any

from models import ApiClient

from .token_codec import app_now, create_access_token, create_refresh_token


async def issue_tokens_for_client(client: ApiClient, ip_addr: str | None = None) -> dict[str, Any]:
    """签发一对令牌，并记录客户端最近登录时间与 IP。"""
    access_token, access_exp = create_access_token(client)
    refresh_token, refresh_exp = await create_refresh_token(client)

    client.last_login_at = app_now()
    if ip_addr:
        client.last_ip = ip_addr
    await client.save()

    return {
        "access_token": access_token,
        "access_expires_at": access_exp,
        "refresh_token": refresh_token,
        "refresh_expires_at": refresh_exp,
    }
