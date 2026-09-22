"""业务域：示例事项页面控制器。"""

from __future__ import annotations

from typing import Any

from nicegui import app, ui

from models import OperationType
from modules.list_page import ListPageFacade
from modules.log_audit import write_user_log
from modules.ui.helpers import clear_element

from .page_forms import ItemFormRefs, build_form_initial, build_item_form, collect_form_data
from .page_table import ITEM_LIST_SPEC, format_item_for_display
from .service import ExampleItemService


class ExamplePageController:
    """示例事项查询、新增、编辑与删除控制器。"""

    def __init__(self) -> None:
        """初始化页面状态，不负责创建具体 UI 组件。"""
        self.list_page = ListPageFacade(spec=ITEM_LIST_SPEC, on_refresh=self.update_table)
        self.add_dialog = None
        self.edit_dialog = None
        self.delete_dialog = None

    async def _render_item_dialog(
        self,
        dialog: Any,
        *,
        title: str,
        on_save: Any,
        initial: dict[str, Any] | None = None,
    ) -> ItemFormRefs:
        """渲染事项弹窗内容。"""
        clear_element(dialog)
        with dialog, ui.card().classes("w-[560px] max-w-[96vw] rounded-2xl shadow-xl"):
            with ui.column().classes("w-full gap-4 p-6"):
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label(title).classes("text-xl font-bold")
                    ui.button(icon="close", on_click=dialog.close).props("flat round dense")
                form = build_item_form(initial=initial)
                with ui.row().classes("w-full justify-end gap-3 pt-2"):
                    ui.button("保存", icon="save", on_click=lambda: on_save(form)).props(
                        "rounded unelevated no-caps"
                    )
        return form

    async def save_new_item(self, form: ItemFormRefs) -> None:
        """保存新增事项。"""
        data = collect_form_data(form)
        try:
            item = await ExampleItemService.create_item(
                title=data.title,
                content=data.content,
                is_done=data.is_done,
            )
        except ValueError as exc:
            ui.notify(str(exc), type="negative")
            return
        except Exception as exc:
            ui.notify(f"创建失败: {exc}", type="negative")
            return
        ui.notify("事项已创建", type="positive")
        await write_user_log(
            user_id=int(app.storage.user.get("user_id") or 0),
            module="示例事项",
            operation_type=OperationType.CREATE,
            action="新增示例事项",
            after_change={"id": int(item.id), "title": item.title},
        )
        self.add_dialog.close()
        await self.update_table()

    async def save_edit_item(self, form: ItemFormRefs, item_id: int) -> None:
        """保存编辑事项。"""
        data = collect_form_data(form)
        try:
            item = await ExampleItemService.update_item(
                item_id=item_id,
                title=data.title,
                content=data.content,
                is_done=data.is_done,
            )
        except ValueError as exc:
            ui.notify(str(exc), type="negative")
            return
        except Exception as exc:
            ui.notify(f"更新失败: {exc}", type="negative")
            return
        ui.notify("事项已更新", type="positive")
        await write_user_log(
            user_id=int(app.storage.user.get("user_id") or 0),
            module="示例事项",
            operation_type=OperationType.UPDATE,
            action="编辑示例事项",
            after_change={"id": int(item.id), "title": item.title, "is_done": item.is_done},
        )
        self.edit_dialog.close()
        await self.update_table()

    async def open_add_dialog(self) -> None:
        """打开新增弹窗。"""
        if not self.add_dialog:
            self.add_dialog = ui.dialog()
        await self._render_item_dialog(
            self.add_dialog,
            title="新增事项",
            on_save=self.save_new_item,
        )
        self.add_dialog.open()

    async def open_edit_dialog(self, row: dict[str, Any]) -> None:
        """打开编辑弹窗。"""
        if not row or not row.get("id"):
            ui.notify("无法获取事项信息", type="negative")
            return
        item_id = int(row["id"])
        detail = await ExampleItemService.get_item(item_id)
        if not detail:
            ui.notify("事项不存在", type="negative")
            return
        if not self.edit_dialog:
            self.edit_dialog = ui.dialog()
        await self._render_item_dialog(
            self.edit_dialog,
            title="编辑事项",
            on_save=lambda form: self.save_edit_item(form, item_id),
            initial=build_form_initial(detail),
        )
        self.edit_dialog.open()

    async def open_delete_dialog(self, row: dict[str, Any]) -> None:
        """打开删除确认弹窗。"""
        if not row or not row.get("id"):
            ui.notify("无法获取事项信息", type="negative")
            return
        if not self.delete_dialog:
            self.delete_dialog = ui.dialog()
        title = str(row.get("title") or "")
        item_id = int(row["id"])
        clear_element(self.delete_dialog)
        with self.delete_dialog, ui.card().classes("w-[420px] max-w-[96vw] rounded-2xl"):
            with ui.column().classes("w-full gap-4 p-6"):
                ui.label("删除示例事项").classes("text-xl font-bold")
                ui.label(f"确定删除「{title}」？此操作不可恢复。").classes("text-sm")
                with ui.row().classes("w-full justify-end gap-2"):
                    ui.button("取消", on_click=self.delete_dialog.close).props("flat rounded")
                    ui.button(
                        "删除",
                        color="negative",
                        on_click=lambda: self.delete_item(item_id),
                    ).props("unelevated rounded")
        self.delete_dialog.open()

    async def delete_item(self, item_id: int) -> None:
        """删除事项并刷新表格。"""
        try:
            await ExampleItemService.delete_item(item_id)
        except ValueError as exc:
            ui.notify(str(exc), type="negative")
            return
        except Exception as exc:
            ui.notify(f"删除失败: {exc}", type="negative")
            return
        ui.notify("事项已删除", type="positive")
        await write_user_log(
            user_id=int(app.storage.user.get("user_id") or 0),
            module="示例事项",
            operation_type=OperationType.DELETE,
            action="删除示例事项",
            after_change={"id": item_id},
        )
        if self.delete_dialog:
            self.delete_dialog.close()
        await self.update_table()

    async def update_table(self) -> None:
        """刷新表格与分页。"""
        if not self.list_page.is_mounted:
            return
        current_page, page_size = self.list_page.page_and_size()
        try:
            result = await ExampleItemService.search_items(
                page=current_page,
                page_size=page_size,
                keyword=self.list_page.search_state.keyword,
                **self.list_page.filter_kwargs(),
            )
        except Exception as exc:
            ui.notify(f"加载失败: {exc}。若刚启用本域，请先执行数据库迁移。", type="negative")
            return
        await write_user_log(
            user_id=int(app.storage.user.get("user_id") or 0),
            module="示例事项",
            operation_type=OperationType.READ,
            action="查询示例事项",
            note={"keyword": self.list_page.search_state.keyword},
        )
        items = result.get("items", [])
        self.list_page.apply_items(
            items if isinstance(items, list) else [],
            total=int(result.get("total", 0)),
            row_mapper=format_item_for_display,
        )
