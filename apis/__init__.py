"""外部 API 鉴权依赖。"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from models import ApiClient
from modules.sys_api.auth_service import decode_token, ensure_ip_allowed


security = HTTPBearer(auto_error=False)


async def get_current_client(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> ApiClient:
    """解析并校验当前 API 客户端。"""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    payload = decode_token(credentials.credentials, "access")
    client_id = payload.get("sub")
    if not client_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    client = await ApiClient.filter(client_id=client_id, is_active=True).first()
    if not client:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Client not found or inactive")

    ip_addr = request.state.real_ip if hasattr(request, "state") else (request.client.host if request.client else None)
    ensure_ip_allowed(client, ip_addr)
    return client
