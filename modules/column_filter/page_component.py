"""系统能力：列头筛选的触发器、弹窗与芯片。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from inspect import isawaitable
from typing import Any

from nicegui import ui

from modules.ui.helpers import clear_element

from .service import (
    DATE_SHORTCUTS,
    ColumnFilterSpec,
    ColumnFilterValue,
    active_column_filters,
    app_today,
    date_range_for_shortcut,
    dump_column_filter_value,
    match_date_shortcut,
    parse_column_filter_value,
    parse_iso_date,
    resolved_date_range,
    selected_value_for_spec,
)

CHIP_ROW_CLASSES = "w-full items-center gap-2 flex-wrap min-h-0 mt-2"
CHIP_CLASSES = "ng-column-filter-chip max-w-72"
DIALOG_CARD_CLASSES = "w-[26rem] max-w-[90vw] p-3 gap-2"
DIALOG_DATE_CARD_CLASSES = "w-[19.5rem] max-w-[90vw] p-3 gap-1"
DIALOG_NUMBER_CARD_CLASSES = "w-80 max-w-[90vw] p-3 gap-2"
DIALOG_SELECT_CARD_CLASSES = "w-80 max-w-[90vw] p-3 gap-2"
DATE_EMPTY_RADIO = "empty"
DATE_EMPTY_LABEL = "筛选空值"
HEADER_SLOT = """
<q-th :props="props" class="ng-column-filter-th">
  <span class="ng-column-filter-label" @click.stop="$parent.$emit('open-column-filter', props.col.name)">{{ props.col.label }}</span>
  <q-icon
    name="search"
    size="14px"
    class="q-ml-xs"
    :class="props.col.filter_active ? 'text-primary ng-column-filter-active' : 'text-grey-6 ng-column-filter-trigger'"
    @click.stop="$parent.$emit('open-column-filter', props.col.name)"
  />
