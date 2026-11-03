"""业务域事务用例：确保默认管理员账号存在。"""

from __future__ import annotations

import uuid

from models import User
from modules.password.services import PasswordService


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
