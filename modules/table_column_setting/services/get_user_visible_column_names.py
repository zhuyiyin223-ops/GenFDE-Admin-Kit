"""系统能力用例：读取当前账号的表格可见列。"""

from __future__ import annotations

from collections.abc import Sequence

from models import UserTablePreference

from .column_names import TableColumnSettingConfig, normalize_visible_column_names


async def get_user_visible_column_names(
    *,
    user_id: int | None,
    config: TableColumnSettingConfig,
) -> list[str]:
    """读取当前账号的表格可见列配置。"""
    normalized_default_names = normalize_visible_column_names(
        config.default_visible_column_names,
        config=config,
    )
    if not isinstance(user_id, int) or user_id <= 0:
        return normalized_default_names

    try:
        preference = await UserTablePreference.filter(
            user_id=user_id,
            page_code=config.page_code,
            table_key=config.table_key,
        ).first()
    except Exception:
        return normalized_default_names

    storage_value = preference.visible_column_names if preference else None
    raw_visible_column_names: Sequence[str] | None = None
    raw_known_column_names: Sequence[str] | None = None
    if isinstance(storage_value, list):
        raw_visible_column_names = storage_value
    elif isinstance(storage_value, dict):
        visible_value = storage_value.get("visible_column_names")
        known_value = storage_value.get("known_column_names")
        raw_visible_column_names = visible_value if isinstance(visible_value, list) else None
        raw_known_column_names = known_value if isinstance(known_value, list) else None

    normalized_names = normalize_visible_column_names(
        raw_visible_column_names if raw_visible_column_names is not None else config.default_visible_column_names,
        config=config,
    )
    normalized_known_names = normalize_visible_column_names(
        raw_known_column_names,
        config=config,
    )
    if raw_known_column_names is not None:
        for column_name in normalized_default_names:
            if column_name not in normalized_known_names and column_name not in normalized_names:
                normalized_names.append(column_name)
    return normalized_names or normalized_default_names
