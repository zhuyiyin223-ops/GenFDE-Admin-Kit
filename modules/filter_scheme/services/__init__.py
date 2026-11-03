"""系统能力：列表过滤方案的读写、校验与编解码。

只再导出。用例文件彼此不引用，编解码在 ``scheme_values``，归属校验在 ``scheme_access``。
按账号保存个人结构化筛选快照，不含关键字与分页，不可分享。
"""

from .create_scheme import create_scheme
from .delete_scheme import delete_scheme
from .list_schemes import list_schemes
from .scheme_values import (
    EMPTY_SCHEME_ERROR,
    FilterScheme,
    FilterSchemeConfig,
    FilterSchemeField,
    config_from_column_filters,
    describe_active_fields,
    describe_values,
    encode_values,
    is_default_values,
    to_widget_values,
    values_equal,
)
from .update_scheme import update_scheme

__all__ = [
    "EMPTY_SCHEME_ERROR",          # 当前没有可保存的筛选条件
    "FilterScheme",                # 过滤方案
    "FilterSchemeConfig",          # 方案字段配置
    "FilterSchemeField",           # 方案字段
    "config_from_column_filters",  # 按列头筛选声明生成方案配置
    "create_scheme",               # 新建个人方案
    "delete_scheme",               # 删除自己创建的方案
    "describe_active_fields",      # 整理非默认条件
    "describe_values",             # 整理弹窗展示用的条件文案
    "encode_values",               # 把控件值编码为存储形态
    "is_default_values",           # 判断是否等于字段默认值
    "list_schemes",                # 列出当前用户的个人方案
    "to_widget_values",            # 把存储形态展开为控件值
    "update_scheme",               # 更新自己创建的方案
    "values_equal",                # 比较两份存储形态是否相等
]
