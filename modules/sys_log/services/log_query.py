"""业务域：操作日志查询组装。非事务，供查询与导出复用，避免 N+1。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any

from tortoise.expressions import Q

from models import User, UserLog
from modules.column_filter.services import ColumnFilterSpec, ColumnFilterValue, apply_column_filter_q
from modules.keyword_search.services import build_keyword_q, or_q

from .operation_labels import OPERATION_TYPE_LABELS


def parse_date(text: str) -> datetime | None:
    """将日期文本转换为当天零点。"""
    normalized = str(text or "").strip()
    if not normalized:
        return None
    try:
        return datetime.strptime(normalized, "%Y-%m-%d")
    except ValueError:
        return None


def to_export_row(item: dict[str, Any]) -> dict[str, Any]:
    """将操作日志展示行转为导出字段。"""
    return {
        "user_name": item.get("user_name") or "",
        "user_id": item.get("user_id") or "",
        "operation_type": item.get("operation_type") or "",
        "module": item.get("module") or "",
        "action": item.get("action") or "",
        "execution_time": item.get("execution_time") or "",
        "created_at": item.get("created_at") or "",
    }


async def user_log_q_by_user_keyword(keyword: str | None) -> Q | None:
    """按操作用户账号或姓名关键词反查日志。"""
    user_q = build_keyword_q(("userid", "name"), keyword, model=User)
    if user_q is None:
        return None
    user_ids = [int(pk) for pk in await User.filter(user_q).values_list("id", flat=True)]
    if not user_ids:
        return None
    return Q(user_id__in=user_ids)


async def collect_user_logs(
    page: int = 1,
    page_size: int = 10,
    keyword: str = "",
    date_range: str = "",
    operation_type: int | None = None,
    column_filters: Mapping[str, ColumnFilterValue] | None = None,
    column_filter_specs: Sequence[ColumnFilterSpec] = (),
) -> dict[str, Any]:
    """分页查询操作日志。"""
    query = Q()
    keyword_q = or_q(
        build_keyword_q(
            ("module", "action", "execution_time", "created_at"),
            keyword,
            model=UserLog,
            labels={"operation_type": OPERATION_TYPE_LABELS},
        ),
        await user_log_q_by_user_keyword(keyword),
    )
    if keyword_q:
        query &= keyword_q
    query = apply_column_filter_q(query, column_filter_specs, column_filters)

    date_range_text = str(date_range or "").strip()
    if date_range_text and " - " in date_range_text:
        start_text, end_text = date_range_text.split(" - ", 1)
        start_dt = parse_date(start_text)
        end_dt = parse_date(end_text)
        if start_dt is not None:
            query &= Q(created_at__gte=start_dt)
        if end_dt is not None:
            query &= Q(created_at__lt=end_dt + timedelta(days=1))

    if operation_type is not None:
        query &= Q(operation_type=operation_type)

    current_page = max(1, int(page))
    current_page_size = max(1, int(page_size))
    total = await UserLog.filter(query).count()
    logs = await UserLog.filter(query).offset((current_page - 1) * current_page_size).limit(
        current_page_size
    ).order_by("-created_at", "-id")

    user_ids = list({int(item.user_id) for item in logs if item.user_id})
    users = await User.filter(id__in=user_ids).values("id", "name", "userid") if user_ids else []
    user_map = {int(row["id"]): row for row in users if row.get("id") is not None}

    rows = []
    for index, item in enumerate(logs, start=(current_page - 1) * current_page_size + 1):
        user_row = user_map.get(int(item.user_id)) if item.user_id else None
        operation_type_value = int(item.operation_type) if item.operation_type is not None else -1
        rows.append(
            {
                "id": int(item.id),
                "index": index,
                "user_name": str(user_row.get("name")) if user_row else "-",
                "user_id": str(user_row.get("userid")) if user_row else str(item.user_id),
                "operation_type": OPERATION_TYPE_LABELS.get(operation_type_value, "未知"),
                "module": item.module or "",
                "action": item.action or "",
                "execution_time": f"{float(item.execution_time):.4f}s" if item.execution_time is not None else "",
                "created_at": item.created_at.strftime("%Y-%m-%d %H:%M") if item.created_at else "",
            }
        )

    return {"logs": rows, "total": total, "page": current_page, "page_size": current_page_size}