</q-th>
"""
COLUMN_FILTER_CSS = """
.q-table th.ng-column-filter-th {
    white-space: nowrap;
    user-select: none;
}
.q-table th.ng-column-filter-th .ng-column-filter-label {
    cursor: pointer;
    vertical-align: middle;
}
.q-table th .ng-column-filter-trigger {
    opacity: 0;
    transition: opacity 0.12s ease;
    vertical-align: middle;
}
.q-table th:hover .ng-column-filter-trigger,
.q-table th .ng-column-filter-active {
    opacity: 1;
    vertical-align: middle;
    cursor: pointer;
}
.ng-column-filter-chip.q-chip,
.ng-column-filter-chip .q-chip__content,
.ng-column-filter-chip .q-icon {
    color: #fff !important;
}
.ng-column-filter-date.q-date {
    box-shadow: none;
    width: 100%;
    min-width: 0;
}
.ng-column-filter-date .q-date__view {
    min-height: 0;
    padding: 8px 8px 0;
}
.ng-column-filter-date .q-date__calendar-days-container {
    height: auto;
    min-height: 0;
}
.ng-column-filter-shortcuts.q-option-group {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    column-gap: 4px;
    row-gap: 0;
    margin: 0;
}
.ng-column-filter-shortcuts.q-option-group > div {
    margin: 0;
    padding: 0;
}
.ng-column-filter-shortcuts .q-radio {
    margin: 0;
    padding: 0;
    min-height: 1.75rem;
}
"""


class ColumnFilterController:
    """列头筛选：弹窗、芯片与表头图标。"""

    def __init__(
        self,
        *,
        specs: Sequence[ColumnFilterSpec],
        on_apply: Callable[[], Awaitable[None] | None] | None = None,
    ) -> None:
        self.specs = [spec for spec in specs if spec.name]
        self.on_apply = on_apply
        self.values: dict[str, ColumnFilterValue] = {}
        self._spec_by_name = {spec.name: spec for spec in self.specs}
        self._table: Any = None
        self._chip_row: Any = None
        self._dialog: Any = None
        self._focus_input: Any = None
        self._committing = False
        self._show_chips = True

    def active_values(self) -> dict[str, ColumnFilterValue]:
        """当前生效的列筛选。"""
        return active_column_filters(self.values)

    def dump_values(self) -> dict[str, Any]:
        """可序列化的列筛选取值，仅含生效条件。"""
        dumped: dict[str, Any] = {}
        for name, value in self.active_values().items():
            payload = dump_column_filter_value(value, spec=self._spec_by_name.get(name))
            if payload is not None:
                dumped[name] = payload
        return dumped

    def replace_values(self, raw: Mapping[str, Any] | None) -> None:
        """用快照完整替换当前列筛选，未出现或未生效的列一律清除，并展示芯片，不触发 on_apply。"""
        next_values: dict[str, ColumnFilterValue] = {}
        for name, payload in dict(raw or {}).items():
            key = str(name or "").strip()
            if key not in self._spec_by_name:
                continue
            value = parse_column_filter_value(payload)
            if value.is_active():
                next_values[key] = value
        self.values = next_values
        self._show_chips = True
        self._redraw_chips()
        self.sync_header_state()

    def set_show_chips(self, visible: bool) -> None:
        """控制列筛选芯片是否展示。"""
        self._show_chips = bool(visible)
        self._redraw_chips()

    def render_chips(self) -> None:
        """在表格上方渲染芯片行，并准备弹窗。"""
        ui.add_css(COLUMN_FILTER_CSS)
        self._ensure_dialog()
        self._chip_row = ui.row().classes(CHIP_ROW_CLASSES)
        self._redraw_chips()

    def attach(self, table: Any) -> None:
        """给可筛列挂表头触发器。"""
        self._table = table
        self._ensure_dialog()
        if table is None:
            return
        table.columns = [dict(column) for column in list(table.columns or [])]
        for spec in self.specs:
            table.add_slot(f"header-cell-{spec.name}", HEADER_SLOT)
        table.on("open-column-filter", self._on_open_event)
        self.sync_header_state()

    def sync_header_state(self) -> None:
        """把生效列同步到表头图标高亮。"""
        if self._table is None:
            return
        active_names = set(self.active_values())
        for column in self._table.columns:
            name = str(column.get("name") or "")
            spec = self._spec_by_name.get(name)
            if spec is None:
                continue
            column["filter_active"] = name in active_names
        self._table.update()

    def _ensure_dialog(self) -> None:
        """确保筛选弹窗已创建。"""
        if self._dialog is not None:
            return
        self._dialog = ui.dialog()
        self._dialog.on("show", self._on_dialog_show)

    def _on_dialog_show(self, _event: Any = None) -> None:
        """弹窗显示后再把焦点放到输入框，避免被表头点击抢走。"""
        target = self._focus_input
        if target is None:
            return

        def focus_keyword_input() -> None:
            target.run_method("focus")
            if str(getattr(target, "value", "") or "").strip():
                target.run_method("select")

        ui.timer(0.05, focus_keyword_input, once=True)

    def _on_open_event(self, event_args: Any) -> None:
        """处理表头点击，打开对应列的筛选弹窗。"""
        self._open(_column_name_from_event(event_args))

    def _open(self, column_name: str) -> None:
        """打开指定列的筛选弹窗。"""
        spec = self._spec_by_name.get(str(column_name or "").strip())
        if spec is None or self._dialog is None:
            return
        current = self.values.get(spec.name, ColumnFilterValue()).normalized()
        clear_element(self._dialog)
        if spec.is_date():
            self._render_date_dialog(spec, current)
        elif spec.is_number():
            self._render_number_dialog(spec, current)
        elif spec.is_select():
            self._render_select_dialog(spec, current)
        else:
            self._render_string_dialog(spec, current)
        self._dialog.open()

    def render_field_editor(
        self,
        name: str,
        raw: Any,
        on_change: Callable[[Any], None],
    ) -> None:
        """在当前 UI 上下文渲染一列筛选控件，变更时回写快照，不改表格。"""
        spec = self._spec_by_name.get(str(name or "").strip())
        if spec is None:
            ui.label("无法编辑该条件").classes("text-sm text-grey-7")
            return
        ui.add_css(COLUMN_FILTER_CSS)
        current = parse_column_filter_value(raw).normalized()

        def emit(value: ColumnFilterValue) -> None:
            on_change(dump_column_filter_value(value, spec=spec))

        if spec.is_date():
            self._render_inline_date_editor(current, emit)
        elif spec.is_number():
            self._render_inline_number_editor(current, emit)
        elif spec.is_select():
            self._render_inline_select_editor(spec, current, emit)
        else:
            self._render_inline_string_editor(spec, current, emit)

    def _render_string_dialog(self, spec: ColumnFilterSpec, current: ColumnFilterValue) -> None:
        """渲染字符串列筛选弹窗：多关键词空格分隔，与空值互斥。"""
        with self._dialog, ui.card().classes(DIALOG_CARD_CLASSES):
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                keyword_input = ui.input(
                    placeholder=spec.input_placeholder(),
                    value="" if current.empty else current.keyword,
                ).classes("min-w-0 flex-1").props("dense autocomplete=off hide-bottom-space autofocus")
                confirm_button = ui.button("确定").props("unelevated no-caps dense")
            empty_checkbox = ui.checkbox("筛选空值", value=current.empty)

            def on_empty_change(event: Any) -> None:
                if bool(getattr(event, "value", False)):
                    keyword_input.value = ""

            def on_keyword_change(event: Any) -> None:
                if str(getattr(event, "value", "") or "").strip():
                    empty_checkbox.value = False

            async def confirm(_=None) -> None:
                value = ColumnFilterValue(
                    keyword=str(keyword_input.value or ""),
                    empty=bool(empty_checkbox.value),
                )
                self._dialog.close()
                await self._commit(spec.name, value)

            empty_checkbox.on_value_change(on_empty_change)
            keyword_input.on_value_change(on_keyword_change)
            keyword_input.on("keydown.enter", confirm)
            confirm_button.on_click(confirm)
        self._focus_input = keyword_input

    def _render_select_dialog(self, spec: ColumnFilterSpec, current: ColumnFilterValue) -> None:
        """渲染选择列筛选弹窗：下拉多选，与空值互斥。布尔与枚举共用。"""
        option_map = spec.option_map()
        current_selected = (
            []
            if current.empty
            else [key for key in current.selected if key in option_map]
        )
        with self._dialog, ui.card().classes(DIALOG_SELECT_CARD_CLASSES):
            ui.label(spec.label).classes("text-sm font-medium")
            with ui.row().classes("w-full items-start gap-2 no-wrap"):
                select_props = "dense use-chips clearable options-dense hide-bottom-space"
                if len(option_map) > 8:
                    select_props += " use-input input-debounce=0"
                select_input = ui.select(
                    option_map,
                    value=current_selected,
                    multiple=True,
                ).classes("min-w-0 flex-1").props(select_props)
                confirm_button = ui.button("确定").props("unelevated no-caps dense")
            empty_checkbox = ui.checkbox("筛选空值", value=current.empty)

            def _selected_keys() -> list[str]:
                raw = select_input.value
                if raw is None or raw == "":
                    return []
                items = raw if isinstance(raw, (list, tuple)) else [raw]
                keys: list[str] = []
                seen: set[str] = set()
                for item in items:
                    key = str(item or "").strip()
                    if not key or key in seen or key not in option_map:
                        continue
                    seen.add(key)
                    keys.append(key)
                return keys

            def on_empty_change(event: Any) -> None:
                if bool(getattr(event, "value", False)):
                    select_input.value = []

            def on_select_change(_event: Any = None) -> None:
                if _selected_keys():
                    empty_checkbox.value = False

            async def confirm(_=None) -> None:
                if bool(empty_checkbox.value):
                    value = ColumnFilterValue(empty=True)
                else:
                    value = selected_value_for_spec(spec, _selected_keys())
                self._dialog.close()
                await self._commit(spec.name, value)

            empty_checkbox.on_value_change(on_empty_change)
            select_input.on_value_change(on_select_change)
            confirm_button.on_click(confirm)
        self._focus_input = None

    def _render_number_dialog(self, spec: ColumnFilterSpec, current: ColumnFilterValue) -> None:
        """渲染数字列筛选弹窗：标题标明列名范围，输入框用 ≥ / ≤ 前缀，缺一端不限，与空值互斥。"""
        with self._dialog, ui.card().classes(DIALOG_NUMBER_CARD_CLASSES):
            ui.label(f"{spec.label}范围").classes("text-sm font-medium")
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                min_input = ui.input(
                    value="" if current.empty else current.start,
                ).classes("min-w-0 flex-1").props(
                    "dense type=number step=any prefix=≥ autocomplete=off hide-bottom-space autofocus"
                )
                ui.label("—").classes("text-grey-6")
                max_input = ui.input(
                    value="" if current.empty else current.end,
                ).classes("min-w-0 flex-1").props(
                    "dense type=number step=any prefix=≤ autocomplete=off hide-bottom-space"
                )
                confirm_button = ui.button("确定").props("unelevated no-caps dense")
            empty_checkbox = ui.checkbox("筛选空值", value=current.empty)

            def _has_number_input() -> bool:
                return bool(str(min_input.value or "").strip() or str(max_input.value or "").strip())

            def on_empty_change(event: Any) -> None:
                if bool(getattr(event, "value", False)):
                    min_input.value = ""
                    max_input.value = ""

            def on_bound_change(_event: Any = None) -> None:
                if _has_number_input():
                    empty_checkbox.value = False

            async def confirm(_=None) -> None:
                if bool(empty_checkbox.value):
                    value = ColumnFilterValue(empty=True)
                else:
                    value = ColumnFilterValue(
                        start=str(min_input.value or ""),
                        end=str(max_input.value or ""),
                    )
                self._dialog.close()
                await self._commit(spec.name, value)

            empty_checkbox.on_value_change(on_empty_change)
            min_input.on_value_change(on_bound_change)
            max_input.on_value_change(on_bound_change)
            min_input.on("keydown.enter", confirm)
            max_input.on("keydown.enter", confirm)
            confirm_button.on_click(confirm)
        self._focus_input = min_input

    def _render_date_dialog(self, spec: ColumnFilterSpec, current: ColumnFilterValue) -> None:
        """渲染日期列筛选弹窗：范围日历、快捷单选与空值。"""
        today = app_today()
        picker_value: dict[str, str] | None = None
        if current.empty:
            active_shortcut = DATE_EMPTY_RADIO
        else:
            start, end = resolved_date_range(current, today=today)
            active_shortcut = current.shortcut
            if not active_shortcut and start is not None and end is not None:
                active_shortcut = match_date_shortcut(start, end, today=today)
            if start is not None and end is not None:
                picker_value = {"from": start.isoformat(), "to": end.isoformat()}
        shortcut_options = {key: label for key, label in DATE_SHORTCUTS}
        shortcut_options[DATE_EMPTY_RADIO] = DATE_EMPTY_LABEL
        syncing = {"on": False}

        with self._dialog, ui.card().classes(DIALOG_DATE_CARD_CLASSES):
            date_picker = ui.date(value=picker_value).props("range flat").classes("w-full ng-column-filter-date")
            shortcut_radio = ui.radio(
                shortcut_options,
                value=active_shortcut or None,
            ).props("dense").classes("w-full ng-column-filter-shortcuts")
            with ui.row().classes("w-full justify-end"):
                confirm_button = ui.button("确定").props("unelevated no-caps dense")

            def apply_shortcut(key: str) -> None:
                syncing["on"] = True
                try:
                    shortcut_radio.value = key
                    if key == DATE_EMPTY_RADIO:
                        date_picker.value = None
                        return
                    bounds = date_range_for_shortcut(key, today=today)
                    if bounds is None:
                        return
                    range_start, range_end = bounds
                    date_picker.value = {"from": range_start.isoformat(), "to": range_end.isoformat()}
                finally:
                    syncing["on"] = False

            def on_shortcut_change(event: Any) -> None:
                if syncing["on"]:
                    return
                key = str(getattr(event, "value", "") or "").strip()
                if key:
                    apply_shortcut(key)
                    return
                syncing["on"] = True
                try:
                    date_picker.value = None
                finally:
                    syncing["on"] = False

            def on_date_change(event: Any) -> None:
                if syncing["on"]:
                    return
                start_text, end_text = _parse_date_picker_value(getattr(event, "value", None))
                start_day = parse_iso_date(start_text)
                end_day = parse_iso_date(end_text)
                matched = ""
                if start_day is not None and end_day is not None:
                    matched = match_date_shortcut(start_day, end_day, today=today)
                syncing["on"] = True
                try:
                    shortcut_radio.value = matched or None
                finally:
                    syncing["on"] = False

            async def confirm(_=None) -> None:
                selected = str(shortcut_radio.value or "").strip()
                if selected == DATE_EMPTY_RADIO:
                    value = ColumnFilterValue(empty=True)
                elif selected:
                    value = ColumnFilterValue(shortcut=selected)
                else:
                    start_text, end_text = _parse_date_picker_value(date_picker.value)
                    value = ColumnFilterValue(start=start_text, end=end_text)
                self._dialog.close()
                await self._commit(spec.name, value)

            shortcut_radio.on_value_change(on_shortcut_change)
            date_picker.on_value_change(on_date_change)
            confirm_button.on_click(confirm)
        self._focus_input = None

    def _render_inline_string_editor(
        self,
        spec: ColumnFilterSpec,
        current: ColumnFilterValue,
        emit: Callable[[ColumnFilterValue], None],
    ) -> None:
        """内联字符串筛选：关键词与空值互斥。"""
        keyword_input = ui.input(
            placeholder=str(spec.placeholder or "").strip() or "多个关键词用空格分隔",
            value="" if current.empty else current.keyword,
        ).classes("w-full").props("dense autocomplete=off hide-bottom-space")
        empty_checkbox = ui.checkbox("筛选空值", value=current.empty)

        def emit_current() -> None:
            emit(
                ColumnFilterValue(
                    keyword=str(keyword_input.value or ""),
                    empty=bool(empty_checkbox.value),
                )
            )

        def on_empty_change(event: Any) -> None:
            if bool(getattr(event, "value", False)):
                keyword_input.value = ""
            emit_current()

        def on_keyword_change(event: Any) -> None:
            if str(getattr(event, "value", "") or "").strip():
                empty_checkbox.value = False
            emit_current()

        empty_checkbox.on_value_change(on_empty_change)
        keyword_input.on_value_change(on_keyword_change)

    def _render_inline_select_editor(
        self,
        spec: ColumnFilterSpec,
        current: ColumnFilterValue,
        emit: Callable[[ColumnFilterValue], None],
    ) -> None:
        """内联选择筛选：下拉多选与空值互斥。"""
        option_map = spec.option_map()
        current_selected = [] if current.empty else [key for key in current.selected if key in option_map]
        select_props = "dense use-chips clearable options-dense hide-bottom-space"
        if len(option_map) > 8:
            select_props += " use-input input-debounce=0"
        select_input = ui.select(
            option_map,
            value=current_selected,
            multiple=True,
        ).classes("w-full").props(select_props)
        empty_checkbox = ui.checkbox("筛选空值", value=current.empty)

        def selected_keys() -> list[str]:
            raw = select_input.value
            if raw is None or raw == "":
                return []
            items = raw if isinstance(raw, (list, tuple)) else [raw]
            keys: list[str] = []
            seen: set[str] = set()
            for item in items:
                key = str(item or "").strip()
                if not key or key in seen or key not in option_map:
                    continue
                seen.add(key)
                keys.append(key)
            return keys

        def emit_current() -> None:
            if bool(empty_checkbox.value):
                emit(ColumnFilterValue(empty=True))
            else:
                emit(selected_value_for_spec(spec, selected_keys()))

        def on_empty_change(event: Any) -> None:
            if bool(getattr(event, "value", False)):
                select_input.value = []
            emit_current()

        def on_select_change(_event: Any = None) -> None:
            if selected_keys():
                empty_checkbox.value = False
            emit_current()

        empty_checkbox.on_value_change(on_empty_change)
        select_input.on_value_change(on_select_change)

    def _render_inline_number_editor(
        self,
        current: ColumnFilterValue,
        emit: Callable[[ColumnFilterValue], None],
    ) -> None:
        """内联数字筛选：闭区间与空值互斥。"""
        with ui.row().classes("w-full items-center gap-2 no-wrap"):
            min_input = ui.input(
                value="" if current.empty else current.start,
            ).classes("min-w-0 flex-1").props(
                "dense type=number step=any prefix=≥ autocomplete=off hide-bottom-space"
            )
            ui.label("—").classes("text-grey-6")
            max_input = ui.input(
                value="" if current.empty else current.end,
            ).classes("min-w-0 flex-1").props(
                "dense type=number step=any prefix=≤ autocomplete=off hide-bottom-space"
            )
        empty_checkbox = ui.checkbox("筛选空值", value=current.empty)

        def has_number_input() -> bool:
            return bool(str(min_input.value or "").strip() or str(max_input.value or "").strip())

        def emit_current() -> None:
            if bool(empty_checkbox.value):
                emit(ColumnFilterValue(empty=True))
            else:
                emit(
                    ColumnFilterValue(
                        start=str(min_input.value or ""),
                        end=str(max_input.value or ""),
                    )
                )

        def on_empty_change(event: Any) -> None:
            if bool(getattr(event, "value", False)):
                min_input.value = ""
                max_input.value = ""
            emit_current()

        def on_bound_change(_event: Any = None) -> None:
            if has_number_input():
                empty_checkbox.value = False
            emit_current()

        empty_checkbox.on_value_change(on_empty_change)
        min_input.on_value_change(on_bound_change)
        max_input.on_value_change(on_bound_change)

    def _render_inline_date_editor(
        self,
        current: ColumnFilterValue,
        emit: Callable[[ColumnFilterValue], None],
    ) -> None:
        """内联日期筛选：快捷单选、起止日期与空值。"""
        today = app_today()
        start_text = ""
        end_text = ""
        if current.empty:
            active_shortcut = DATE_EMPTY_RADIO
        else:
            start, end = resolved_date_range(current, today=today)
            active_shortcut = current.shortcut
            if not active_shortcut and start is not None and end is not None:
                active_shortcut = match_date_shortcut(start, end, today=today)
            if start is not None:
                start_text = start.isoformat()
            if end is not None:
                end_text = end.isoformat()
        shortcut_options = {key: label for key, label in DATE_SHORTCUTS}
        shortcut_options[DATE_EMPTY_RADIO] = DATE_EMPTY_LABEL
        syncing = {"on": False}
        shortcut_radio = ui.radio(
            shortcut_options,
            value=active_shortcut or None,
        ).props("dense").classes("w-full ng-column-filter-shortcuts")
        with ui.row().classes("w-full items-center gap-2 no-wrap"):
            start_input = ui.input(value=start_text).classes("min-w-0 flex-1").props(
                "dense type=date hide-bottom-space"
            )
            ui.label("—").classes("text-grey-6")
            end_input = ui.input(value=end_text).classes("min-w-0 flex-1").props(
                "dense type=date hide-bottom-space"
            )

        def emit_current() -> None:
            selected = str(shortcut_radio.value or "").strip()
            if selected == DATE_EMPTY_RADIO:
                emit(ColumnFilterValue(empty=True))
            elif selected:
                emit(ColumnFilterValue(shortcut=selected))
            else:
                emit(
                    ColumnFilterValue(
                        start=str(start_input.value or "").strip(),
                        end=str(end_input.value or "").strip(),
                    )
                )

        def apply_shortcut(key: str) -> None:
            syncing["on"] = True
            try:
                shortcut_radio.value = key
                if key == DATE_EMPTY_RADIO:
                    start_input.value = ""
                    end_input.value = ""
                    return
                bounds = date_range_for_shortcut(key, today=today)
                if bounds is None:
                    return
                range_start, range_end = bounds
                start_input.value = range_start.isoformat()
                end_input.value = range_end.isoformat()
            finally:
                syncing["on"] = False

        def on_shortcut_change(event: Any) -> None:
            if syncing["on"]:
                return
            key = str(getattr(event, "value", "") or "").strip()
            if key:
                apply_shortcut(key)
            else:
                syncing["on"] = True
                try:
                    start_input.value = ""
                    end_input.value = ""
                finally:
                    syncing["on"] = False
            emit_current()

        def on_date_change(_event: Any = None) -> None:
            if syncing["on"]:
                return
            start_day = parse_iso_date(str(start_input.value or "").strip())
            end_day = parse_iso_date(str(end_input.value or "").strip())
            matched = ""
            if start_day is not None and end_day is not None:
                matched = match_date_shortcut(start_day, end_day, today=today)
            syncing["on"] = True
            try:
                shortcut_radio.value = matched or None
            finally:
                syncing["on"] = False
            emit_current()

        shortcut_radio.on_value_change(on_shortcut_change)
        start_input.on_value_change(on_date_change)
        end_input.on_value_change(on_date_change)

    async def _commit(self, name: str, value: ColumnFilterValue) -> None:
        """写入一列筛选并刷新列表。"""
        if self._committing:
            return
        self._committing = True
        try:
            normalized = value.normalized()
            if normalized.is_active():
                self.values[name] = normalized
            else:
                self.values.pop(name, None)
            self._redraw_chips()
            self.sync_header_state()
            if self.on_apply is None:
                return
            result = self.on_apply()
            if isawaitable(result):
                await result
        finally:
            self._committing = False

    def _redraw_chips(self) -> None:
        """按当前生效条件重绘芯片。"""
        if self._chip_row is None:
            return
        clear_element(self._chip_row)
        items: list[tuple[ColumnFilterSpec, ColumnFilterValue]] = []
        for spec in self.specs:
            value = self.values.get(spec.name)
            if value is None or not value.is_active():
                continue
            items.append((spec, value.normalized()))
        visible = bool(items) and self._show_chips
        self._chip_row.set_visibility(visible)
        if not visible:
            return
        with self._chip_row:
            for spec, value in items:
                ui.chip(
                    f"{spec.label}: {value.chip_text(spec)}",
                    color="secondary",
                    text_color="white",
                    removable=True,
                    on_value_change=self._make_remove_handler(spec.name),
                ).props("dense").classes(CHIP_CLASSES)

    def _make_remove_handler(self, name: str) -> Callable[[Any], Awaitable[None]]:
        """生成芯片关闭按钮的回调。"""

        async def _handler(event: Any) -> None:
            if bool(getattr(event, "value", True)):
                return
            await self._commit(name, ColumnFilterValue())

        return _handler


def _parse_date_picker_value(raw: Any) -> tuple[str, str]:
    """从范围日期控件取值。"""
    if isinstance(raw, dict):
        start = str(raw.get("from") or "").strip()
        end = str(raw.get("to") or start).strip()
        return start, end
    text = str(raw or "").strip()
    if parse_iso_date(text) is not None:
        return text, text
    return "", ""


def _column_name_from_event(event_args: Any) -> str:
    """从表格自定义事件中读取列名。"""
    raw = event_args.args if hasattr(event_args, "args") else event_args
    if isinstance(raw, (list, tuple)) and raw:
        raw = raw[0]
    if isinstance(raw, dict):
        raw = raw.get("name")
    return str(raw or "").strip()
