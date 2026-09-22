from __future__ import annotations

import hashlib
import secrets
import ipaddress
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple

from fastapi import HTTPException, status

from models import ApiClient, ApiToken
from settings import API_AUTH, SECRETS

try:
    from jwt import decode as jwt_decode, encode as jwt_encode
    from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
except ImportError:  # pragma: no cover - 依赖缺失时由运行时给出明确错误
    jwt_decode = None
    jwt_encode = None
    ExpiredSignatureError = InvalidTokenError = Exception


def _now() -> datetime:
    return datetime.now()


def _require_jwt_secret() -> str:
    if jwt_encode is None or jwt_decode is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PyJWT not installed",
        )
    if not SECRETS.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT secret not configured",
        )
    return SECRETS.jwt_secret


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def is_ip_allowed(client: ApiClient, ip_addr: Optional[str]) -> bool:
    whitelist = (client.ip_whitelist or "").strip()
    if not whitelist:
        return True
    if not ip_addr:
        return False
    try:
        ip = ipaddress.ip_address(ip_addr)
    except ValueError:
        return False

    entries = [item.strip() for item in whitelist.split(",") if item.strip()]
    for entry in entries:
        try:
            if "/" in entry:
                if ip in ipaddress.ip_network(entry, strict=False):
                    return True
            else:
                if ip == ipaddress.ip_address(entry):
                    return True
        except ValueError:
            continue
    return False


def ensure_ip_allowed(client: ApiClient, ip_addr: Optional[str]) -> None:
    if not is_ip_allowed(client, ip_addr):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="IP not allowed")


def _build_claims(
        client_id: str,
        token_type: str,
        expires_at: datetime,
        jti: str,
) -> Dict[str, Any]:
    return {
        "iss": API_AUTH.issuer,
        "aud": API_AUTH.audience,
        "sub": client_id,
        "iat": int(_now().timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": jti,
        "token_type": token_type,
    }


def create_access_token(client: ApiClient) -> Tuple[str, datetime]:
    secret = _require_jwt_secret()
    expires_at = _now() + timedelta(minutes=API_AUTH.access_ttl_minutes)
    jti = secrets.token_hex(16)
    claims = _build_claims(client.client_id, "access", expires_at, jti)
    token = jwt_encode(claims, secret, algorithm=API_AUTH.algorithm)
    return token, expires_at


async def create_refresh_token(client: ApiClient) -> Tuple[str, datetime]:
    secret = _require_jwt_secret()
    expires_at = _now() + timedelta(days=API_AUTH.refresh_ttl_days)
    jti = secrets.token_hex(32)
    claims = _build_claims(client.client_id, "refresh", expires_at, jti)
    token = jwt_encode(claims, secret, algorithm=API_AUTH.algorithm)

    await ApiToken.create(
        client_id=client.id,
        jti=jti,
        token_hash=_hash_token(token),
        token_type="refresh",
        expires_at=expires_at,
    )
    return token, expires_at


def decode_token(token: str, expected_type: str) -> Dict[str, Any]:
    secret = _require_jwt_secret()
    try:
        payload = jwt_decode(
            token,
            secret,
            algorithms=[API_AUTH.algorithm],
            audience=API_AUTH.audience,
            issuer=API_AUTH.issuer,
        )
    except ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if payload.get("token_type") != expected_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    return payload


async def rotate_refresh_token(refresh_token: str, ip_addr: Optional[str] = None) -> Dict[str, Any]:
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

    if token_record.expires_at < _now():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    if token_record.token_hash != _hash_token(refresh_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token mismatch")

    token_record.revoked_at = _now()
    token_record.last_used_at = _now()
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


async def issue_tokens_for_client(
        client: ApiClient,
        ip_addr: Optional[str] = None,
) -> Dict[str, Any]:
    access_token, access_exp = create_access_token(client)
    refresh_token, refresh_exp = await create_refresh_token(client)

    client.last_login_at = _now()
    if ip_addr:
        client.last_ip = ip_addr
    await client.save()

    return {
        "access_token": access_token,
        "access_expires_at": access_exp,
        "refresh_token": refresh_token,
        "refresh_expires_at": refresh_exp,
    }
