"""通用附件上传组件。

本模块只负责附件选择、基础校验、待提交列表和提交回调。
数据库记录、本地目录或 OSS 等持久化必须由业务 service 通过 ``on_submit`` 处理。
"""

from __future__ import annotations

import mimetypes
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from inspect import isawaitable
from typing import Any

from nicegui import events, ui

from modules.ui.attachment_types import (
    DEFAULT_ATTACHMENT_EXTENSIONS,
    AttachmentItem,
    format_attachment_extension_hint,
    format_attachment_size,
    get_attachment_icon,
    is_allowed_attachment_name,
    normalize_attachment_extensions,
    validate_attachment_preview_content,
)
from modules.ui.helpers import clear_element, read_upload_event_file

__all__ = [
    "DEFAULT_ATTACHMENT_EXTENSIONS",
    "AttachmentItem",
    "AttachmentUpload",
    "AttachmentUploadState",
    "build_attachment_upload",
]


@dataclass(slots=True)
class AttachmentUploadState:
    """保存待提交附件和最近一次成功提交的附件。"""

    pending: list[AttachmentItem] = field(default_factory=list)
    submitted: list[AttachmentItem] = field(default_factory=list)


class AttachmentUpload:
    """管理通用附件上传组件的状态和交互。"""

    def __init__(
        self,
        *,
        title: str,
        max_files: int,
        max_file_size: int,
        allowed_extensions: Sequence[str],
        show_submit_button: bool,
        full_width: bool,
        on_submit: Callable[[list[AttachmentItem]], Any] | None = None,
    ) -> None:
        """初始化附件限制、提交回调和页面状态。"""
        if max_files <= 0:
            raise ValueError("最大附件数量必须大于 0")
        if max_file_size <= 0:
            raise ValueError("单个附件大小限制必须大于 0")

        self.title = title
        self.max_files = max_files
        self.max_file_size = max_file_size
        self.normalized_extensions = normalize_attachment_extensions(allowed_extensions)
        self.accept_value = ",".join(self.normalized_extensions)
        self.extension_hint = format_attachment_extension_hint(self.normalized_extensions)
        self.max_file_size_text = format_attachment_size(max_file_size)
        self.show_submit_button = show_submit_button
        self.full_width = full_width
        self.on_submit = on_submit
        self.state = AttachmentUploadState()

        self.attachment_container: Any | None = None
        self.submit_button: Any | None = None
        self.uploader: Any | None = None

    def build(self) -> AttachmentUploadState:
        """构建隐藏上传器和待提交附件卡片。"""
        self._build_hidden_uploader()
        self._build_upload_card()
        return self.state

    def _build_hidden_uploader(self) -> None:
        """构建由自定义按钮触发的隐藏上传器。"""
        self.uploader = ui.upload(
            on_upload=self._handle_upload,
            on_rejected=self._handle_rejected,
            multiple=True,
            auto_upload=True,
        ).classes("hidden").props(
            f"accept={self.accept_value} max-file-size={self.max_file_size} no-thumbnails"
        )

    def _build_upload_card(self) -> None:
        """构建紧凑的待提交附件选择卡片。"""
        width_classes = "w-full" if self.full_width else "w-full max-w-2xl"
        with ui.card().classes(
            f"{width_classes} rounded-xl border border-dashed border-gray-300 p-4 shadow-none "
            "dark:border-slate-600 dark:bg-slate-900"
        ):
            with ui.row().classes("w-full items-start justify-between gap-4"):
                with ui.row().classes("min-w-0 flex-1 items-start gap-3"):
                    ui.icon("attach_file", size="md").classes("mt-1 shrink-0 text-primary")
                    with ui.column().classes("min-w-0 flex-1 gap-0.5"):
                        ui.label(self.title).classes("text-base font-semibold")
                        ui.label(
                            f"最多 {self.max_files} 个附件，单个不超过 {self.max_file_size_text}"
                        ).classes("text-sm text-gray-400")
                        ui.label(f"支持：{self.extension_hint}").classes("text-xs leading-5 text-gray-400")
                with ui.row().classes("shrink-0 items-center gap-2"):
                    ui.button(
                        "添加",
                        icon="add",
                        on_click=self._open_file_picker,
                    ).props("outline rounded no-caps color=primary").classes("min-w-24")
                    if self.show_submit_button:
                        self.submit_button = ui.button(
                            "提交",
                            icon="cloud_upload",
                            on_click=self._submit_attachments,
                        ).props("unelevated rounded no-caps color=primary").classes("min-w-24")
            self.attachment_container = ui.column().classes("w-full gap-2")
            self._render_pending_attachments()

    def _update_submit_button(self) -> None:
        """根据待提交附件数量更新提交按钮状态。"""
        if self.submit_button is not None:
            self.submit_button.set_enabled(bool(self.state.pending))

    def _render_pending_attachments(self) -> None:
        """刷新当前待提交附件列表。"""
        if self.attachment_container is None:
            return
        clear_element(self.attachment_container)
        with self.attachment_container:
            if not self.state.pending:
                ui.label("暂未添加附件").classes("text-sm text-gray-400")
            for attachment in list(self.state.pending):
                with ui.row().classes(
                    "w-full items-center gap-3 rounded-lg bg-gray-100 px-3 py-2 dark:bg-slate-800"
                ):
                    ui.icon(get_attachment_icon(attachment.file_name), size="sm").classes(
                        "shrink-0 text-primary"
                    )
                    with ui.column().classes("min-w-0 flex-1 gap-0"):
                        ui.label(attachment.file_name).classes("w-full truncate text-xs font-medium")
                        ui.label(format_attachment_size(attachment.size)).classes(
                            "text-[11px] text-gray-400"
                        )
                    ui.button(
                        icon="close",
                        on_click=lambda item=attachment: self._remove_attachment(item),
                    ).props("flat dense round size=xs color=grey")
        self._update_submit_button()

    def _remove_attachment(self, attachment: AttachmentItem) -> None:
        """删除页面内存中的指定待提交附件。"""
        item_index = next(
            (index for index, item in enumerate(self.state.pending) if item is attachment),
            None,
        )
        if item_index is None:
            return
        self.state.pending.pop(item_index)
        self._render_pending_attachments()

    async def _submit_attachments(self) -> None:
        """调用提交回调，并在成功后记录最近一次提交结果。"""
        if not self.state.pending:
            ui.notify("请先添加附件", type="warning")
            return

        submitted_attachments = list(self.state.pending)
        if self.on_submit is not None:
            submit_result = self.on_submit(submitted_attachments)
            if isawaitable(submit_result):
                submit_result = await submit_result
            if submit_result is False:
                return

        self.state.submitted[:] = submitted_attachments
        self.state.pending.clear()
        self._render_pending_attachments()
        ui.notify(f"已提交 {len(self.state.submitted)} 个附件", type="positive")

    async def _handle_upload(self, event: events.UploadEventArguments) -> None:
        """校验并读取附件到页面内存。"""
        try:
            if len(self.state.pending) >= self.max_files:
                ui.notify(f"最多上传 {self.max_files} 个附件", type="warning")
                return

            try:
                file_name, content = await read_upload_event_file(event)
                validate_attachment_preview_content(file_name, content)
            except ValueError as exc:
                ui.notify(str(exc), type="negative")
                return

            if not is_allowed_attachment_name(file_name, self.normalized_extensions):
                ui.notify(f"{file_name} 的文件格式不支持", type="warning")
                return
            if len(content) > self.max_file_size:
                ui.notify(f"{file_name} 超过 {self.max_file_size_text}，未添加", type="warning")
                return
            if len(self.state.pending) >= self.max_files:
                ui.notify(f"最多上传 {self.max_files} 个附件", type="warning")
                return

            upload_file = getattr(event, "file", None)
            guessed_content_type = mimetypes.guess_type(file_name)[0]
            self.state.pending.append(
                AttachmentItem.from_bytes(
                    file_name=file_name,
                    content_type=str(
                        guessed_content_type
                        or getattr(upload_file, "content_type", "")
                        or "application/octet-stream"
                    ),
                    content=content,
                )
            )
            self._render_pending_attachments()
        finally:
            if self.uploader is not None:
                await self.uploader.run_method("removeUploadedFiles")

    def _handle_rejected(self) -> None:
        """提示前端拒绝的附件格式或大小限制。"""
        ui.notify(
            f"附件未添加，请选择支持的格式，且单个文件不超过 {self.max_file_size_text}",
            type="warning",
        )

    async def _open_file_picker(self) -> None:
        """打开隐藏上传器的文件选择窗口。"""
        if self.uploader is not None:
            await self.uploader.run_method("pickFiles")


def build_attachment_upload(
    *,
    title: str = "上传附件",
    max_files: int = 6,
    max_file_size: int = 10 * 1024 * 1024,
    allowed_extensions: Sequence[str] = DEFAULT_ATTACHMENT_EXTENSIONS,
    show_submit_button: bool = True,
    full_width: bool = False,
    on_submit: Callable[[list[AttachmentItem]], Any] | None = None,
) -> AttachmentUploadState:
    """构建存储无关的通用附件上传组件。"""
    component = AttachmentUpload(
        title=title,
        max_files=max_files,
        max_file_size=max_file_size,
        allowed_extensions=allowed_extensions,
        show_submit_button=show_submit_button,
        full_width=full_width,
        on_submit=on_submit,
    )
    return component.build()
