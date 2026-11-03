"""业务域事务用例：轮换刷新令牌。"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from models import ApiClient, ApiToken

from .token_codec import (
    app_now,
    create_access_token,
    create_refresh_token,
    decode_token,
    ensure_ip_allowed,
    hash_token,
)


async def rotate_refresh_token(refresh_token: str, ip_addr: str | None = None) -> dict[str, Any]:
    """校验刷新令牌后作废旧令牌，并签发新的访问令牌与刷新令牌。"""
    payload = decode_token(refresh_token, "refresh")

    client_id = payload.get("sub")
    jti = payload.get("jti")
    if not client_id or not jti:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    client = await ApiClient.filter(client_id=client_id, is_active=True).first()
    if not client:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Client not found or inactive")

    ensure_ip_allowed(client, ip_addr)

    token_record = await ApiToken.filter(jti=jti, client_id=client.id).first()
    if not token_record or token_record.revoked_at:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked")

    if token_record.expires_at < app_now():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    if token_record.token_hash != hash_token(refresh_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token mismatch")

    token_record.revoked_at = app_now()
    token_record.last_used_at = app_now()
    await token_record.save()

    access_token, access_exp = create_access_token(client)
    new_refresh_token, refresh_exp = await create_refresh_token(client)

    return {
        "client": client,
        "access_token": access_token,
        "access_expires_at": access_exp,
        "refresh_token": new_refresh_token,
        "refresh_expires_at": refresh_exp,
    }
