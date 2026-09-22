"""系统能力：列表页门面。可被业务域引用。

业务域在 page_table 声明 ListPageSpec（列与筛选），由 ListPageFacade 接上
模糊搜索、列筛选、过滤方案、列设置、导出按钮与分页。
attach_column_filters 默认 True，自动给表格挂列头筛选。
本包禁止 import 业务域。
"""

from .facade import ListPageFacade, ListSearchState, event_row
from .spec import DEFAULT_PAGE_SIZE, ListPageSpec, default_page_size_options

__all__ = [
    "DEFAULT_PAGE_SIZE",
    "ListPageFacade",
    "ListPageSpec",
    "ListSearchState",
    "default_page_size_options",
    "event_row",
]
