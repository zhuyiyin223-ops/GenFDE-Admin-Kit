"""系统能力：密码哈希与校验。"""

from __future__ import annotations

try:
    import bcrypt
except ImportError:  # pragma: no cover - 依赖缺失时给出明确错误
    bcrypt = None


class PasswordService:
    """密码哈希与校验。"""

    @staticmethod
    def hash_password(password: str) -> str:
        """生成 bcrypt 密码哈希。"""
        if bcrypt is None:
            raise RuntimeError("缺少 bcrypt 依赖，请先安装 requirements.txt")
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """校验明文密码与哈希是否匹配。"""
        if bcrypt is None:
            raise RuntimeError("缺少 bcrypt 依赖，请先安装 requirements.txt")
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
