"""业务域事务用例：读取单条示例事项。"""

from __future__ import annotations

from typing import Any

from models import ExampleItem


def _serialize(item: ExampleItem) -> dict[str, Any]:
    """序列化详情行。"""
    return {
        "id": int(item.id),
        "title": item.title,
        "content": item.content or "",
        "is_done": bool(item.is_done),
        "created_at": item.created_at.strftime("%Y-%m-%d %H:%M") if item.created_at else "",
        "updated_at": item.updated_at.strftime("%Y-%m-%d %H:%M") if item.updated_at else "",
    }


async def get_item(item_id: int) -> dict[str, Any] | None:
    """读取单条示例事项。"""
    item = await ExampleItem.filter(id=item_id).first()
    if item is None:
        return None
    return _serialize(item)
