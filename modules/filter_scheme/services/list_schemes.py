"""系统能力用例：列出当前用户的个人过滤方案。"""

from __future__ import annotations

from loguru import logger

from models import FilterSchemeVisibility, UserFilterScheme

from .scheme_access import _is_valid_user_id
from .scheme_values import READ_MIGRATION_ERROR, FilterScheme, FilterSchemeConfig, _scheme_sort_key, _to_scheme


async def list_schemes(*, user_id: int | None, config: FilterSchemeConfig) -> list[FilterScheme]:
    """列出当前用户在该列表上的个人方案。"""
    if not _is_valid_user_id(user_id):
        return []
    try:
        rows = await UserFilterScheme.filter(
            user_id=user_id,
            page_code=config.page_code,
            list_key=config.list_key,
            visibility=FilterSchemeVisibility.PERSONAL,
        )
    except Exception:
        logger.exception("读取过滤方案列表失败")
        raise RuntimeError(READ_MIGRATION_ERROR) from None

    schemes = [_to_scheme(row, config=config) for row in rows]
    schemes.sort(key=_scheme_sort_key)
    return schemes
