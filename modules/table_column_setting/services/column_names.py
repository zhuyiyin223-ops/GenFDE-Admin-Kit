"""系统能力：表格列偏好的配置与列名归一化。非事务，读写用例共用。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class TableColumnSettingConfig:
    """表格列偏好配置。"""

    page_code: str
    table_key: str
    allowed_column_names: Sequence[str]
    required_column_names: Sequence[str]
    default_visible_column_names: Sequence[str]
    column_name_aliases: dict[str, str] | None = None


def normalize_visible_column_names(
    column_names: Sequence[str] | None,
    *,
    config: TableColumnSettingConfig,
) -> list[str]:
    """归一化可见列编码列表。"""
    allowed_names = {str(name or "").strip() for name in config.allowed_column_names if str(name or "").strip()}
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
