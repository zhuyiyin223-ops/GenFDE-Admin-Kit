"""业务域：API 令牌编解码与 IP 白名单。非事务，签发与刷新共用。"""

from __future__ import annotations

import hashlib
import ipaddress
import secrets
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException, status

from models import ApiClient, ApiToken
from settings import API_AUTH, SECRETS

try:
    from jwt import decode as jwt_decode
    from jwt import encode as jwt_encode
    from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
except ImportError:  # pragma: no cover - 依赖缺失时由运行时给出明确错误
    jwt_decode = None
    jwt_encode = None
    ExpiredSignatureError = InvalidTokenError = Exception


def app_now() -> datetime:
    """返回本地当前时间。"""
    return datetime.now()


def require_jwt_secret() -> str:
    """读取已配置的 JWT 密钥。"""
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


def hash_token(token: str) -> str:
    """计算令牌摘要，用于刷新令牌落库比对。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def is_ip_allowed(client: ApiClient, ip_addr: str | None) -> bool:
    """判断请求 IP 是否落在客户端白名单内。空白名单表示不限制。"""
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
            elif ip == ipaddress.ip_address(entry):
                return True
        except ValueError:
            continue
    return False


def ensure_ip_allowed(client: ApiClient, ip_addr: str | None) -> None:
    """拒绝不在白名单内的请求 IP。"""
    if not is_ip_allowed(client, ip_addr):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="IP not allowed")


def build_claims(client_id: str, token_type: str, expires_at: datetime, jti: str) -> dict[str, Any]:
    """组装访问令牌或刷新令牌的声明。"""
    return {
        "iss": API_AUTH.issuer,
        "aud": API_AUTH.audience,
        "sub": client_id,
        "iat": int(app_now().timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": jti,
        "token_type": token_type,
    }


def create_access_token(client: ApiClient) -> tuple[str, datetime]:
    """签发访问令牌，不落库。"""
    secret = require_jwt_secret()
    expires_at = app_now() + timedelta(minutes=API_AUTH.access_ttl_minutes)
    jti = secrets.token_hex(16)
    claims = build_claims(client.client_id, "access", expires_at, jti)
    token = jwt_encode(claims, secret, algorithm=API_AUTH.algorithm)
    return token, expires_at


async def create_refresh_token(client: ApiClient) -> tuple[str, datetime]:
    """签发刷新令牌并写入令牌表。"""
    secret = require_jwt_secret()
    expires_at = app_now() + timedelta(days=API_AUTH.refresh_ttl_days)
    jti = secrets.token_hex(32)
    claims = build_claims(client.client_id, "refresh", expires_at, jti)
    token = jwt_encode(claims, secret, algorithm=API_AUTH.algorithm)

    await ApiToken.create(
        client_id=client.id,
        jti=jti,
        token_hash=hash_token(token),
        token_type="refresh",
        expires_at=expires_at,
    )
    return token, expires_at


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    """校验并解码指定类型的 JWT。"""
    secret = require_jwt_secret()
    try:
        payload = jwt_decode(
            token,
            secret,
            algorithms=[API_AUTH.algorithm],
            audience=API_AUTH.audience,
            issuer=API_AUTH.issuer,
        )
    except ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired") from None
    except InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from None

    if payload.get("token_type") != expected_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    return payload
