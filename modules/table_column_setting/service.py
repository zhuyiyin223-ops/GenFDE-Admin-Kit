"""系统能力：表格列显示偏好的读写与归一化。

按账号持久化页面表格列偏好，并兼容列删除、改名和新增。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from models import UserTablePreference


@dataclass(frozen=True)
class TableColumnSettingConfig:
    """表格列偏好配置。"""

    page_code: str
    table_key: str
    allowed_column_names: Sequence[str]
    required_column_names: Sequence[str]
    default_visible_column_names: Sequence[str]
    column_name_aliases: dict[str, str] | None = None


class TableColumnSettingService:
    """表格列显示偏好的读写与归一化。"""

    @staticmethod
    def normalize_visible_column_names(
        column_names: Sequence[str] | None,
        *,
        config: TableColumnSettingConfig,
    ) -> list[str]:
        """归一化可见列编码列表。"""
        allowed_names = {
            str(name or "").strip()
            for name in config.allowed_column_names
            if str(name or "").strip()
        }
        aliases = {
            str(raw_name or "").strip(): str(target_name or "").strip()
            for raw_name, target_name in (config.column_name_aliases or {}).items()
            if str(raw_name or "").strip() and str(target_name or "").strip()
        }
        required_names = [
            str(name or "").strip()
            for name in config.required_column_names
            if str(name or "").strip() and str(name or "").strip() in allowed_names
        ]

        normalized_optional_names: list[str] = []
        for raw_name in column_names or []:
            column_name = aliases.get(str(raw_name or "").strip(), str(raw_name or "").strip())
            if (
                column_name
                and column_name in allowed_names
                and column_name not in required_names
                and column_name not in normalized_optional_names
            ):
                normalized_optional_names.append(column_name)
        return required_names + normalized_optional_names

    @staticmethod
    async def get_user_visible_column_names(
        *,
        user_id: int | None,
        config: TableColumnSettingConfig,
    ) -> list[str]:
        """读取当前账号的表格可见列配置。"""
        normalized_default_names = TableColumnSettingService.normalize_visible_column_names(
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

        normalized_names = TableColumnSettingService.normalize_visible_column_names(
            raw_visible_column_names if raw_visible_column_names is not None else config.default_visible_column_names,
            config=config,
        )
        normalized_known_names = TableColumnSettingService.normalize_visible_column_names(
            raw_known_column_names,
            config=config,
        )
        if raw_known_column_names is not None:
            for column_name in normalized_default_names:
                if column_name not in normalized_known_names and column_name not in normalized_names:
                    normalized_names.append(column_name)
        return normalized_names or normalized_default_names

    @staticmethod
    async def save_user_visible_column_names(
        *,
        user_id: int | None,
        visible_column_names: Sequence[str],
        config: TableColumnSettingConfig,
    ) -> list[str]:
        """保存当前账号的表格可见列配置。"""
        normalized_names = TableColumnSettingService.normalize_visible_column_names(
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
                        "known_column_names": TableColumnSettingService.normalize_visible_column_names(
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
