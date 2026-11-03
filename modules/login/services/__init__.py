"""业务域：登录认证。

只再导出。用例文件彼此不引用。
"""

from .authenticate_user import authenticate_user
from .ensure_admin_user import ensure_admin_user

__all__ = [
    "authenticate_user",  # 校验账号密码并更新登录审计
    "ensure_admin_user",  # 账号不存在时创建默认管理员
]
