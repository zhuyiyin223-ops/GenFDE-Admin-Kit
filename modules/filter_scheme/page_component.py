"""系统能力：列表过滤方案的保存/编辑弹窗与表格上方芯片。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from nicegui import app, ui
from nicegui.events import SortableEventArguments

from modules.ui.helpers import clear_element

from .service import EMPTY_SCHEME_ERROR, FilterScheme, FilterSchemeConfig, FilterSchemeService

CHIP_ROW_CLASSES = "ng-filter-scheme-row w-full items-center justify-start gap-2 flex-wrap min-h-0 mt-2"
CHIP_CLASSES = "ng-filter-scheme-chip max-w-40"
DIALOG_CARD_CLASSES = "w-[420px] max-w-[95vw] max-h-[92vh] overflow-auto rounded-2xl shadow-xl"
EDIT_DIALOG_CARD_CLASSES = "w-[760px] max-w-[95vw] max-h-[92vh] overflow-auto rounded-2xl shadow-xl"
FORM_FIELD_PROPS = "dense outlined hide-bottom-space autocomplete=off"
FIELD_BOARD_CARD_CLASSES = (
    "ng-filter-scheme-field-card w-40 flex-none min-w-0 self-start items-stretch "
    "max-[640px]:w-full"
)
EDITOR_BOARD_CARD_CLASSES = "flex-1 min-w-0 self-start"
SORT_SCROLL_CLASSES = "ng-filter-scheme-sort-scroll w-full"
SORT_COLUMN_CLASSES = "ng-filter-scheme-sort-column w-full gap-0"
SORT_ITEM_CLASSES = (
    "ng-filter-scheme-sort-item w-full items-center no-wrap gap-0 px-1 rounded text-sm "
    "cursor-grab active:cursor-grabbing select-none hover:bg-slate-50"
)
SORT_ITEM_LABEL_CLASSES = "min-w-0 flex-1 truncate text-left"
SORT_ITEM_ACTION_CLASSES = "ng-filter-scheme-sort-action text-grey-6"
SORT_ITEM_SELECTED_CLASS = "bg-slate-100"
SORT_OPTIONS = {"filter": ".ng-filter-scheme-sort-action", "preventOnFilter": True}
CHIP_CSS = """
.ng-filter-scheme-chip:not(.q-chip--outline).q-chip,
.ng-filter-scheme-chip:not(.q-chip--outline) .q-chip__content,
.ng-filter-scheme-chip:not(.q-chip--outline) .q-icon {
    color: #fff !important;
}
.ng-filter-scheme-chip.q-chip--outline {
    background-color: transparent !important;
}
.ng-filter-scheme-field-card {
    padding: 0.5rem;
    gap: 0.5rem;
    align-items: stretch;
}
.ng-filter-scheme-sort-scroll {
    display: block;
    width: 100%;
    height: 16rem;
    overflow-x: hidden;
    overflow-y: auto;
    flex-shrink: 0;
    align-self: stretch;
}
.ng-filter-scheme-sort-column {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    justify-content: flex-start;
    width: 100%;
    flex: none;
    min-height: min-content;
    gap: 0;
}
.ng-filter-scheme-sort-item {
    display: flex;
    flex-direction: row;
    align-items: center;
    box-sizing: border-box;
    width: 100%;
    flex: none;
    min-height: 2rem;
    gap: 0;
}
.ng-filter-scheme-sort-action,
.ng-filter-scheme-sort-action.q-btn {
    min-width: 1.25rem;
    width: 1.25rem;
    height: 1.25rem;
    padding: 0;
    cursor: pointer;
}
.ng-filter-scheme-sort-action .q-icon {
    font-size: 1rem;
}
"""


@dataclass
class FilterSchemeBindings:
    """业务页提供的控件读写与刷新。

    get_values 只返回结构化筛选取值的控件形态，禁止含 keyword / 分页。
    set_values 入参已是控件形态，必须用该快照完整替换当前结构化筛选，不得与旧条件合并，
    并清空模糊搜索、current_page=1。
    refresh 只根据 search_state 刷表，禁止再从控件读值，禁止传入 do_search。
    render_field_editor 在当前上下文渲染单字段筛选控件，变更时只把快照交给回调，不得改表格筛选。
    """

    get_values: Callable[[], dict[str, Any]]
    set_values: Callable[[dict[str, Any]], None]
    refresh: Callable[[], Awaitable[None]]
    render_field_editor: Callable[[str, Any, Callable[[Any], None]], None] | None = None


@dataclass
class FilterSchemeState:
    """过滤方案页面状态。"""

    schemes: list[FilterScheme] = field(default_factory=list)
    active_scheme_id: int | None = None
    unavailable: bool = False


class FilterSchemeController:
    """过滤方案保存/编辑弹窗与表格上方芯片。"""

    def __init__(
        self,
        *,
        config: FilterSchemeConfig,
        bindings: FilterSchemeBindings,
        get_user_id: Callable[[], int | None] | None = None,
    ) -> None:
        self.config = config
        self.bindings = bindings
        self.get_user_id = get_user_id or self._default_get_user_id
        self.state = FilterSchemeState()
        self._chip_row: Any = None
        self._save_dialog: Any = None
        self._edit_dialog: Any = None
        self._edit_draft: dict[str, Any] | None = None
        self._edit_scheme_id: int | None = None
        self._edit_name_input: Any = None
        self._edit_enabled_keys: list[str] | None = None
        self._edit_selected_key: str | None = None
        self._edit_item_keys: dict[int, str] = {}
        self._edit_item_elements: dict[str, Any] = {}
        self._edit_item_actions: dict[str, Any] = {}
        self._available_column: Any = None
        self._enabled_column: Any = None
        self._edit_editor_panel: Any = None
        self._sort_ignore_click = False
        self._edit_syncing = False
        self._applying = False

    @staticmethod
    def _default_get_user_id() -> int | None:
        """获取当前登录账号 ID。"""
        raw_user_id = app.storage.user.get("user_id")
        if raw_user_id in (None, ""):
            return None
        try:
            user_id = int(raw_user_id)
        except (TypeError, ValueError):
            return None
        return user_id if user_id > 0 else None

    def render_chips(self) -> None:
        """在表格上方创建方案芯片行。"""
        ui.add_css(CHIP_CSS)
        self._chip_row = ui.row().classes(CHIP_ROW_CLASSES)
        self._chip_row.set_visibility(False)
        self._save_dialog = ui.dialog()
        self._ensure_edit_dialog()
        self._redraw_chips()

    def _ensure_edit_dialog(self) -> None:
        """确保方案编辑弹窗已创建。"""
        if self._edit_dialog is not None:
            return
        self._edit_dialog = ui.dialog().props("persistent")
        self._edit_dialog.on("hide", self._clear_edit_session)

    def _clear_edit_session(self, _event: Any = None) -> None:
        """关闭编辑弹窗后丢掉草稿。"""
        self._edit_draft = None
        self._edit_scheme_id = None
        self._edit_name_input = None
        self._edit_enabled_keys = None
        self._edit_selected_key = None
        self._edit_item_keys = {}
        self._edit_item_elements = {}
        self._edit_item_actions = {}
        self._available_column = None
        self._enabled_column = None
        self._edit_editor_panel = None
        self._sort_ignore_click = False
        self._edit_syncing = False

    async def initialize(self) -> None:
        """拉取当前账号的个人方案，不自动套用。"""
        if self._chip_row is None:
            return
        try:
            self.state.schemes = await FilterSchemeService.list_schemes(
                user_id=self.get_user_id(),
                config=self.config,
            )
            self.state.unavailable = False
        except RuntimeError as exc:
            self.state.schemes = []
            self.state.unavailable = True
            ui.notify(str(exc), type="warning")
        self.state.active_scheme_id = self._matching_scheme_id()
        self._redraw_chips()

    def on_filters_changed(self) -> None:
        """筛选变化后同步选中芯片；套用方案过程中忽略。"""
        if self._applying or self.state.unavailable:
            return
        self.state.active_scheme_id = self._matching_scheme_id()
        self._redraw_chips()

    def open_save_dialog(self) -> None:
        """打开保存方案弹窗，先展示当前条件再填写名称。"""
        if self._save_dialog is None:
            self._save_dialog = ui.dialog()
        current_values = self.bindings.get_values()
        items = FilterSchemeService.describe_values(current_values, config=self.config)
        if not items or FilterSchemeService.is_default_values(
            FilterSchemeService.encode_values(current_values, config=self.config),
            config=self.config,
        ):
            ui.notify(EMPTY_SCHEME_ERROR, type="warning")
            return
        clear_element(self._save_dialog)
        with self._save_dialog, ui.card().classes(DIALOG_CARD_CLASSES):
            with ui.column().classes("w-full gap-3 p-6"):
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("保存方案").classes("text-xl font-bold")
                    ui.button(icon="close", on_click=self._save_dialog.close).props("flat round dense")
                ui.label("当前筛选条件").classes("text-sm text-grey-7")
                with ui.column().classes("w-full gap-1"):
                    for label, text in items:
                        ui.label(f"{label}：{text}").classes("text-sm")
                name_input = ui.input("方案名称").props("dense autofocus").classes("w-full")
                with ui.row().classes("w-full justify-end pt-3"):
                    ui.button(
                        "保存",
                        icon="bookmarks",
                        on_click=lambda: self._submit_create(name_input),
                    ).props("rounded unelevated no-caps")
        name_input.on("keydown.enter", lambda: self._submit_create(name_input))
        self._save_dialog.open()

    async def apply_scheme(self, scheme_id: int) -> None:
        """套用指定方案：完整替换当前结构化筛选，不与上一套叠加，不含模糊搜索。"""
        if self._applying:
            return
        scheme = self._find_scheme(scheme_id)
        if scheme is None:
            ui.notify("过滤方案不存在", type="warning")
            return
        self._applying = True
        try:
            widget_values = FilterSchemeService.to_widget_values(scheme.values, config=self.config)
            self.bindings.set_values(widget_values)
            self.state.active_scheme_id = scheme.id
            await self.bindings.refresh()
            self._redraw_chips()
        finally:
            self._applying = False

    def _find_scheme(self, scheme_id: int | None) -> FilterScheme | None:
        """按 ID 查找当前可见方案。"""
        if scheme_id is None:
            return None
        for scheme in self.state.schemes:
            if scheme.id == scheme_id:
                return scheme
        return None

    def _current_stored_values(self) -> dict[str, Any]:
        """读取当前控件并编码为存储形态。"""
        return FilterSchemeService.encode_values(self.bindings.get_values(), config=self.config)

    def _matching_scheme_id(self) -> int | None:
        """当前筛选命中的方案 ID。"""
        current = self._current_stored_values()
        if self.state.active_scheme_id is not None:
            scheme = self._find_scheme(self.state.active_scheme_id)
            if scheme is not None and FilterSchemeService.values_equal(current, scheme.values, config=self.config):
                return scheme.id
        for scheme in self.state.schemes:
            if FilterSchemeService.values_equal(current, scheme.values, config=self.config):
                return scheme.id
        return None

    def _redraw_chips(self) -> None:
        """整表重绘芯片行。"""
        if self._chip_row is None:
            return
        clear_element(self._chip_row)
        schemes = self.state.schemes
        self._chip_row.set_visibility(bool(schemes))
        if not schemes:
            return
        with self._chip_row:
            for scheme in schemes:
                self._render_scheme_chip(scheme)

    def _render_scheme_chip(self, scheme: FilterScheme) -> None:
        """渲染一条个人方案芯片，尾端为编辑图标。未选中为描边。"""
        selected = self.state.active_scheme_id == scheme.id
        chip = ui.chip(
            scheme.name,
            icon="check" if selected else None,
            color="teal",
            text_color="white" if selected else None,
            on_click=self._make_apply_handler(scheme.id),
        ).props("dense" if selected else "dense outline").classes(CHIP_CLASSES)
        with chip:
            ui.icon("edit").classes("cursor-pointer text-base").on(
                "click.stop",
                self._make_edit_handler(scheme.id),
            ).tooltip("编辑方案")

    def _make_apply_handler(self, scheme_id: int) -> Callable[[], Awaitable[None]]:
        """生成套用指定方案的点击回调。"""

        async def _handler() -> None:
            await self.apply_scheme(scheme_id)

        return _handler

    def _make_edit_handler(self, scheme_id: int) -> Callable[[Any], None]:
        """生成打开方案编辑弹窗的点击回调。"""

        def _handler(_event: Any = None) -> None:
            self._open_edit_dialog(scheme_id)

        return _handler

    async def _reload_schemes(self) -> None:
        """重新拉取方案列表并重绘，不改变当前筛选。"""
        try:
            self.state.schemes = await FilterSchemeService.list_schemes(
                user_id=self.get_user_id(),
                config=self.config,
            )
            self.state.unavailable = False
        except RuntimeError as exc:
            self.state.unavailable = True
            ui.notify(str(exc), type="warning")
        self.state.active_scheme_id = self._matching_scheme_id()
        self._redraw_chips()

    def _open_edit_dialog(self, scheme_id: int) -> None:
        """打开方案编辑弹窗：表单改名，拖拽启用字段并点击编辑。"""
        scheme = self._find_scheme(scheme_id)
        if scheme is None:
            ui.notify("过滤方案不存在", type="warning")
            return
        self._ensure_edit_dialog()
        self._edit_scheme_id = scheme.id
        self._edit_draft = dict(scheme.values)
        self._edit_enabled_keys = [
            key for key, _, _ in FilterSchemeService.describe_active_fields(scheme.values, config=self.config)
        ]
        self._edit_selected_key = None
        self._edit_item_keys = {}
        self._edit_item_elements = {}
        self._sort_ignore_click = False
        clear_element(self._edit_dialog)
        with self._edit_dialog, ui.card().classes(EDIT_DIALOG_CARD_CLASSES):
            with ui.column().classes("w-full gap-3 p-6 max-[640px]:p-4"):
                with ui.row().classes("w-full items-start justify-between gap-3"):
                    ui.label("方案编辑").classes("text-xl font-bold")
                    ui.button(icon="close", on_click=self._edit_dialog.close).props("flat round dense")
                self._edit_name_input = ui.input(
                    label="* 方案名称",
                    placeholder="请输入方案名称",
                    value=scheme.name,
                    validation=self._name_validation(),
                ).classes("w-full").props(
                    f"{FORM_FIELD_PROPS} maxlength={self.config.max_name_length}"
                )
                self._render_edit_field_boards()
                with ui.row().classes("w-full items-center justify-between pt-5 mt-1"):
                    ui.button(
                        "删除",
                        icon="delete",
                        color="negative",
                        on_click=self._delete_scheme_from_edit,
                    ).props("rounded unelevated no-caps")
                    ui.button(
                        "保存",
                        icon="save",
                        on_click=self._submit_update,
                    ).props("rounded unelevated no-caps").classes("px-5")
        self._edit_dialog.open()

    def _name_validation(self) -> dict[str, Callable[[Any], bool]]:
        """方案名称表单校验。"""
        max_length = self.config.max_name_length
        return {
            "不能为空": lambda value: bool(str(value or "").strip()),
            f"长度不能超过{max_length}个字符": lambda value: len(str(value or "")) <= max_length,
        }

    def _render_edit_field_boards(self) -> None:
        """同一行：未启用筛选 / 启用筛选 / 编辑条件。字段列表固定高度，超出在卡片内滚动。"""
        enabled_keys = list(self._edit_enabled_keys or [])
        enabled_set = set(enabled_keys)
        available_keys = [item.key for item in self.config.fields if item.key and item.key not in enabled_set]
        with ui.row().classes("w-full gap-3 items-start max-[640px]:flex-col"):
            with ui.card().classes(FIELD_BOARD_CARD_CLASSES):
                ui.label("未启用筛选").classes("w-full text-left font-bold")
                with ui.element("div").classes(SORT_SCROLL_CLASSES):
                    with ui.column().classes(SORT_COLUMN_CLASSES) as available_column:
                        for key in available_keys:
                            self._render_sort_item(key)
            with ui.card().classes(FIELD_BOARD_CARD_CLASSES):
                ui.label("启用筛选").classes("w-full text-left font-bold")
                with ui.element("div").classes(SORT_SCROLL_CLASSES):
                    with ui.column().classes(SORT_COLUMN_CLASSES) as enabled_column:
                        for key in enabled_keys:
                            self._render_sort_item(key)
            with ui.card().classes(EDITOR_BOARD_CARD_CLASSES):
                ui.label("编辑条件").classes("font-bold")
                self._edit_editor_panel = ui.column().classes("w-full gap-2")
        self._available_column = available_column
        self._enabled_column = enabled_column
        available_column.make_sortable(
            group="filter-scheme-fields",
            on_end=self._on_field_sort_end,
            options=SORT_OPTIONS,
        )
        enabled_column.make_sortable(
            group="filter-scheme-fields",
            on_end=self._on_field_sort_end,
            options=SORT_OPTIONS,
        )
        self._redraw_editor_panel()

    def _render_sort_item(self, key: str) -> None:
        """渲染一枚可拖拽字段：未启用为向右箭头，启用为关闭按钮。"""
        enabled = key in (self._edit_enabled_keys or [])
        with ui.row().classes(SORT_ITEM_CLASSES) as item:
            label = ui.label(self._field_label(key)).classes(SORT_ITEM_LABEL_CLASSES)
            action = ui.button(
                icon="close" if enabled else "chevron_right",
                color=None,
            ).props("flat round dense size=xs").classes(SORT_ITEM_ACTION_CLASSES)
        label.on("click", self._make_item_click_handler(key))
        action.on_click(self._make_item_action_handler(key))
        self._edit_item_keys[item.id] = key
        self._edit_item_elements[key] = item
        self._edit_item_actions[key] = action

    def _field_label(self, key: str) -> str:
        """字段展示名。"""
        for item in self.config.fields:
            if item.key == key:
                return item.label
        return key

    def _field_caption(self, key: str, *, enabled: bool) -> str:
        """字段条件文案；列表只显示字段名，编辑区无控件时作回退。"""
        label = self._field_label(key)
        if not enabled:
            return label
        for item_key, _, text in FilterSchemeService.describe_active_fields(
            self._edit_draft or {},
            config=self.config,
        ):
            if item_key == key:
                return f"{label}：{text}"
        return label

    @staticmethod
    def _is_same_element(left: Any, right: Any) -> bool:
        """判断两个 NiceGUI 元素是否为同一控件。"""
        if left is None or right is None:
            return False
        if left is right:
            return True
        left_id = getattr(left, "id", None)
        right_id = getattr(right, "id", None)
        return left_id is not None and left_id == right_id

    def _column_field_keys(self, column: Any) -> list[str]:
        """读取可排序列里当前字段顺序。"""
        if column is None:
            return []
        slot = getattr(column, "default_slot", None)
        children = list(getattr(slot, "children", []) if slot is not None else [])
        keys: list[str] = []
        for child in children:
            child_id = getattr(child, "id", None)
            if not isinstance(child_id, int):
                continue
            key = self._edit_item_keys.get(child_id)
            if key:
                keys.append(key)
        return keys

    def _on_field_sort_end(self, event: SortableEventArguments) -> None:
        """拖拽结束后同步启用字段；移出不丢草稿，移回后仍可编辑原值。"""
        self._sort_ignore_click = True
        self._apply_enabled_keys_change(self._sync_enabled_keys_from_sort(event))

    def _apply_enabled_keys_change(self, enabled_keys: list[str]) -> None:
        """应用启用列表变更：切换箭头/关闭，并处理选中与编辑区。"""
        old_enabled = list(self._edit_enabled_keys or [])
        self._edit_enabled_keys = enabled_keys
        old_set = set(old_enabled)
        new_set = set(enabled_keys)
        removed = [key for key in old_enabled if key not in new_set]
        added = [key for key in enabled_keys if key not in old_set]
        for key in added + removed:
            self._sync_item_action(key)
        if added:
            self._select_enabled_field(added[-1])
            return
        if self._edit_selected_key in removed:
            self._edit_selected_key = None
            self._sync_selected_item_style()
            self._redraw_editor_panel()
            return
        self._sync_selected_item_style()

    def _sync_item_action(self, key: str) -> None:
        """按是否启用切换向右箭头或关闭按钮。"""
        action = self._edit_item_actions.get(key)
        if action is None:
            return
        icon = "close" if key in (self._edit_enabled_keys or []) else "chevron_right"
        action.set_icon(icon)

    def _sync_enabled_keys_from_sort(self, event: SortableEventArguments) -> list[str]:
        """按列内顺序读取启用字段，拖拽结果与列状态不一致时以事件为准。"""
        enabled_keys = self._column_field_keys(self._enabled_column)
        moved_id = getattr(event.item, "id", None)
        moved_key = self._edit_item_keys.get(moved_id) if isinstance(moved_id, int) else None
        if not moved_key:
            return enabled_keys
        target_is_enabled = self._is_same_element(event.target, self._enabled_column)
        source_is_enabled = self._is_same_element(event.source, self._enabled_column)
        if target_is_enabled and moved_key not in enabled_keys:
            index = max(0, min(int(event.new_index), len(enabled_keys)))
            enabled_keys.insert(index, moved_key)
        elif source_is_enabled and not target_is_enabled and moved_key in enabled_keys:
            enabled_keys = [key for key in enabled_keys if key != moved_key]
        return enabled_keys

    def _make_item_click_handler(self, key: str) -> Callable[[Any], None]:
        """生成点击字段的回调：仅启用列打开编辑。"""

        def _handler(_event: Any = None) -> None:
            ignore_click = self._sort_ignore_click
            self._sort_ignore_click = False
            if ignore_click and self._edit_selected_key == key:
                return
            self._select_enabled_field(key)

        return _handler

    def _make_item_action_handler(self, key: str) -> Callable[[Any], None]:
        """生成箭头启用 / 关闭移出的回调。"""

        def _handler(_event: Any = None) -> None:
            self._sort_ignore_click = False
            if key in (self._edit_enabled_keys or []):
                self._disable_field_by_action(key)
            else:
                self._enable_field_by_action(key)

        return _handler

    def _enable_field_by_action(self, key: str) -> None:
        """把未启用字段移入启用筛选并打开编辑。"""
        item = self._edit_item_elements.get(key)
        if item is None or self._enabled_column is None:
            return
        if key in (self._edit_enabled_keys or []):
            self._select_enabled_field(key)
            return
        item.move(target_container=self._enabled_column)
        enabled_keys = list(self._edit_enabled_keys or [])
        enabled_keys.append(key)
        self._apply_enabled_keys_change(enabled_keys)

    def _disable_field_by_action(self, key: str) -> None:
        """把启用字段移回未启用筛选，保留草稿值。"""
        item = self._edit_item_elements.get(key)
        if item is None or self._available_column is None:
            return
        if key not in (self._edit_enabled_keys or []):
            return
        item.move(
            target_container=self._available_column,
            target_index=self._available_insert_index(key),
        )
        enabled_keys = [item_key for item_key in (self._edit_enabled_keys or []) if item_key != key]
        self._apply_enabled_keys_change(enabled_keys)

    def _available_insert_index(self, key: str) -> int:
        """按配置字段顺序，计算放回未启用列的位置。"""
        enabled = {item_key for item_key in (self._edit_enabled_keys or []) if item_key != key}
        config_keys = [item.key for item in self.config.fields if item.key]
        available_now = self._column_field_keys(self._available_column)
        present = set(available_now)
        ordered = [item_key for item_key in config_keys if item_key not in enabled]
        try:
            target = ordered.index(key)
        except ValueError:
            return len(available_now)
        return sum(1 for item_key in ordered[:target] if item_key in present)

    def _select_enabled_field(self, key: str) -> None:
        """选中启用筛选中的字段并打开编辑区。"""
        if key not in (self._edit_enabled_keys or []):
            return
        self._edit_selected_key = key
        self._sync_selected_item_style()
        self._redraw_editor_panel()

    def _sync_selected_item_style(self) -> None:
        """同步启用字段的选中高亮。"""
        selected = self._edit_selected_key
        for key, item in self._edit_item_elements.items():
            if key == selected:
                item.classes(add=SORT_ITEM_SELECTED_CLASS)
            else:
                item.classes(remove=SORT_ITEM_SELECTED_CLASS)

    def _redraw_editor_panel(self) -> None:
        """重绘当前选中字段的编辑控件。"""
        if self._edit_editor_panel is None:
            return
        self._edit_syncing = True
        try:
            clear_element(self._edit_editor_panel)
            key = self._edit_selected_key
            with self._edit_editor_panel:
                if not key or key not in (self._edit_enabled_keys or []):
                    ui.label("点击启用筛选中的字段进行编辑").classes("text-sm text-grey-7")
                    return
                ui.label(self._field_label(key)).classes("text-sm font-medium")
                if self.bindings.render_field_editor is not None:
                    self.bindings.render_field_editor(
                        key,
                        (self._edit_draft or {}).get(key),
                        self._make_field_change_handler(key),
                    )
                else:
                    ui.label(self._field_caption(key, enabled=True)).classes("text-sm")
        finally:
            self._edit_syncing = False

    def _make_field_change_handler(self, key: str) -> Callable[[Any], None]:
        """生成条件控件变更时回写草稿的回调。"""

        def _handler(payload: Any) -> None:
            self._on_field_change(key, payload)

        return _handler

    def _on_field_change(self, key: str, payload: Any) -> None:
        """把单字段快照写入草稿；重绘编辑区时忽略控件初始化事件。"""
        if self._edit_syncing or self._edit_draft is None:
            return
        if payload:
            self._edit_draft[key] = payload
        else:
            self._edit_draft.pop(key, None)

    async def _submit_create(self, name_input: Any) -> None:
        """提交新建方案。"""
        try:
            scheme = await FilterSchemeService.create_scheme(
                user_id=self.get_user_id(),
                config=self.config,
                name=str(name_input.value or ""),
                values=self.bindings.get_values(),
            )
        except ValueError as exc:
            ui.notify(str(exc), type="warning")
            return
        except RuntimeError as exc:
            ui.notify(str(exc), type="warning")
            return
        self.state.active_scheme_id = scheme.id
        ui.notify("已保存方案", type="positive")
        self._save_dialog.close()
        await self._reload_schemes()

    async def _submit_update(self) -> None:
        """提交方案名称与草稿条件。"""
        scheme_id = self._edit_scheme_id
        name_input = self._edit_name_input
        draft = self._edit_draft
        if scheme_id is None or name_input is None or draft is None:
            return
        original = self._find_scheme(scheme_id)
        enabled = set(self._edit_enabled_keys or [])
        values = {key: value for key, value in draft.items() if key in enabled}
        try:
            updated = await FilterSchemeService.update_scheme(
                user_id=self.get_user_id(),
                config=self.config,
                scheme_id=scheme_id,
                name=str(name_input.value or ""),
                values=values,
            )
        except ValueError as exc:
            ui.notify(str(exc), type="warning")
            return
        except RuntimeError as exc:
            ui.notify(str(exc), type="warning")
            return
        was_active = self.state.active_scheme_id == scheme_id
        values_changed = original is None or not FilterSchemeService.values_equal(
            original.values,
            updated.values,
            config=self.config,
        )
        ui.notify("已保存方案", type="positive")
        if self._edit_dialog is not None:
            self._edit_dialog.close()
        if was_active and values_changed:
            self._applying = True
            try:
                widget_values = FilterSchemeService.to_widget_values(updated.values, config=self.config)
                self.bindings.set_values(widget_values)
                self.state.active_scheme_id = updated.id
                await self.bindings.refresh()
            finally:
                self._applying = False
        await self._reload_schemes()

    async def _delete_scheme_from_edit(self) -> None:
        """从编辑弹窗删除当前方案。"""
        scheme = self._find_scheme(self._edit_scheme_id)
        if scheme is None:
            ui.notify("过滤方案不存在", type="warning")
            return
        await self._delete_scheme(scheme)

    async def _delete_scheme(self, scheme: FilterScheme) -> None:
        """删除指定过滤方案。"""
        try:
            await FilterSchemeService.delete_scheme(
                user_id=self.get_user_id(),
                config=self.config,
                scheme_id=scheme.id,
            )
        except ValueError as exc:
            ui.notify(str(exc), type="warning")
            return
        except RuntimeError as exc:
            ui.notify(str(exc), type="warning")
            return
        if self.state.active_scheme_id == scheme.id:
            self.state.active_scheme_id = None
        ui.notify("已删除方案", type="positive")
        if self._edit_dialog is not None:
            self._edit_dialog.close()
        await self._reload_schemes()
