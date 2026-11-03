"""业务域：用户账号与附件。

只再导出。用例文件彼此不引用。列表与导出共用 ``user_rows``，附件路径边界在 ``attachment_storage``，二者都不是事务。
"""

from .attachment_storage import USER_ATTACHMENT_MAX_FILES, USER_ATTACHMENT_MAX_SIZE
from .check_password_policy import is_password_policy_valid
from .create_user import create_user
from .delete_attachment import delete_attachment
from .export_users import export_users
from .get_attachment_file import get_attachment_file
from .get_role_options import get_role_options
from .get_user_detail import get_user_detail
from .list_attachments import list_attachments
from .save_attachments import save_attachments
from .search_users import search_users
from .update_user import update_user

__all__ = [
    "USER_ATTACHMENT_MAX_FILES",  # 单用户附件数量上限
    "USER_ATTACHMENT_MAX_SIZE",   # 单个附件大小上限
    "create_user",                # 创建用户账号并关联角色
    "delete_attachment",          # 删除用户附件
    "export_users",               # 按当前筛选导出用户
    "get_attachment_file",        # 读取附件文件
    "get_role_options",           # 读取可选角色
    "get_user_detail",            # 读取用户详情
    "is_password_policy_valid",   # 校验密码是否符合策略
    "list_attachments",           # 查询用户附件
    "save_attachments",           # 保存用户附件
    "search_users",               # 分页查询用户
    "update_user",                # 更新用户账号并替换角色关系
]
