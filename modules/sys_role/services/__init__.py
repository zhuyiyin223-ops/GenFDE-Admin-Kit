"""业务域：角色权限。

只再导出。用例文件彼此不引用。列表与导出共用 ``role_rows``，导出不得调用列表用例。
"""

from .create_role import create_role
from .delete_role import delete_role
from .export_roles import export_roles
from .get_role_by_id import get_role_by_id
from .get_roles_with_details import get_roles_with_details
from .update_role import update_role

__all__ = [
    "create_role",             # 创建角色并保存权限
    "delete_role",             # 删除角色及其关联关系
    "export_roles",            # 按当前筛选导出角色
    "get_role_by_id",          # 读取角色详情
    "get_roles_with_details",  # 分页查询角色及关联展示
    "update_role",             # 更新角色并替换权限
]
