"""业务域事务用例：分页查询示例事项。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from tortoise.expressions import Q

from models import ExampleItem
from modules.column_filter.services import ColumnFilterSpec, ColumnFilterValue, apply_column_filter_q
from modules.keyword_search.services import build_keyword_q

DONE_LABELS: dict[bool, str] = {True: "已完成", False: "未完成"}


def _serialize(item: ExampleItem) -> dict[str, Any]:
    """序列化列表行。"""
    return {
        "id": int(item.id),
        "title": item.title,
        "content": item.content or "",
        "is_done": bool(item.is_done),
        "created_at": item.created_at.strftime("%Y-%m-%d %H:%M") if item.created_at else "",
        "updated_at": item.updated_at.strftime("%Y-%m-%d %H:%M") if item.updated_at else "",
    }


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
        "items": [_serialize(item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
