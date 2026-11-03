"""系统能力：过滤方案归属校验。非事务，写入用例共用。"""

from __future__ import annotations

from loguru import logger

from models import FilterSchemeVisibility, UserFilterScheme

from .scheme_values import (
    DUPLICATE_NAME_ERROR,
    FORBIDDEN_SCHEME_ERROR,
    READ_MIGRATION_ERROR,
    FilterSchemeConfig,
)


def _is_valid_user_id(user_id: int | None) -> bool:
    """判断登录账号 ID 是否可用。"""
    return isinstance(user_id, int) and user_id > 0


def _require_user_id(user_id: int | None) -> int:
    """写路径要求有效登录账号。"""
    if not _is_valid_user_id(user_id):
        raise ValueError("当前登录账号无效，无法保存过滤方案")
    return int(user_id)


async def _get_owned_row(
    *,
    user_id: int,
    config: FilterSchemeConfig,
    scheme_id: int,
) -> UserFilterScheme:
    """读取当前用户拥有的方案行。"""
    try:
        row = await UserFilterScheme.filter(
            id=scheme_id,
            user_id=user_id,
            page_code=config.page_code,
            list_key=config.list_key,
        ).first()
    except Exception:
        logger.exception("读取过滤方案失败")
        raise RuntimeError(READ_MIGRATION_ERROR) from None
    if row is None:
        raise ValueError(FORBIDDEN_SCHEME_ERROR)
    return row


async def _assert_name_available(
    *,
    user_id: int,
    config: FilterSchemeConfig,
    name: str,
    exclude_id: int | None,
) -> None:
    """检查当前用户在该列表上是否重名。"""
    query = UserFilterScheme.filter(
        user_id=user_id,
        page_code=config.page_code,
        list_key=config.list_key,
        name=name,
        visibility=FilterSchemeVisibility.PERSONAL,
    )
    if exclude_id is not None:
        query = query.exclude(id=exclude_id)
    try:
        exists = await query.exists()
    except Exception:
        logger.exception("校验过滤方案名称失败")
        raise RuntimeError(READ_MIGRATION_ERROR) from None
    if exists:
        raise ValueError(DUPLICATE_NAME_ERROR)


async def _assert_count_available(*, user_id: int, config: FilterSchemeConfig) -> None:
    """检查个人方案数量上限。"""
    try:
        count = await UserFilterScheme.filter(
            user_id=user_id,
            page_code=config.page_code,
            list_key=config.list_key,
            visibility=FilterSchemeVisibility.PERSONAL,
        ).count()
    except Exception:
        logger.exception("统计过滤方案数量失败")
        raise RuntimeError(READ_MIGRATION_ERROR) from None
    if count >= config.max_scheme_count:
        raise ValueError(f"个人过滤方案最多保存{config.max_scheme_count}个")


async def _next_personal_sort_order(*, user_id: int, config: FilterSchemeConfig) -> int:
    """个人方案新建时的显示顺序。"""
    try:
        row = await UserFilterScheme.filter(
            user_id=user_id,
            page_code=config.page_code,
            list_key=config.list_key,
            visibility=FilterSchemeVisibility.PERSONAL,
        ).order_by("-sort_order").first()
    except Exception:
        logger.exception("读取过滤方案顺序失败")
        raise RuntimeError(READ_MIGRATION_ERROR) from None
    return int(row.sort_order or 0) + 1 if row is not None else 1
