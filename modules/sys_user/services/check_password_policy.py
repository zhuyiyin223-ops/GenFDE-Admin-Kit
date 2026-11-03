"""业务域：用户密码策略。纯规则，不是事务。"""

from __future__ import annotations

import re


def is_password_policy_valid(password: str) -> bool:
    """校验旧系统同款密码策略。"""
    text = str(password or "").strip()
    if not 6 <= len(text) <= 16:
        return False
    return bool(
        re.search(r"[A-Z]", text)
        and re.search(r"[a-z]", text)
        and re.search(r"\d", text)
        and re.search(r"[^A-Za-z0-9]", text)
    )
