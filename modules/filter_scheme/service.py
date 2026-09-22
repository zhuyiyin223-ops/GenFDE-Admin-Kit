"""系统能力：列表过滤方案的读写、校验与编解码。

无 NiceGUI。按账号保存个人结构化筛选快照，不含关键字与分页，不可分享。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from loguru import logger
from tortoise.exceptions import IntegrityError, OperationalError

from models import FilterSchemeVisibility, UserFilterScheme, UserFilterSchemePref
from modules.column_filter.service import dump_column_filter_value, parse_column_filter_value

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


class FilterSchemeService:
    """过滤方案的读写、校验与编解码。"""

    @staticmethod
    def stored_field_default(field: FilterSchemeField) -> Any:
        """返回字段的默认存储形态。"""
        if field.value_kind == VALUE_KIND_DATE_RANGE:
            if field.relative_days is not None:
                return {"mode": "relative", "days": int(field.relative_days)}
            return {"mode": "unbounded"}
        if field.value_kind == VALUE_KIND_COLUMN_FILTER:
            return None
        return field.default

    @staticmethod
    def default_stored_values(config: FilterSchemeConfig) -> dict[str, Any]:
        """返回配置中全部字段的默认存储形态。"""
        return {field.key: FilterSchemeService.stored_field_default(field) for field in config.fields}

    @staticmethod
    def decode_field(raw: Any, *, field: FilterSchemeField, present: bool) -> Any:
        """将原始 JSON 值解码为该字段的存储形态。"""
        if field.value_kind == VALUE_KIND_DATE_RANGE:
            return _decode_date_range(raw, field=field, present=present)
        if field.value_kind == VALUE_KIND_COLUMN_FILTER:
            return _decode_column_filter(raw, present=present)
        return _decode_scalar(raw, field=field, present=present)

    @staticmethod
    def normalize_values(raw: Any, *, config: FilterSchemeConfig) -> dict[str, Any]:
        """按字段声明归一化存储形态，丢弃未知 key。"""
        raw_values = raw if isinstance(raw, dict) else {}
        normalized: dict[str, Any] = {}
        for field in config.fields:
            extracted, present = _extract_raw(raw_values, field)
            normalized[field.key] = FilterSchemeService.decode_field(extracted, field=field, present=present)
        return normalized

    @staticmethod
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
            encoded[field.key] = FilterSchemeService.decode_field(extracted, field=field, present=present)
        return encoded

    @staticmethod
    def to_widget_values(
        stored_values: dict[str, Any],
        *,
        config: FilterSchemeConfig,
        today: date | None = None,
    ) -> dict[str, Any]:
        """把存储形态展开为控件形态。日期字段永远是 str。"""
        today_value = today or date.today()
        stored = FilterSchemeService.normalize_values(stored_values, config=config)
        widget_values: dict[str, Any] = {}
        for field in config.fields:
            stored_value = stored.get(field.key)
            if field.value_kind == VALUE_KIND_DATE_RANGE:
                widget_values[field.key] = _date_range_to_widget(stored_value, today=today_value)
                continue
            widget_values[field.key] = stored_value
        return widget_values

    @staticmethod
    def values_equal(left: Any, right: Any, *, config: FilterSchemeConfig) -> bool:
        """比较两份存储形态是否相等。"""
        return FilterSchemeService.normalize_values(left, config=config) == FilterSchemeService.normalize_values(
            right,
            config=config,
        )

    @staticmethod
    def is_default_values(values: Any, *, config: FilterSchemeConfig) -> bool:
        """判断存储形态是否等于页面字段默认。"""
        return FilterSchemeService.values_equal(
            values,
            FilterSchemeService.default_stored_values(config),
            config=config,
        )

    @staticmethod
    def describe_active_fields(values: Any, *, config: FilterSchemeConfig) -> list[tuple[str, str, str]]:
        """非默认条件：(字段 key, 标签, 文案)。"""
        stored = FilterSchemeService.normalize_values(values, config=config)
        items: list[tuple[str, str, str]] = []
        for field in config.fields:
            text = _describe_field(field, stored.get(field.key))
            if text:
                items.append((field.key, field.label, text))
        return items

    @staticmethod
    def describe_values(values: Any, *, config: FilterSchemeConfig) -> list[tuple[str, str]]:
        """把当前筛选整理为弹窗展示用的「标签 / 文案」列表，跳过默认值。"""
        return [
            (label, text)
            for _, label, text in FilterSchemeService.describe_active_fields(values, config=config)
        ]

    @staticmethod
    def normalize_name(name: str, *, config: FilterSchemeConfig) -> str:
        """校验并归一化方案名称。"""
        normalized = str(name or "").strip()
        if not normalized:
            raise ValueError("请填写方案名称")
        if len(normalized) > config.max_name_length:
            raise ValueError(f"方案名称不能超过{config.max_name_length}个字符")
        return normalized

    @staticmethod
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

    @staticmethod
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
        normalized_name = FilterSchemeService.normalize_name(name, config=config)
        stored_values = FilterSchemeService.encode_values(values, config=config, today=today)
        if FilterSchemeService.is_default_values(stored_values, config=config):
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

    @staticmethod
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
        next_name = FilterSchemeService.normalize_name(name, config=config) if name is not None else str(row.name or "")
        if values is None:
            stored_values = FilterSchemeService.normalize_values(row.filter_values, config=config)
        else:
            stored_values = FilterSchemeService.encode_values(values, config=config, today=today)
        if FilterSchemeService.is_default_values(stored_values, config=config):
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

    @staticmethod
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


def _is_valid_user_id(user_id: int | None) -> bool:
    """判断登录账号 ID 是否可用。"""
    return isinstance(user_id, int) and user_id > 0


def _require_user_id(user_id: int | None) -> int:
    """写路径要求有效登录账号。"""
    if not _is_valid_user_id(user_id):
        raise ValueError("当前登录账号无效，无法保存过滤方案")
    return int(user_id)


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
    field_default = FilterSchemeService.stored_field_default(field)
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
        return FilterSchemeService.stored_field_default(field)
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
        values=FilterSchemeService.normalize_values(row.filter_values, config=config),
        sort_order=int(row.sort_order or 0),
        user_id=int(row.user_id or 0),
    )


def _scheme_sort_key(scheme: FilterScheme) -> tuple[int, int]:
    """个人方案按显示顺序排列。"""
    return (scheme.sort_order, scheme.id)


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
