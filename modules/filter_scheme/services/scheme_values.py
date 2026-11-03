"""系统能力：过滤方案编解码。非事务，读写用例共用。

无 NiceGUI。按账号保存个人结构化筛选快照，不含关键字与分页，不可分享。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from models import UserFilterScheme
from modules.column_filter.services import dump_column_filter_value, parse_column_filter_value

VALUE_KIND_SCALAR = "scalar"

VALUE_KIND_DATE_RANGE = "date_range"

VALUE_KIND_COLUMN_FILTER = "column_filter"

DATE_RANGE_SEP = " - "

READ_MIGRATION_ERROR = "读取过滤方案失败，请先完成数据库迁移"

WRITE_MIGRATION_ERROR = "保存过滤方案失败，请先完成数据库迁移"

DUPLICATE_NAME_ERROR = "已存在同名过滤方案"

FORBIDDEN_SCHEME_ERROR = "无权修改该过滤方案"

EMPTY_SCHEME_ERROR = "当前没有可保存的筛选条件"

@dataclass(frozen=True)
class FilterSchemeField:
    """一个进入方案快照的结构化筛选项。"""

    key: str
    label: str
    default: Any = None
    value_kind: str = VALUE_KIND_SCALAR
    aliases: tuple[str, ...] = ()
    relative_days: int | None = None


@dataclass(frozen=True)
class FilterSchemeConfig:
    """某一列表表面的过滤方案配置。"""

    page_code: str
    list_key: str
    fields: Sequence[FilterSchemeField]
    max_scheme_count: int = 20
    max_name_length: int = 16


@dataclass(frozen=True)
class FilterScheme:
    """内存中的过滤方案。values 为存储形态。"""

    id: int
    name: str
    values: dict[str, Any]
    sort_order: int
    user_id: int


def stored_field_default(field: FilterSchemeField) -> Any:
    """返回字段的默认存储形态。"""
    if field.value_kind == VALUE_KIND_DATE_RANGE:
        if field.relative_days is not None:
            return {"mode": "relative", "days": int(field.relative_days)}
        return {"mode": "unbounded"}
    if field.value_kind == VALUE_KIND_COLUMN_FILTER:
        return None
    return field.default


def default_stored_values(config: FilterSchemeConfig) -> dict[str, Any]:
    """返回配置中全部字段的默认存储形态。"""
    return {field.key: stored_field_default(field) for field in config.fields}


def decode_field(raw: Any, *, field: FilterSchemeField, present: bool) -> Any:
    """将原始 JSON 值解码为该字段的存储形态。"""
    if field.value_kind == VALUE_KIND_DATE_RANGE:
        return _decode_date_range(raw, field=field, present=present)
    if field.value_kind == VALUE_KIND_COLUMN_FILTER:
        return _decode_column_filter(raw, present=present)
    return _decode_scalar(raw, field=field, present=present)


def normalize_values(raw: Any, *, config: FilterSchemeConfig) -> dict[str, Any]:
    """按字段声明归一化存储形态，丢弃未知 key。"""
    raw_values = raw if isinstance(raw, dict) else {}
    normalized: dict[str, Any] = {}
    for field in config.fields:
        extracted, present = _extract_raw(raw_values, field)
        normalized[field.key] = decode_field(extracted, field=field, present=present)
    return normalized


def encode_values(
    widget_values: dict[str, Any],
    *,
    config: FilterSchemeConfig,
    today: date | None = None,
) -> dict[str, Any]:
    """把控件形态编码为存储形态。"""
    today_value = today or date.today()
    raw_values = widget_values if isinstance(widget_values, dict) else {}
    encoded: dict[str, Any] = {}
    for field in config.fields:
        extracted, present = _extract_raw(raw_values, field)
        if field.value_kind == VALUE_KIND_DATE_RANGE:
            encoded[field.key] = _encode_date_range(
                extracted if present else None,
                field=field,
                today=today_value,
            )
            continue
        encoded[field.key] = decode_field(extracted, field=field, present=present)
    return encoded


def to_widget_values(
    stored_values: dict[str, Any],
    *,
    config: FilterSchemeConfig,
    today: date | None = None,
) -> dict[str, Any]:
    """把存储形态展开为控件形态。日期字段永远是 str。"""
    today_value = today or date.today()
    stored = normalize_values(stored_values, config=config)
    widget_values: dict[str, Any] = {}
    for field in config.fields:
        stored_value = stored.get(field.key)
        if field.value_kind == VALUE_KIND_DATE_RANGE:
            widget_values[field.key] = _date_range_to_widget(stored_value, today=today_value)
            continue
        widget_values[field.key] = stored_value
    return widget_values


def values_equal(left: Any, right: Any, *, config: FilterSchemeConfig) -> bool:
    """比较两份存储形态是否相等。"""
    return normalize_values(left, config=config) == normalize_values(
        right,
        config=config,
    )


def is_default_values(values: Any, *, config: FilterSchemeConfig) -> bool:
    """判断存储形态是否等于页面字段默认。"""
    return values_equal(
        values,
        default_stored_values(config),
        config=config,
    )


def describe_active_fields(values: Any, *, config: FilterSchemeConfig) -> list[tuple[str, str, str]]:
    """非默认条件：(字段 key, 标签, 文案)。"""
    stored = normalize_values(values, config=config)
    items: list[tuple[str, str, str]] = []
    for field in config.fields:
        text = _describe_field(field, stored.get(field.key))
        if text:
            items.append((field.key, field.label, text))
    return items


def describe_values(values: Any, *, config: FilterSchemeConfig) -> list[tuple[str, str]]:
    """把当前筛选整理为弹窗展示用的「标签 / 文案」列表，跳过默认值。"""
    return [
        (label, text)
        for _, label, text in describe_active_fields(values, config=config)
    ]


def normalize_name(name: str, *, config: FilterSchemeConfig) -> str:
    """校验并归一化方案名称。"""
    normalized = str(name or "").strip()
    if not normalized:
        raise ValueError("请填写方案名称")
    if len(normalized) > config.max_name_length:
        raise ValueError(f"方案名称不能超过{config.max_name_length}个字符")
    return normalized


def config_from_column_filters(
    *,
    page_code: str,
    list_key: str,
    specs: Sequence[Any],
) -> FilterSchemeConfig:
    """按列头筛选声明生成方案配置。"""
    fields = tuple(
        FilterSchemeField(
            key=str(getattr(spec, "name", "") or ""),
            label=str(getattr(spec, "label", "") or ""),
            value_kind=VALUE_KIND_COLUMN_FILTER,
        )
        for spec in specs
        if str(getattr(spec, "name", "") or "").strip()
    )
    return FilterSchemeConfig(page_code=page_code, list_key=list_key, fields=fields)


def _extract_raw(raw_values: dict[str, Any], field: FilterSchemeField) -> tuple[Any, bool]:
    """按字段 key 与 alias 取值。"""
    if field.key in raw_values:
        return raw_values[field.key], True
    for alias in field.aliases:
        if alias in raw_values:
            return raw_values[alias], True
    return None, False


def _decode_scalar(raw: Any, *, field: FilterSchemeField, present: bool) -> Any:
    """解码标量字段。"""
    if not present:
        return field.default
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float) and raw.is_integer():
        return int(raw)
    if isinstance(raw, float):
        return field.default
    if isinstance(raw, str):
        return raw
    return field.default


def _decode_column_filter(raw: Any, *, present: bool) -> dict[str, Any] | None:
    """解码列头筛选取值。"""
    if not present or raw is None or raw == "":
        return None
    return dump_column_filter_value(parse_column_filter_value(raw))


def _describe_field(field: FilterSchemeField, value: Any) -> str | None:
    """生成单个字段的展示文案；默认值返回 None。"""
    if field.value_kind == VALUE_KIND_COLUMN_FILTER:
        parsed = parse_column_filter_value(value)
        if not parsed.is_active():
            return None
        return parsed.chip_text()
    if field.value_kind == VALUE_KIND_DATE_RANGE:
        if not isinstance(value, dict):
            return None
        mode = str(value.get("mode") or "").strip()
        if mode == "unbounded":
            return None
        if mode == "relative":
            days = value.get("days")
            if isinstance(days, bool) or not isinstance(days, int):
                return None
            return f"近{days}天"
        if mode == "absolute":
            start_text = str(value.get("from") or "").strip()
            end_text = str(value.get("to") or "").strip()
            if start_text and end_text:
                return f"{start_text} 至 {end_text}"
        return None
    if value is None or value == "" or value == field.default:
        return None
    if isinstance(value, bool):
        return "是" if value else "否"
    return str(value)


def _decode_date_range(raw: Any, *, field: FilterSchemeField, present: bool) -> dict[str, Any]:
    """解码日期区间字段为存储形态。"""
    field_default = stored_field_default(field)
    if not present:
        return field_default
    if raw is None or raw == "":
        return {"mode": "unbounded"}
    if isinstance(raw, dict):
        mode = str(raw.get("mode") or "").strip()
        if mode == "unbounded":
            return {"mode": "unbounded"}
        if mode == "relative":
            days = raw.get("days")
            if isinstance(days, bool):
                return field_default
            if isinstance(days, float) and days.is_integer():
                days = int(days)
            if isinstance(days, int) and field.relative_days is not None and days == int(field.relative_days):
                return {"mode": "relative", "days": days}
            return field_default
        start_text = str(raw.get("from") or "").strip()
        end_text = str(raw.get("to") or "").strip()
        if _is_iso_date(start_text) and _is_iso_date(end_text):
            return {"mode": "absolute", "from": start_text, "to": end_text}
        return field_default
    if isinstance(raw, str):
        parsed = _parse_absolute_range(raw)
        if parsed is None:
            return field_default
        start, end = parsed
        return {"mode": "absolute", "from": start.isoformat(), "to": end.isoformat()}
    return field_default


def _encode_date_range(raw: Any, *, field: FilterSchemeField, today: date) -> dict[str, Any]:
    """把控件日期字符串编码为存储形态。"""
    if raw is None or str(raw).strip() == "":
        return {"mode": "unbounded"}
    if isinstance(raw, dict):
        return _decode_date_range(raw, field=field, present=True)
    parsed = _parse_absolute_range(str(raw))
    if parsed is None:
        return stored_field_default(field)
    start, end = parsed
    relative_days = field.relative_days
    if (
        relative_days is not None
        and start == today - timedelta(days=int(relative_days))
        and end == today
    ):
        return {"mode": "relative", "days": int(relative_days)}
    return {"mode": "absolute", "from": start.isoformat(), "to": end.isoformat()}


def _date_range_to_widget(stored_value: Any, *, today: date) -> str:
    """把日期存储形态展开为控件字符串。"""
    if not isinstance(stored_value, dict):
        return ""
    mode = str(stored_value.get("mode") or "").strip()
    if mode == "unbounded":
        return ""
    if mode == "relative":
        days = stored_value.get("days")
        if isinstance(days, bool) or not isinstance(days, int):
            return ""
        return _relative_range_text(today=today, days=days)
    if mode == "absolute":
        start_text = str(stored_value.get("from") or "").strip()
        end_text = str(stored_value.get("to") or "").strip()
        if _is_iso_date(start_text) and _is_iso_date(end_text):
            return f"{start_text}{DATE_RANGE_SEP}{end_text}"
    return ""


def _relative_range_text(*, today: date, days: int) -> str:
    """生成与页面默认日期区间相同的控件字符串。"""
    start = today - timedelta(days=int(days))
    return f"{start.isoformat()}{DATE_RANGE_SEP}{today.isoformat()}"


def _parse_absolute_range(raw: str) -> tuple[date, date] | None:
    """解析 'YYYY-MM-DD - YYYY-MM-DD'。"""
    text = str(raw or "").strip()
    if DATE_RANGE_SEP not in text:
        return None
    start_text, end_text = text.split(DATE_RANGE_SEP, 1)
    start_text, end_text = start_text.strip(), end_text.strip()
    if not _is_iso_date(start_text) or not _is_iso_date(end_text):
        return None
    try:
        return date.fromisoformat(start_text), date.fromisoformat(end_text)
    except ValueError:
        return None


def _is_iso_date(value: str) -> bool:
    """判断是否为 YYYY-MM-DD。"""
    if len(value) != 10:
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _to_scheme(row: UserFilterScheme, *, config: FilterSchemeConfig) -> FilterScheme:
    """把 ORM 行转为内存 DTO。"""
    return FilterScheme(
        id=int(row.id),
        name=str(row.name or ""),
        values=normalize_values(row.filter_values, config=config),
        sort_order=int(row.sort_order or 0),
        user_id=int(row.user_id or 0),
    )


def _scheme_sort_key(scheme: FilterScheme) -> tuple[int, int]:
    """个人方案按显示顺序排列。"""
    return (scheme.sort_order, scheme.id)
