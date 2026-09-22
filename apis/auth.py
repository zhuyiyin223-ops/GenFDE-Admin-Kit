"""API 认证接口。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from modules.sys_api.auth_service import ensure_ip_allowed, issue_tokens_for_client, rotate_refresh_token
from modules.sys_api.client_service import ApiClientService


router = APIRouter(prefix="/api/auth", tags=["auth"])


class TokenRequest(BaseModel):
    """获取令牌请求。"""

    client_id: str = Field(..., max_length=64)
    client_secret: str = Field(..., min_length=6, max_length=128)


class TokenResponse(BaseModel):
    """令牌响应。"""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_expires_in: int


class RefreshRequest(BaseModel):
    """刷新令牌请求。"""

    refresh_token: str


@router.post("/token", response_model=TokenResponse)
async def issue_token(payload: TokenRequest, request: Request):
    """使用客户端账号密码换取访问令牌和刷新令牌。"""
    client = await ApiClientService.authenticate_client(payload.client_id, payload.client_secret)
    if not client:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid client credentials")

    ip_addr = request.state.real_ip if hasattr(request, "state") else (request.client.host if request.client else None)
    ensure_ip_allowed(client, ip_addr)
    tokens = await issue_tokens_for_client(client, ip_addr=ip_addr)
    access_expires = tokens["access_expires_at"]
    refresh_expires = tokens["refresh_expires_at"]

    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "Bearer",
        "expires_in": int((access_expires - datetime.now()).total_seconds()),
        "refresh_expires_in": int((refresh_expires - datetime.now()).total_seconds()),
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshRequest, request: Request):
    """使用刷新令牌换取新的访问令牌和刷新令牌。"""
    ip_addr = request.state.real_ip if hasattr(request, "state") else (request.client.host if request.client else None)
    tokens = await rotate_refresh_token(payload.refresh_token, ip_addr=ip_addr)
    access_expires = tokens["access_expires_at"]
    refresh_expires = tokens["refresh_expires_at"]
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "Bearer",
        "expires_in": int((access_expires - datetime.now()).total_seconds()),
        "refresh_expires_in": int((refresh_expires - datetime.now()).total_seconds()),
    }
