"""通用附件展示组件。

本模块独立负责图片灯箱、PDF 新标签预览和普通文件下载。
附件来源既可以是页面内存字节，也可以是业务接口或 OSS 提供的 URL。
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from inspect import isawaitable
from typing import Any

from nicegui import events, ui

from modules.ui.attachment_types import (
    AttachmentItem,
    build_attachment_data_url,
    format_attachment_size,
    get_attachment_download_source,
    get_attachment_icon,
    get_attachment_preview_source,
    get_attachment_thumbnail_source,
    is_image_attachment,
    is_pdf_attachment,
)
from modules.ui.helpers import clear_element, render_section_title

__all__ = ["AttachmentDisplay", "AttachmentItem", "build_attachment_display"]

ATTACHMENT_DISPLAY_CSS = """
.attachment-focus-target:focus {
    border-color: var(--q-primary) !important;
    box-shadow: 0 0 0 2px var(--q-primary) !important;
    outline: none !important;
}
.ng-lightbox-card,
body:not(.body--dark) .ng-lightbox-card,
body:not(.body--dark) .q-dialog__inner > .ng-lightbox-card {
    background-color: #080b12 !important;
    background-image: none !important;
    border: none !important;
    box-shadow: none !important;
    color: #f8fafc !important;
}
.ng-lightbox-card .q-btn,
.ng-lightbox-card .q-icon {
    color: #ffffff !important;
}
"""


def _get_file_action(attachment: AttachmentItem) -> tuple[str, str]:
    """返回非图片附件的操作图标和提示文案。"""
    if is_pdf_attachment(attachment):
        return "open_in_new", "新标签打开"
    return "download", "点击下载"


def _build_pdf_open_handler(attachment: AttachmentItem) -> str:
    """构建在新标签打开 PDF 的浏览器事件。"""
    source_url = get_attachment_preview_source(attachment)
    if attachment.content is None and source_url:
        return f"() => window.open({json.dumps(source_url)}, '_blank')"

    data_url = build_attachment_data_url(attachment)
    if not data_url:
        return "() => undefined"
    return f"""() => {{
        const previewWindow = window.open('', '_blank');
        fetch({json.dumps(data_url)})
            .then(response => response.blob())
            .then(blob => {{
                const objectUrl = URL.createObjectURL(blob);
                if (previewWindow) {{
                    previewWindow.opener = null;
                    previewWindow.location.href = objectUrl;
                }}
                window.setTimeout(() => URL.revokeObjectURL(objectUrl), 300000);
            }});
    }}"""


class AttachmentDisplay:
    """管理独立附件展示组件的状态和交互。"""

    def __init__(
        self,
        *,
        title: str = "附件列表",
        items: Sequence[AttachmentItem] = (),
        on_delete: Callable[[AttachmentItem], Any] | None = None,
        show_title: bool = True,
        show_empty: bool = False,
        full_width: bool = False,
    ) -> None:
        """初始化展示标题和附件列表。"""
        self.title = title
        self.items = list(items)
        self.on_delete = on_delete
        self.show_title = show_title
        self.show_empty = show_empty
        self.full_width = full_width
        self.section: Any | None = None
        self.container: Any | None = None
        self.preview_container: Any | None = None
        self.image_lightbox: Any | None = None
        self.lightbox_keyboard: Any | None = None
        self.preview_image_index = 0

    def build(self) -> AttachmentDisplay:
        """构建附件展示区和图片灯箱。"""
        ui.add_css(ATTACHMENT_DISPLAY_CSS)
        self._build_image_lightbox()
        width_classes = "w-full" if self.full_width else "w-full max-w-4xl"
        section_classes = f"mt-6 {width_classes} gap-4" if self.show_title else f"{width_classes} gap-3"
        self.section = ui.column().classes(section_classes)
        with self.section:
            self.container = ui.column().classes("w-full gap-4")
        self._render()
        return self

    def set_items(self, items: Sequence[AttachmentItem]) -> None:
        """替换附件列表并刷新展示区。"""
        self._close_lightbox()
        self.items[:] = items
        self.preview_image_index = 0
        self._render()

    def _build_image_lightbox(self) -> None:
        """构建全屏图片灯箱和键盘监听。"""
        self.image_lightbox = ui.dialog().props(
            "maximized transition-show=fade transition-hide=fade"
        )
        self.image_lightbox.on("hide", self._deactivate_lightbox_keyboard)
        with self.image_lightbox:
            with ui.card().classes(
                "ng-lightbox-card relative h-screen w-screen max-w-none rounded-none p-0 shadow-none"
            ):
                self.preview_container = ui.column().classes("h-full w-full gap-0")
        self.lightbox_keyboard = ui.keyboard(
            on_key=self._handle_lightbox_key,
            active=False,
            repeating=False,
            ignore=[],
        )

    def _get_images(self) -> list[AttachmentItem]:
        """获取当前列表中的图片附件。"""
        return [item for item in self.items if is_image_attachment(item)]

    def _download_attachment(self, attachment: AttachmentItem) -> None:
        """下载内存附件或打开业务提供的下载地址。"""
        if attachment.content is not None:
            ui.download(
                attachment.content,
                filename=attachment.file_name,
                media_type=attachment.content_type,
            )
            return

        download_source = get_attachment_download_source(attachment)
        if download_source:
            ui.navigate.to(download_source, new_tab=True)
            return
        ui.notify("当前附件没有可用的下载地址", type="warning")

    def _render_lightbox(self) -> None:
        """刷新图片灯箱中的当前图片和缩略图导航。"""
        if self.preview_container is None:
            return
        image_attachments = self._get_images()
        if not image_attachments:
            return

        current_attachment = image_attachments[self.preview_image_index]
        preview_source = get_attachment_preview_source(current_attachment)
        if not preview_source:
            ui.notify("当前图片没有可用的预览地址", type="warning")
            return

        clear_element(self.preview_container)
        with self.preview_container:
            with ui.row().classes("w-full items-center justify-between gap-4 px-4 py-3"):
                with ui.column().classes("min-w-0 gap-0"):
                    ui.label(current_attachment.file_name).classes(
                        "max-w-[70vw] truncate text-base font-semibold text-white"
                    )
                    ui.label(
                        f"{self.preview_image_index + 1}/{len(image_attachments)} · "
                        f"{format_attachment_size(current_attachment.size)}"
                    ).classes("text-xs text-slate-400")
                with ui.row().classes("shrink-0 items-center gap-1"):
                    ui.button(
                        "下载原图",
                        icon="download",
                        on_click=lambda item=current_attachment: self._download_attachment(item),
                    ).props("flat no-caps color=white")
                    ui.button(icon="close", on_click=self._close_lightbox).props(
                        "flat round color=white"
                    )

            with ui.row().classes("w-full flex-1 items-center justify-center gap-3 px-3 pb-4"):
                if len(image_attachments) > 1:
                    ui.button(icon="chevron_left", on_click=lambda: self._change_preview_image(-1)).props(
                        "flat round color=white size=lg"
                    )
                ui.image(preview_source).classes("h-[78vh] min-w-0 flex-1 rounded-lg").props(
                    "fit=contain no-spinner"
                )
                if len(image_attachments) > 1:
                    ui.button(icon="chevron_right", on_click=lambda: self._change_preview_image(1)).props(
                        "flat round color=white size=lg"
                    )

            with ui.row().classes(
                "absolute bottom-4 right-4 max-w-[70vw] flex-nowrap gap-2 overflow-x-auto "
                "rounded-xl bg-black/60 p-2 shadow-lg backdrop-blur"
            ):
                for index, attachment in enumerate(image_attachments):
                    thumbnail_source = get_attachment_thumbnail_source(attachment)
                    if not thumbnail_source:
                        continue
                    thumbnail_classes = (
                        "h-12 w-12 shrink-0 cursor-pointer rounded-md border-2 transition-all "
                        "duration-150"
                    )
                    if index == self.preview_image_index:
                        thumbnail_classes += " border-primary opacity-100"
                    else:
                        thumbnail_classes += " border-transparent opacity-60 hover:opacity-100"
                    ui.image(thumbnail_source).classes(thumbnail_classes).props(
                        "fit=cover no-spinner"
                    ).on("click", lambda selected_index=index: self._select_preview_image(selected_index))

    def _close_lightbox(self) -> None:
        """关闭图片灯箱。"""
        self._deactivate_lightbox_keyboard()
        if self.image_lightbox is not None:
            self.image_lightbox.close()

    def _deactivate_lightbox_keyboard(self) -> None:
        """停用灯箱键盘监听。"""
        if self.lightbox_keyboard is not None:
            self.lightbox_keyboard.active = False

    def _handle_lightbox_key(self, event: events.KeyEventArguments) -> None:
        """处理灯箱中的左右方向键和退出键。"""
        if not event.action.keydown:
            return
        if event.key.arrow_left:
            self._change_preview_image(-1)
        elif event.key.arrow_right:
            self._change_preview_image(1)
        elif event.key.escape:
            self._close_lightbox()

    def _change_preview_image(self, offset: int) -> None:
        """循环切换灯箱中的图片。"""
        image_count = len(self._get_images())
        if image_count == 0:
            return
        self.preview_image_index = (self.preview_image_index + offset) % image_count
        self._render_lightbox()

    def _select_preview_image(self, image_index: int) -> None:
        """切换到缩略图对应的图片。"""
        image_count = len(self._get_images())
        if not 0 <= image_index < image_count:
            return
        self.preview_image_index = image_index
        self._render_lightbox()

    def open_image_lightbox(self, attachment: AttachmentItem | None = None) -> None:
        """直接打开当前附件列表的图片灯箱。"""
        images = self._get_images()
        if not images:
            ui.notify("当前没有可预览的图片", type="warning")
            return
        self._open_image_lightbox(attachment if attachment in images else images[0])

    def _open_image_lightbox(self, attachment: AttachmentItem) -> None:
        """打开指定图片的灯箱预览。"""
        image_attachments = self._get_images()
        self.preview_image_index = next(
            (index for index, item in enumerate(image_attachments) if item is attachment),
            0,
        )
        self._render_lightbox()
        if self.image_lightbox is not None:
            self.image_lightbox.open()
        if self.lightbox_keyboard is not None:
            self.lightbox_keyboard.active = True

    async def _delete_attachment(self, attachment: AttachmentItem) -> None:
        """调用业务删除回调，并在成功后刷新附件列表。"""
        if self.on_delete is None:
            return
        delete_result = self.on_delete(attachment)
        if isawaitable(delete_result):
            delete_result = await delete_result
        if delete_result is False:
            return
        self.items[:] = [item for item in self.items if item is not attachment]
        self._render()

    def _render_preview_card(self, attachment: AttachmentItem) -> None:
        """渲染图片缩略图预览卡片。"""
        thumbnail_source = get_attachment_thumbnail_source(attachment)
        if not thumbnail_source:
            return

        card = ui.card().tight().classes(
            "attachment-focus-target group relative w-full max-w-[180px] cursor-pointer gap-0 overflow-hidden "
            "rounded-xl border border-slate-200 bg-white p-0 shadow-none transition-all duration-200 "
            "hover:-translate-y-0.5 hover:border-primary hover:shadow-md "
            "dark:border-slate-700 dark:bg-slate-900"
        ).props("role=button tabindex=0")
        card.on("click", lambda item=attachment: self._open_image_lightbox(item))

        with card:
            if self.on_delete is not None:
                delete_button = ui.button(
                    icon="delete_outline",
                    on_click=lambda item=attachment: self._delete_attachment(item),
                ).props("flat dense round size=sm color=negative").classes(
                    "absolute right-1 top-1 z-10 bg-white/90 dark:bg-slate-900/90"
                )
                delete_button.on("click", js_handler="(event) => event.stopPropagation()")
                with delete_button:
                    ui.tooltip("删除附件")
            with ui.image(thumbnail_source).classes("h-32 w-full").props(
                "fit=cover loading=lazy no-spinner"
            ):
                with ui.element("div").classes("absolute-bottom w-full px-2 py-1 text-center"):
                    ui.label(attachment.file_name).classes(
                        "w-full truncate text-subtitle2 leading-5"
                    )
                    ui.label(format_attachment_size(attachment.size)).classes(
                        "w-full truncate text-caption leading-4"
                    )

    def _render_file_link(self, attachment: AttachmentItem) -> None:
        """将非图片附件渲染为紧凑的链接式操作项。"""
        action_icon, action_text = _get_file_action(attachment)
        file_row = ui.row().classes(
            "attachment-focus-target group w-full cursor-pointer items-center gap-3 rounded-lg border "
            "border-transparent px-3 py-2 transition-colors duration-200 hover:border-slate-200 "
            "hover:bg-slate-50 dark:hover:border-slate-700 dark:hover:bg-slate-800"
        ).props("role=link tabindex=0")
        if is_pdf_attachment(attachment):
            file_row.on("click", js_handler=_build_pdf_open_handler(attachment))
        else:
            file_row.on("click", lambda item=attachment: self._download_attachment(item))

        with file_row:
            ui.icon(get_attachment_icon(attachment.file_name), size="sm").classes(
                "shrink-0 text-primary"
            )
            ui.label(attachment.file_name).classes(
                "min-w-0 flex-1 truncate text-sm font-medium text-primary group-hover:underline"
            )
            ui.label(format_attachment_size(attachment.size)).classes(
                "shrink-0 text-xs text-gray-400"
            )
            with ui.row().classes(
                "shrink-0 items-center gap-1 text-gray-400 transition-colors group-hover:text-primary"
            ):
                ui.icon(action_icon, size="xs")
                ui.label(action_text).classes("hidden text-xs sm:block")
            if self.on_delete is not None:
                delete_button = ui.button(
                    icon="delete_outline",
                    on_click=lambda item=attachment: self._delete_attachment(item),
                ).props("flat dense round size=sm color=negative")
                delete_button.on("click", js_handler="(event) => event.stopPropagation()")
                with delete_button:
                    ui.tooltip("删除附件")

    def _render(self) -> None:
        """刷新独立附件展示区。"""
        if self.container is None or self.section is None:
            return
        self.section.set_visibility(bool(self.items) or self.show_empty)
        clear_element(self.container)
        if not self.items:
            if self.show_empty:
                with self.container:
                    if self.show_title:
                        render_section_title(self.title, accent=True)
                    empty_width_classes = "w-full" if self.full_width else "w-full max-w-2xl"
                    with ui.row().classes(
                        f"{empty_width_classes} items-center gap-3 rounded-xl border border-dashed "
                        "border-gray-300 px-4 py-5 text-gray-400 dark:border-slate-600"
                    ):
                        ui.icon("attachment", size="sm")
                        ui.label("暂未上传附件").classes("text-sm")
            return

        image_attachments = [item for item in self.items if is_image_attachment(item)]
        pdf_count = sum(is_pdf_attachment(item) for item in self.items)
        file_attachments = [item for item in self.items if not is_image_attachment(item)]
        other_count = len(file_attachments) - pdf_count

        with self.container:
            with ui.column().classes("gap-0.5"):
                if self.show_title:
                    render_section_title(self.title, accent=True)
                ui.label(
                    f"共 {len(self.items)} 个 · 图片 {len(image_attachments)} 个 · "
                    f"PDF {pdf_count} 个 · 其他 {other_count} 个"
                ).classes("ml-4 text-sm text-gray-400" if self.show_title else "text-sm text-gray-400")

            if image_attachments:
                with ui.element("div").classes("grid w-full gap-3").style(
                    "grid-template-columns: repeat(auto-fill, minmax(150px, 180px));"
                ):
                    for attachment in image_attachments:
                        self._render_preview_card(attachment)

            if file_attachments:
                file_width_classes = "w-full" if self.full_width else "w-full max-w-2xl"
                with ui.column().classes(f"{file_width_classes} gap-1"):
                    ui.label("其他附件").classes("px-3 text-sm font-semibold text-gray-500")
                    for attachment in file_attachments:
                        self._render_file_link(attachment)


def build_attachment_display(
    *,
    title: str = "附件列表",
    items: Sequence[AttachmentItem] = (),
    on_delete: Callable[[AttachmentItem], Any] | None = None,
    show_title: bool = True,
    show_empty: bool = False,
    full_width: bool = False,
) -> AttachmentDisplay:
    """构建可独立刷新的通用附件展示组件。"""
    return AttachmentDisplay(
        title=title,
        items=items,
        on_delete=on_delete,
        show_title=show_title,
        show_empty=show_empty,
        full_width=full_width,
    ).build()
