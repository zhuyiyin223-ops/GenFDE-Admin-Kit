"""系统能力：权限定义、鉴权与菜单上下文。

只再导出。用例文件彼此不引用，只依赖 ``permission_context``。
"""

from .clear_user_permission_cache import clear_user_permission_cache
from .get_cached_user_permissions import get_cached_user_permissions
from .get_first_accessible_path import get_first_accessible_path
from .has_permission import has_permission
from .permission_context import UserPermissionContext

__all__ = [
    "UserPermissionContext",        # 当前用户的权限上下文
    "clear_user_permission_cache",  # 清理当前会话权限缓存
    "get_cached_user_permissions",  # 读取用户权限编码
    "get_first_accessible_path",    # 解析登录后首个可访问页面
    "has_permission",               # 判断是否拥有指定权限
]
