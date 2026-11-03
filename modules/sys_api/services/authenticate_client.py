"""业务域事务用例：校验 API 客户端账号密码。"""

from __future__ import annotations

from models import ApiClient
from modules.password.services import PasswordService


async def authenticate_client(client_id: str, client_secret: str) -> ApiClient | None:
    """校验启用中的客户端账号与密钥。"""
    client = await ApiClient.filter(client_id=client_id, is_active=True).first()
    if not client:
        return None

    if PasswordService.verify_password(client_secret, client.password_hash):
        return client
    return None
