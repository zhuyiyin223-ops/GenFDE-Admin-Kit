"""系统能力用例：更新自己创建的过滤方案。"""

from __future__ import annotations

from datetime import date
from typing import Any

from tortoise.exceptions import IntegrityError, OperationalError

from models import FilterSchemeVisibility

from .scheme_access import _assert_name_available, _get_owned_row, _require_user_id
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
    normalize_values,
)


async def update_scheme(
    *,
    user_id: int | None,
    config: FilterSchemeConfig,
    scheme_id: int,
    values: dict[str, Any] | None = None,
    name: str | None = None,
    today: date | None = None,
) -> FilterScheme:
    """更新自己创建的过滤方案。values 为控件形态；None 表示不改筛选值。"""
    current_user_id = _require_user_id(user_id)
    row = await _get_owned_row(
        user_id=current_user_id,
        config=config,
        scheme_id=scheme_id,
    )
    next_name = normalize_name(name, config=config) if name is not None else str(row.name or "")
    if values is None:
        stored_values = normalize_values(row.filter_values, config=config)
    else:
        stored_values = encode_values(values, config=config, today=today)
    if is_default_values(stored_values, config=config):
        raise ValueError(EMPTY_SCHEME_ERROR)
    await _assert_name_available(
        user_id=current_user_id,
        config=config,
        name=next_name,
        exclude_id=int(row.id),
    )
    row.name = next_name
    row.visibility = FilterSchemeVisibility.PERSONAL
    row.filter_values = stored_values
    try:
        await row.save()
    except IntegrityError as exc:
        raise ValueError(DUPLICATE_NAME_ERROR) from exc
    except OperationalError as exc:
        raise RuntimeError(WRITE_MIGRATION_ERROR) from exc
    return _to_scheme(row, config=config)
