"""系统能力：列表页门面。按声明接上搜索、列筛选、方案、列设置、导出与分页。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from nicegui import ui

from modules.column_filter.page_component import ColumnFilterController
from modules.excel.page_component import render_export_button
from modules.filter_scheme.page_component import FilterSchemeBindings, FilterSchemeController
from modules.filter_scheme.service import config_from_column_filters
from modules.keyword_search.page_component import render_keyword_search
from modules.table_column_setting.page_component import TableColumnSettingController
from modules.table_column_setting.service import TableColumnSettingConfig
from modules.ui.helpers import render_page_title
from modules.ui.paged_table import (
    compute_total_pages,
    map_rows_with_index,
    parse_pagination_event,
    render_standard_pagination,
    to_page_int,
)

from .spec import DEFAULT_PAGE_SIZE, ListPageSpec


@dataclass
class ListSearchState:
    """列表页检索状态：模糊搜索与分页。"""

    keyword: str = ""
    current_page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


def event_row(event_args: Any) -> dict[str, Any] | None:
    """从表格事件中读取稳定的行数据。"""
    row = event_args.args if hasattr(event_args, "args") else event_args
    return row if isinstance(row, dict) else None


class ListPageFacade:
    """按 ListPageSpec 装配一张列表页的搜索、筛选、方案、列设置与分页。"""

    def __init__(
        self,
        spec: ListPageSpec,
        *,
        on_refresh: Callable[[], Awaitable[None]],
        on_scheme_reset: Callable[[], None] | None = None,
    ) -> None:
        """初始化列表装配，不创建具体 UI。"""
        self.spec = spec
        self.on_refresh = on_refresh
        self.on_scheme_reset = on_scheme_reset
        self.search_state = ListSearchState(page_size=spec.default_page_size)
        self.search_input: Any = None
        self.table: Any = None
        self.pagination_container: Any = None
        self.export_button: Any = None
        self.column_filter: ColumnFilterController | None = None
        self.filter_scheme: FilterSchemeController | None = None
        if spec.column_filters:
            self.column_filter = ColumnFilterController(
                specs=spec.column_filters,
                on_apply=self._on_column_filter_apply,
            )
            if spec.initial_filter_values:
                self.column_filter.replace_values(spec.initial_filter_values)
            self.filter_scheme = FilterSchemeController(
                config=config_from_column_filters(
                    page_code=spec.page_code,
                    list_key=spec.list_key,
                    specs=spec.column_filters,
                ),
                bindings=FilterSchemeBindings(
                    get_values=self.column_filter.dump_values,
                    set_values=self._apply_scheme_values,
                    refresh=self.on_refresh,
                    render_field_editor=self.column_filter.render_field_editor,
                ),
            )
        self.column_setting = TableColumnSettingController(
            config=TableColumnSettingConfig(
                page_code=spec.page_code,
                table_key=spec.list_key,
                allowed_column_names=spec.allowed_column_names(),
                required_column_names=spec.required_column_names,
                default_visible_column_names=spec.resolved_visible_column_names(),
                column_name_aliases=(
                    dict(spec.column_name_aliases) if spec.column_name_aliases else None
                ),
            ),
            columns=list(spec.columns),
            get_tables=lambda: [self.table],
        )

    @property
    def is_mounted(self) -> bool:
        """表格与分页槽是否已挂到页面。"""
        return self.table is not None and self.pagination_container is not None

    def filter_kwargs(self) -> dict[str, Any]:
        """当前列筛选参数，供 service 查询与导出。"""
        if self.column_filter is None:
            return {}
        return {
            "column_filters": self.column_filter.active_values(),
            "column_filter_specs": self.column_filter.specs,
        }

    def page_and_size(self) -> tuple[int, int]:
        """归一化当前页码与每页条数。"""
        current_page = to_page_int(self.search_state.current_page, default=1)
        page_size = to_page_int(self.search_state.page_size, default=self.spec.default_page_size)
        self.search_state.current_page = current_page
        self.search_state.page_size = page_size
        return current_page, page_size

    def _apply_scheme_values(self, values: dict[str, Any]) -> None:
        """用方案快照完整替换列筛选，并清空模糊搜索。"""
        self.search_state.keyword = ""
        self.search_state.current_page = 1
        if self.search_input is not None:
            self.search_input.value = ""
        if self.column_filter is not None:
            self.column_filter.replace_values(values)
            self.column_filter.set_show_chips(True)
        if self.on_scheme_reset is not None:
            self.on_scheme_reset()

    async def _on_column_filter_apply(self) -> None:
        """列筛选变化后回到第一页并刷表。"""
        self.search_state.current_page = 1
        if self.filter_scheme is not None:
            self.filter_scheme.on_filters_changed()
        await self.on_refresh()

    async def do_search(self, _=None) -> None:
        """读取模糊搜索并刷新表格。"""
        self.search_state.keyword = str(getattr(self.search_input, "value", "") or "")
        self.search_state.current_page = 1
        await self.on_refresh()

    async def change_page(self, event: Any) -> None:
        """更新当前页码。"""
        self.search_state.current_page = parse_pagination_event(
            event,
            default=self.search_state.current_page,
        )
        await self.on_refresh()

    async def on_page_size_change(self, event: Any) -> None:
        """更新分页大小并回到第一页。"""
        self.search_state.page_size = parse_pagination_event(
            event,
            default=self.spec.default_page_size,
        )
        self.search_state.current_page = 1
        await self.on_refresh()

    def render_search(self) -> Any:
        """渲染模糊搜索框。自定义工具栏时单独调用。"""
        self.search_input = render_keyword_search(on_search=self.do_search)
        return self.search_input

    def render_save_scheme_button(self) -> Any | None:
        """渲染保存方案按钮；未声明列筛选时不渲染。"""
        if self.filter_scheme is None:
            return None
        return (
            ui.button(
                "保存方案",
                icon="bookmarks",
                color="secondary",
                on_click=self.filter_scheme.open_save_dialog,
            )
            .classes("font-bold")
            .props("outline rounded")
        )

    def render_export(self, *, on_click: Any) -> Any:
        """渲染导出按钮。权限由调用方决定是否调用。"""
        self.export_button = render_export_button(on_click=on_click)
        return self.export_button

    def open_save_scheme(self) -> None:
        """打开当前列表的保存方案弹窗。"""
        if self.filter_scheme is not None:
            self.filter_scheme.open_save_dialog()

    @contextmanager
    def render_toolbar(
        self,
        *,
        title: str | None = None,
        show_refresh: bool = True,
        on_export: Callable[..., Any] | None = None,
        show_save_scheme: bool = True,
    ) -> Generator[None, None, None]:
        """标准工具栏：标题、刷新、搜索、域内按钮、保存方案、导出。"""
        with ui.row().classes("w-full items-center justify-between gap-3 flex-wrap"):
            with ui.row().classes("items-center gap-3 flex-wrap"):
                if title:
                    render_page_title(title)
                if show_refresh:
                    with ui.button(
                        icon="refresh",
                        color="dark_page",
                        on_click=ui.navigate.reload,
                    ).classes("text-sm font-bold").props("flat rounded"):
                        ui.tooltip("刷新页面")
                self.render_search()
                yield
                if show_save_scheme:
                    self.render_save_scheme_button()
            if on_export is not None:
                self.render_export(on_click=on_export)

    def render_chips(self) -> None:
        """渲染方案芯片与列筛选芯片。"""
        if self.filter_scheme is not None:
            self.filter_scheme.render_chips()
        if self.column_filter is not None:
            self.column_filter.render_chips()

    def bind_table(self, table: Any) -> Any:
        """绑定表格；attach_column_filters 为 True 时装配列头筛选。"""
        self.table = table
        if self.column_filter is not None and self.spec.attach_column_filters:
            self.column_filter.attach(table)
        return table

    def render_pagination_slot(self) -> Any:
        """创建分页容器。"""
        self.pagination_container = ui.row().classes("mt-4 items-center")
        return self.pagination_container

    def mount(self, table: Any) -> Any:
        """芯片、表格筛选装配与分页槽一次挂上。"""
        self.render_chips()
        self.bind_table(table)
        self.render_pagination_slot()
        return table

    async def initialize(self) -> None:
        """拉取过滤方案与列偏好，不自动套用方案。"""
        if self.filter_scheme is not None:
            await self.filter_scheme.initialize()
        await self.column_setting.initialize()
        self.column_setting.apply_visible_columns()

    def apply_rows(self, rows: Sequence[dict[str, Any]], *, total: int) -> None:
        """写入表格行、同步列偏好与表头筛选，并渲染分页。"""
        if not self.is_mounted:
            return
        current_page, page_size = self.page_and_size()
        total_count = max(0, int(total))
        total_pages = compute_total_pages(total_count, page_size)
        if current_page > total_pages:
            current_page = total_pages
            self.search_state.current_page = current_page
        self.table.rows = list(rows)
        self.table.update()
        self.column_setting.apply_visible_columns()
        if self.column_filter is not None:
            self.column_filter.sync_header_state()
        render_standard_pagination(
            self.pagination_container,
            current_page=current_page,
            page_size=page_size,
            total=total_count,
            on_page_change=self.change_page,
            on_page_size_change=self.on_page_size_change,
            page_size_options=self.spec.resolved_page_size_options(),
            render_leading_content=self.column_setting.render_trigger,
        )

    def apply_items(
        self,
        items: Sequence[dict[str, Any]],
        *,
        total: int,
        row_mapper: Callable[[dict[str, Any], int], dict[str, Any]],
    ) -> None:
        """按当前分页给主数据加序号并刷表。"""
        current_page, page_size = self.page_and_size()
        rows = map_rows_with_index(
            list(items),
            current_page=current_page,
            page_size=page_size,
            row_mapper=row_mapper,
        )
        self.apply_rows(rows, total=total)
