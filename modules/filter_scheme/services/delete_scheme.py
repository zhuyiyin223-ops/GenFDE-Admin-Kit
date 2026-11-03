"""系统能力用例：删除自己创建的过滤方案。"""

from __future__ import annotations

from tortoise.exceptions import OperationalError

from models import UserFilterSchemePref

from .scheme_access import _get_owned_row, _require_user_id
from .scheme_values import WRITE_MIGRATION_ERROR, FilterSchemeConfig


async def delete_scheme(
    *,
    user_id: int | None,
    config: FilterSchemeConfig,
    scheme_id: int,
) -> None:
    """删除自己创建的过滤方案。"""
    current_user_id = _require_user_id(user_id)
    row = await _get_owned_row(
        user_id=current_user_id,
        config=config,
        scheme_id=scheme_id,
    )
    try:
        await row.delete()
        await UserFilterSchemePref.filter(default_scheme_id=int(row.id)).update(default_scheme_id=None)
    except OperationalError as exc:
        raise RuntimeError(WRITE_MIGRATION_ERROR) from exc
