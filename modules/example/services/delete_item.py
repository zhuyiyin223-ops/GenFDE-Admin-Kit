"""业务域事务用例：删除示例事项。"""

from __future__ import annotations

from tortoise.transactions import in_transaction

from models import ExampleItem


async def delete_item(item_id: int) -> None:
    """在单个事务中删除示例事项。"""
    item = await ExampleItem.get_or_none(id=item_id)
    if item is None:
        raise ValueError("事项不存在")
    async with in_transaction():
        await item.delete()
