"""业务域：示例事项数据服务。新增域把业务读写只放在本文件。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from models import ExampleItem
from modules.column_filter.service import ColumnFilterSpec, ColumnFilterValue, apply_column_filter_q
from modules.keyword_search.service import build_keyword_q

DONE_LABELS: dict[bool, str] = {True: "已完成", False: "未完成"}


class ExampleItemService:
    """示例事项读写服务。"""

    @staticmethod
    def _normalize_title(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("标题不能为空")
        if len(text) > 128:
            raise ValueError("标题长度不能超过 128 个字符")
        return text

    @staticmethod
    def _normalize_content(value: str | None) -> str | None:
        text = str(value or "").strip()
        return text or None

    @staticmethod
    async def search_items(
        *,
        page: int = 1,
        page_size: int = 10,
        keyword: str | None = None,
        column_filters: Mapping[str, ColumnFilterValue] | None = None,
        column_filter_specs: Sequence[ColumnFilterSpec] = (),
    ) -> dict[str, Any]:
        """分页查询示例事项。"""
        page = max(1, int(page or 1))
        page_size = max(1, int(page_size or 10))
        query = Q()
        keyword_q = build_keyword_q(
            ("title", "content", "created_at", "updated_at"),
            keyword,
            model=ExampleItem,
            labels={"is_done": DONE_LABELS},
        )
        if keyword_q:
            query &= keyword_q
        query = apply_column_filter_q(query, column_filter_specs, column_filters)

        total = await ExampleItem.filter(query).count()
        items = await ExampleItem.filter(query).offset((page - 1) * page_size).limit(page_size).order_by("-id")
        return {
            "items": [ExampleItemService._serialize(item) for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    async def get_item(item_id: int) -> dict[str, Any] | None:
        """读取单条示例事项。"""
        item = await ExampleItem.filter(id=item_id).first()
        if item is None:
            return None
        return ExampleItemService._serialize(item)

    @staticmethod
    async def create_item(*, title: str, content: str | None, is_done: bool) -> ExampleItem:
        """新增示例事项。"""
        return await ExampleItem.create(
            title=ExampleItemService._normalize_title(title),
            content=ExampleItemService._normalize_content(content),
            is_done=bool(is_done),
        )

    @staticmethod
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
        item.title = ExampleItemService._normalize_title(title)
        item.content = ExampleItemService._normalize_content(content)
        item.is_done = bool(is_done)
        await item.save()
        return item

    @staticmethod
    async def delete_item(item_id: int) -> None:
        """删除示例事项。"""
        item = await ExampleItem.get_or_none(id=item_id)
        if item is None:
            raise ValueError("事项不存在")
        async with in_transaction():
            await item.delete()

    @staticmethod
    def _serialize(item: ExampleItem) -> dict[str, Any]:
        """序列化列表/详情行。"""
        return {
            "id": int(item.id),
            "title": item.title,
            "content": item.content or "",
            "is_done": bool(item.is_done),
            "created_at": item.created_at.strftime("%Y-%m-%d %H:%M") if item.created_at else "",
            "updated_at": item.updated_at.strftime("%Y-%m-%d %H:%M") if item.updated_at else "",
        }
