"""业务域事务用例：校验账号密码并更新登录审计。"""

from __future__ import annotations

import uuid
from datetime import datetime

from models import User
from modules.password.services import PasswordService


async def authenticate_user(userid: str, password: str, ip_addr: str | None = None) -> User | None:
    """验证账号密码，成功后更新登录审计字段。"""
    user = await User.filter(userid=userid, is_active=True).first()
    if user is None:
        return None

    if not PasswordService.verify_password(password, user.password_hash):
        return None

    user.alternative_id = uuid.uuid4().hex
    user.last_active_at = datetime.now()
    user.login_count = (user.login_count or 0) + 1
    if ip_addr:
        user.ip_addr = ip_addr
    await user.save()
    return user
