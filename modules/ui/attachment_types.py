"""附件上传与展示共用的数据结构和文件规则。"""

from __future__ import annotations

import base64
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
WORD_EXTENSIONS = (".doc", ".docx")
EXCEL_EXTENSIONS = (".xls", ".xlsx", ".csv")
POWERPOINT_EXTENSIONS = (".ppt", ".pptx")
TEXT_EXTENSIONS = (".txt",)
ARCHIVE_EXTENSIONS = (".zip", ".rar", ".7z")
DEFAULT_ATTACHMENT_EXTENSIONS = (
    ".pdf",
    *WORD_EXTENSIONS,
    *EXCEL_EXTENSIONS,
    *POWERPOINT_EXTENSIONS,
    *TEXT_EXTENSIONS,
    *IMAGE_EXTENSIONS,
    *ARCHIVE_EXTENSIONS,
)


@dataclass(slots=True)
class AttachmentItem:
    """表示可由上传组件和展示组件共同使用的附件。"""

    file_name: str
    content_type: str
    size: int
    attachment_id: int | None = None
    content: bytes | None = None
    thumbnail_url: str | None = None
    preview_url: str | None = None
    download_url: str | None = None

    @classmethod
    def from_bytes(cls, *, file_name: str, content_type: str, content: bytes) -> AttachmentItem:
        """从内存字节构建附件对象。"""
        return cls(
            file_name=file_name,
            content_type=content_type,
            size=len(content),
            content=content,
        )


def normalize_attachment_extensions(extensions: Sequence[str]) -> tuple[str, ...]:
    """规范化文件后缀并保持原有顺序。"""
    if isinstance(extensions, str):
        raise TypeError("允许上传的文件后缀必须使用序列配置")

    normalized_extensions: list[str] = []
    seen_extensions: set[str] = set()

    for raw_extension in extensions:
        extension = str(raw_extension or "").strip().lower()
        if not extension:
            continue
        if not extension.startswith("."):
            extension = f".{extension}"
        if any(separator in extension for separator in (",", ";", "/", "\\", " ")):
            raise ValueError(f"文件后缀配置不合法：{raw_extension}")
        if extension in seen_extensions:
            continue
        seen_extensions.add(extension)
        normalized_extensions.append(extension)

    if not normalized_extensions:
        raise ValueError("至少需要配置一个允许上传的文件后缀")
    return tuple(normalized_extensions)


def format_attachment_size(file_size: int) -> str:
    """将字节数转换为保留两位小数的文件大小。"""
    size_value = float(file_size)
    for unit in ("B", "KB", "MB", "GB"):
        if size_value < 1024 or unit == "GB":
            return f"{size_value:.2f} {unit}"
        size_value /= 1024
    return f"{file_size:.2f} B"


def format_attachment_extension_hint(extensions: Sequence[str]) -> str:
    """生成用户可读的文件后缀提示。"""
    return "、".join(extension.removeprefix(".").upper() for extension in extensions)


def get_attachment_extension(file_name: str) -> str:
    """获取文件名中的小写后缀。"""
    return Path(file_name).suffix.lower()


def is_image_attachment(attachment: AttachmentItem) -> bool:
    """判断附件是否为支持灯箱预览的图片。"""
    return get_attachment_extension(attachment.file_name) in IMAGE_EXTENSIONS


def is_pdf_attachment(attachment: AttachmentItem) -> bool:
    """判断附件是否为 PDF。"""
    return get_attachment_extension(attachment.file_name) == ".pdf"


def get_attachment_icon(file_name: str) -> str:
    """按文件后缀返回附件展示图标。"""
    extension = get_attachment_extension(file_name)
    if extension in IMAGE_EXTENSIONS:
        return "image"
    if extension == ".pdf":
        return "picture_as_pdf"
    if extension in WORD_EXTENSIONS or extension in TEXT_EXTENSIONS:
        return "description"
    if extension in EXCEL_EXTENSIONS:
        return "table_view"
    if extension in POWERPOINT_EXTENSIONS:
        return "slideshow"
    if extension in ARCHIVE_EXTENSIONS:
        return "folder_zip"
    return "attach_file"


def is_allowed_attachment_name(file_name: str, extensions: Sequence[str]) -> bool:
    """判断文件名是否匹配允许上传的后缀。"""
    normalized_file_name = file_name.strip().lower()
    return any(normalized_file_name.endswith(extension) for extension in extensions)


def validate_attachment_preview_content(file_name: str, content: bytes) -> None:
    """校验图片和 PDF 的文件头，避免预览明显不匹配的内容。"""
    if not content:
        raise ValueError(f"{file_name} 是空文件")

    extension = get_attachment_extension(file_name)
    image_signatures = {
        ".png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": content.startswith(b"\xff\xd8\xff"),
        ".jpeg": content.startswith(b"\xff\xd8\xff"),
        ".gif": content.startswith((b"GIF87a", b"GIF89a")),
        ".webp": len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP",
        ".bmp": content.startswith(b"BM"),
    }
    if extension in image_signatures and not image_signatures[extension]:
        raise ValueError(f"{file_name} 的图片内容与文件后缀不匹配")
    if extension == ".pdf" and b"%PDF-" not in content[:1024]:
        raise ValueError(f"{file_name} 不是有效的 PDF 文件")


def build_attachment_data_url(attachment: AttachmentItem) -> str | None:
    """将内存附件转换为浏览器可展示的数据地址。"""
    if attachment.content is None:
        return None
    encoded_content = base64.b64encode(attachment.content).decode("ascii")
    return f"data:{attachment.content_type};base64,{encoded_content}"


def get_attachment_preview_source(attachment: AttachmentItem) -> str | None:
    """获取附件的大图或在线预览地址。"""
    return attachment.preview_url or attachment.download_url or build_attachment_data_url(attachment)


def get_attachment_thumbnail_source(attachment: AttachmentItem) -> str | None:
    """获取图片附件的缩略图地址。"""
    return attachment.thumbnail_url or get_attachment_preview_source(attachment)


def get_attachment_download_source(attachment: AttachmentItem) -> str | None:
    """获取附件的下载地址。"""
    return attachment.download_url or attachment.preview_url
