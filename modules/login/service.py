"""登录认证服务。"""

from __future__ import annotations

import uuid
from datetime import datetime

from models import User
from modules.password.service import PasswordService


class LoginService:
    """登录事务服务。"""

    @staticmethod
    async def ensure_admin_user(*, userid: str, password: str, name: str) -> tuple[bool, str]:
        """确保默认管理员账号存在。

        只在账号不存在时创建，不修改已有账号密码和状态。
        """
        normalized_userid = str(userid or "").strip()
        normalized_password = str(password or "")
        normalized_name = str(name or "").strip() or normalized_userid
        if not normalized_userid:
            raise RuntimeError("DEFAULT_ADMIN_USERID 不能为空")
        if not normalized_password:
            raise RuntimeError("DEFAULT_ADMIN_PASSWORD 不能为空")

        existing_user = await User.filter(userid=normalized_userid).first()
        if existing_user is not None:
            return False, "默认管理员账号已存在"

        await User.create(
            userid=normalized_userid,
            password_hash=PasswordService.hash_password(normalized_password),
            name=normalized_name,
            is_active=True,
            is_admin=True,
            alternative_id=uuid.uuid4().hex,
            login_count=0,
        )
        return True, "默认管理员账号已创建"

    @staticmethod
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
