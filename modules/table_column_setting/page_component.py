"""系统能力：表格列显示偏好的页面触发组件。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from nicegui import app, ui

from modules.table_column_setting.service import TableColumnSettingConfig, TableColumnSettingService


def apply_table_visible_columns(table: Any, column_names: Iterable[str] | None) -> None:
    """将列显示状态应用到指定表格。"""
    visible_column_name_set = set(column_names or [])
    for column in table.columns:
        column_name = str(column.get("name") or "").strip()
        is_visible = column_name in visible_column_name_set
        column["classes"] = "" if is_visible else "hidden"
        column["headerClasses"] = "" if is_visible else "hidden"
    table.update()


@dataclass
class TableColumnSettingState:
    """表格列显示状态。"""

    visible_column_names: list[str]
    is_saving: bool = False


class TableColumnSettingController:
    """表格列显示偏好控制器。"""

    def __init__(
            self,
            *,
            config: TableColumnSettingConfig,
            columns: list[dict[str, Any]],
            get_tables: Callable[[], list[Any | None]],
            get_user_id: Callable[[], int | None] | None = None,
    ) -> None:
        self.config = config
        self.columns = columns
        self.get_tables = get_tables
        self.get_user_id = get_user_id or self._default_get_user_id
        self.state = TableColumnSettingState(
            visible_column_names=TableColumnSettingService.normalize_visible_column_names(
                config.default_visible_column_names,
                config=config,
            )
        )

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

    def get_optional_column_options(self) -> list[dict[str, str]]:
        """返回可配置业务列选项。"""
        return [
            {
                "name": str(column["name"]),
                "label": str(column["label"]),
            }
            for column in self.columns
            if str(column["name"]) not in self.config.required_column_names
        ]

    def get_visible_optional_column_names(self) -> list[str]:
        """返回当前已勾选的业务列编码。"""
        return [
            name
            for name in self.state.visible_column_names
            if name not in self.config.required_column_names
        ]

    async def initialize(self) -> None:
        """初始化当前账号的列显示偏好。"""
        self.state.visible_column_names = await TableColumnSettingService.get_user_visible_column_names(
            user_id=self.get_user_id(),
            config=self.config,
        )

    def apply_visible_columns(self) -> None:
        """将当前列偏好应用到页面中的所有表格。"""
        for table in self.get_tables():
            if table is None:
                continue
            apply_table_visible_columns(table, self.state.visible_column_names)

    def _sort_optional_column_names(self, column_names: list[str]) -> list[str]:
        """按默认列顺序稳定排序业务列。"""
        order_index = {
            column_name: index
            for index, column_name in enumerate(
                TableColumnSettingService.normalize_visible_column_names(
                    self.config.default_visible_column_names,
                    config=self.config,
                )
            )
        }
        return sorted(column_names, key=lambda column_name: order_index.get(column_name, len(order_index)))

    def _update_visible_column_names(self, *, column_name: str, visible: bool) -> None:
        """更新当前列显示状态。"""
        optional_column_names = self.get_visible_optional_column_names()
        if visible:
            if column_name not in optional_column_names:
                optional_column_names.append(column_name)
        else:
            optional_column_names = [name for name in optional_column_names if name != column_name]

        self.state.visible_column_names = list(self.config.required_column_names) + self._sort_optional_column_names(
            optional_column_names
        )

    async def save_preferences(self) -> None:
        """保存当前列显示偏好。"""
        if self.state.is_saving:
            return

        self.state.is_saving = True
        try:
            self.state.visible_column_names = await TableColumnSettingService.save_user_visible_column_names(
                user_id=self.get_user_id(),
                visible_column_names=self.state.visible_column_names,
                config=self.config,
            )
            self.apply_visible_columns()
        except ValueError as exc:
            ui.notify(str(exc), type="warning")
        except RuntimeError as exc:
            ui.notify(str(exc), type="warning")
        finally:
            self.state.is_saving = False

    async def handle_column_visibility_change(self, *, column_name: str, visible: bool) -> None:
        """处理列显示状态切换并自动保存。"""
        self._update_visible_column_names(column_name=column_name, visible=visible)
        self.apply_visible_columns()
        await self.save_preferences()

    def render_trigger(self) -> None:
        """在分页区域左侧渲染列设置入口。"""
        with ui.button(icon="menu").props("flat round dense"):
            ui.tooltip("显示/隐藏列")
            with ui.menu(), ui.column().classes("gap-0 p-2"):
                for column_option in self.get_optional_column_options():
                    ui.switch(
                        column_option["label"],
                        value=column_option["name"] in self.get_visible_optional_column_names(),
                        on_change=lambda event, column_name=column_option["name"]: self.handle_column_visibility_change(
                            column_name=column_name,
                            visible=bool(event.value),
                        ),
                    ).props("dense")
