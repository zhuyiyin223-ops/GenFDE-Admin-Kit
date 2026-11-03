"""系统能力：表格列显示偏好的读写与归一化。

只再导出。读写用例彼此不引用，列名归一化在 ``column_names``。
按账号持久化页面表格列偏好，并兼容列删除、改名和新增。
"""

from .column_names import TableColumnSettingConfig, normalize_visible_column_names
from .get_user_visible_column_names import get_user_visible_column_names
from .save_user_visible_column_names import save_user_visible_column_names

__all__ = [
    "TableColumnSettingConfig",        # 列偏好配置
    "get_user_visible_column_names",   # 读取当前账号的可见列
    "normalize_visible_column_names",  # 按当前列定义归一化可见列名
    "save_user_visible_column_names",  # 保存当前账号的可见列
]
