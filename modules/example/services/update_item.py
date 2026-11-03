"""业务域事务用例：更新示例事项。"""

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


async def update_item(
    *,
    item_id: int,
    title: str,
    content: str | None,
    is_done: bool,
) -> ExampleItem:
    """更新示例事项。"""
    item = await ExampleItem.get_or_none(id=item_id)
    if item is None:
        raise ValueError("事项不存在")
    item.title = _normalize_title(title)
    item.content = _normalize_content(content)
    item.is_done = bool(is_done)
    await item.save()
    return item
