"""业务域事务用例：新增示例事项。"""

from __future__ import annotations

from models import ExampleItem


def _normalize_title(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("标题不能为空")
    if len(text) > 128:
        raise ValueError("标题长度不能超过 128 个字符")
    return text


def _normalize_content(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


async def create_item(*, title: str, content: str | None, is_done: bool) -> ExampleItem:
    """新增示例事项。"""
    return await ExampleItem.create(
        title=_normalize_title(title),
        content=_normalize_content(content),
        is_done=bool(is_done),
    )
