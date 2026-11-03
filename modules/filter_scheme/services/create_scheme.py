"""系统能力用例：新建个人过滤方案。"""

from __future__ import annotations

from datetime import date
from typing import Any

from tortoise.exceptions import IntegrityError, OperationalError

from models import FilterSchemeVisibility, UserFilterScheme

from .scheme_access import _assert_count_available, _assert_name_available, _next_personal_sort_order, _require_user_id
from .scheme_values import (
    DUPLICATE_NAME_ERROR,
    EMPTY_SCHEME_ERROR,
    WRITE_MIGRATION_ERROR,
    FilterScheme,
    FilterSchemeConfig,
    _to_scheme,
    encode_values,
    is_default_values,
    normalize_name,
)


async def create_scheme(
    *,
    user_id: int | None,
    config: FilterSchemeConfig,
    name: str,
    values: dict[str, Any],
    today: date | None = None,
) -> FilterScheme:
    """新建个人过滤方案。values 为控件形态。"""
    current_user_id = _require_user_id(user_id)
    normalized_name = normalize_name(name, config=config)
    stored_values = encode_values(values, config=config, today=today)
    if is_default_values(stored_values, config=config):
        raise ValueError(EMPTY_SCHEME_ERROR)
    await _assert_name_available(
        user_id=current_user_id,
        config=config,
        name=normalized_name,
        exclude_id=None,
    )
    await _assert_count_available(user_id=current_user_id, config=config)
    sort_order = await _next_personal_sort_order(user_id=current_user_id, config=config)
    try:
        row = await UserFilterScheme.create(
            user_id=current_user_id,
            page_code=config.page_code,
            list_key=config.list_key,
            name=normalized_name,
            visibility=FilterSchemeVisibility.PERSONAL,
            filter_values=stored_values,
            sort_order=sort_order,
        )
    except IntegrityError as exc:
        raise ValueError(DUPLICATE_NAME_ERROR) from exc
    except OperationalError as exc:
        raise RuntimeError(WRITE_MIGRATION_ERROR) from exc
    return _to_scheme(row, config=config)
