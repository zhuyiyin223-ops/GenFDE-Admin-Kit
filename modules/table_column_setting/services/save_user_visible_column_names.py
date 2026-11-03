"""系统能力用例：保存当前账号的表格可见列。"""

from __future__ import annotations

from collections.abc import Sequence

from models import UserTablePreference

from .column_names import TableColumnSettingConfig, normalize_visible_column_names


async def save_user_visible_column_names(
    *,
    user_id: int | None,
    visible_column_names: Sequence[str],
    config: TableColumnSettingConfig,
) -> list[str]:
    """保存当前账号的表格可见列配置。"""
    normalized_names = normalize_visible_column_names(
        visible_column_names,
        config=config,
    )
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("当前登录账号无效，无法保存列设置")

    try:
        await UserTablePreference.update_or_create(
            defaults={
                "visible_column_names": {
                    "visible_column_names": normalized_names,
                    "known_column_names": normalize_visible_column_names(
                        config.allowed_column_names,
                        config=config,
                    ),
                }
            },
            user_id=user_id,
            page_code=config.page_code,
            table_key=config.table_key,
        )
    except Exception as exc:
        raise RuntimeError("保存列设置失败，请先完成数据库迁移") from exc
    return normalized_names
