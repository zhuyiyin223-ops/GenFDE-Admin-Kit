"""系统能力：列头筛选的条件归一化与 Q 编译。

无 NiceGUI。字符串列：空值与关键词互斥，多个关键词空格分隔按 OR 命中；日期列：空值、快捷区间或绝对起止互斥；数字列：空值与闭区间互斥，缺一端则为 ≥ 或 ≤；选择列（布尔与枚举同一套）：多选值 OR，与空值互斥。多列之间 AND。
关联展示列声明 relation，或用 related_text_spec 声明逻辑外键展示列：
交互仍按 kind（默认字符串），查询按中间表/从表反查主表 id，空值表示没有任何关联行。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import isfinite
from typing import Any

from tortoise.expressions import Q, Subquery
from tortoise.models import Model

from modules.keyword_search.service import split_keywords


class ColumnFilterKind:
    """列筛选值类型。"""

    STRING = "string"
    DATE = "date"
    NUMBER = "number"
    SELECT = "select"


class ColumnFilterValueType:
    """选择列选项的取值类型。"""

    STR = "str"
    INT = "int"
    BOOL = "bool"


_UNSET = object()


DATE_SHORTCUTS: tuple[tuple[str, str], ...] = (
    ("today", "今日"),
    ("yesterday", "昨日"),
    ("last_3_days", "近3日"),
    ("last_week", "近1周"),
    ("this_month", "当月"),
    ("last_month", "上月"),
)
DATE_SHORTCUT_LABELS = dict(DATE_SHORTCUTS)


@dataclass(frozen=True)
class ColumnFilterOption:
    """选择列的一个选项：存储键与展示文案。"""

    value: str
    label: str


@dataclass(frozen=True)
class ColumnFilterRelation:
    """逻辑外键关联：按关联表文本筛主表，空值表示没有任何关联行。

    不要求 ORM 声明关系。单跳只填 through_model（从表即搜索对象）；
    双跳再填 related_model / related_fk（先命中关联实体，再经中间表反查主表）。
    """

    through_model: type[Model]
    owner_fk: str
    related_fields: tuple[str, ...]
    related_model: type[Model] | None = None
    related_fk: str = ""
    owner_field: str = "id"


@dataclass(frozen=True)
class ColumnFilterSpec:
    """一列筛选的声明。主表字段用 fields；关联展示列用 relation。"""

    name: str
    label: str
    fields: tuple[str, ...] = ()
    placeholder: str = ""
    kind: str = ColumnFilterKind.STRING
    options: tuple[ColumnFilterOption, ...] = ()
    value_type: str = ColumnFilterValueType.STR
    relation: ColumnFilterRelation | None = None

    def input_placeholder(self) -> str:
        """弹窗输入框占位文案。"""
        text = str(self.placeholder or "").strip()
        return text or f"搜索{self.label}（多个关键词用空格分隔）"

    def is_date(self) -> bool:
        """是否为日期列筛选。"""
        return self.kind == ColumnFilterKind.DATE

    def is_number(self) -> bool:
        """是否为数字列筛选。"""
        return self.kind == ColumnFilterKind.NUMBER

    def is_select(self) -> bool:
        """是否为选择列筛选（布尔与枚举共用）。"""
        return self.kind == ColumnFilterKind.SELECT

    def is_related(self) -> bool:
        """是否按关联表反查主表。"""
        return self.relation is not None

    def option_map(self) -> dict[str, str]:
        """选项键到展示文案。"""
        return {opt.value: opt.label for opt in self.options if opt.value}

    def match_blank_empty(self) -> bool:
        """空值筛选是否同时匹配空串。"""
        if self.is_related() or self.is_date() or self.is_number():
            return False
        if self.is_select():
            return self.value_type == ColumnFilterValueType.STR
        return True


@dataclass(frozen=True)
class ColumnFilterValue:
    """单列筛选取值。

    字符串为空值或空格分隔关键词；日期为空值、快捷区间或起止日期；
    数字为空值或闭区间；选择列为空值或多选键。
    """

    keyword: str = ""
    empty: bool = False
    shortcut: str = ""
    start: str = ""
    end: str = ""
    selected: tuple[str, ...] = ()
    selected_labels: tuple[str, ...] = ()

    def normalized(self) -> ColumnFilterValue:
        """空值优先；其次多选；日期优先快捷区间；数字保留闭区间；否则按空白拆分关键词。"""
        if bool(self.empty):
            return ColumnFilterValue(keyword="", empty=True)
        selected, labels = normalize_selected(self.selected, self.selected_labels)
        if selected:
            return ColumnFilterValue(selected=selected, selected_labels=labels)
        shortcut = str(self.shortcut or "").strip()
        if shortcut in DATE_SHORTCUT_LABELS:
            return ColumnFilterValue(shortcut=shortcut)
        start_day = parse_iso_date(self.start)
        end_day = parse_iso_date(self.end)
        if start_day is not None or end_day is not None:
            if start_day is not None and end_day is not None and start_day > end_day:
                start_day, end_day = end_day, start_day
            return ColumnFilterValue(
                start="" if start_day is None else start_day.isoformat(),
                end="" if end_day is None else end_day.isoformat(),
            )
        start_num = parse_number(self.start)
        end_num = parse_number(self.end)
        if start_num is not None or end_num is not None:
            if start_num is not None and end_num is not None and start_num > end_num:
                start_num, end_num = end_num, start_num
            return ColumnFilterValue(
                start="" if start_num is None else format_number(start_num),
                end="" if end_num is None else format_number(end_num),
            )
        terms = split_keywords(self.keyword)
        if terms:
            return ColumnFilterValue(keyword=" ".join(terms), empty=False)
        return ColumnFilterValue()

    def is_active(self) -> bool:
        """是否构成有效筛选。"""
        value = self.normalized()
        return value.empty or bool(
            value.keyword or value.shortcut or value.start or value.end or value.selected
        )

    def chip_text(self, spec: ColumnFilterSpec | None = None) -> str:
        """芯片右侧展示文案。"""
        value = self.normalized()
        if value.empty:
            return "空值"
        if value.selected:
            mapping = spec.option_map() if spec is not None else {}
            texts: list[str] = []
            for index, key in enumerate(value.selected):
                if key in mapping:
                    texts.append(mapping[key])
                elif index < len(value.selected_labels) and value.selected_labels[index]:
                    texts.append(value.selected_labels[index])
                else:
                    texts.append(key)
            return "、".join(texts)
        if value.shortcut:
            return DATE_SHORTCUT_LABELS[value.shortcut]
        if value.start and value.end:
            if value.start == value.end:
                return value.start
            return f"{value.start} 至 {value.end}"
        if value.start:
            if parse_iso_date(value.start) is not None:
                return f"{value.start} 起"
            return f"≥ {value.start}"
        if value.end:
            if parse_iso_date(value.end) is not None:
                return f"{value.end} 止"
            return f"≤ {value.end}"
        return value.keyword


def app_today() -> date:
    """当天日期（naive 墙钟）。"""
    return datetime.now().date()


def parse_number(raw: Any) -> float | None:
    """解析数字；非法或非有限值返回 None。"""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        if not isfinite(raw):
            return None
        if raw.is_integer():
            return int(raw)
        return raw
    text = str(raw or "").strip().replace(",", "")
    if not text:
        return None
    try:
        if any(marker in text for marker in (".", "e", "E")):
            value = float(text)
            if not isfinite(value):
                return None
            if value.is_integer():
                return int(value)
            return value
        return int(text, 10)
    except ValueError:
        return None


def format_number(value: float) -> str:
    """把数字格式化为筛选快照字符串。"""
    if isinstance(value, bool):
        return ""
    if isinstance(value, int):
        return str(value)
    if value.is_integer():
        return str(int(value))
    return f"{value:.10f}".rstrip("0").rstrip(".")


def resolved_number_range(value: ColumnFilterValue) -> tuple[float | None, float | None]:
    """把数字筛选取值展开为闭区间。"""
    normalized = value.normalized()
    return parse_number(normalized.start), parse_number(normalized.end)


def parse_iso_date(raw: Any) -> date | None:
    """解析 YYYY-MM-DD；非法则返回 None。"""
    text = str(raw or "").strip()
    if len(text) != 10:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def date_range_for_shortcut(shortcut: str, *, today: date | None = None) -> tuple[date, date] | None:
    """把快捷区间展开为闭区间起止日期。"""
    today_value = today or app_today()
    key = str(shortcut or "").strip()
    if key == "today":
        return today_value, today_value
    if key == "yesterday":
        day = today_value - timedelta(days=1)
        return day, day
    if key == "last_3_days":
        return today_value - timedelta(days=2), today_value
    if key == "last_week":
        return today_value - timedelta(days=6), today_value
    if key == "this_month":
        return _month_bounds(today_value.year, today_value.month)
    if key == "last_month":
        first_this_month = today_value.replace(day=1)
        last_prev = first_this_month - timedelta(days=1)
        return _month_bounds(last_prev.year, last_prev.month)
    return None


def match_date_shortcut(start: date, end: date, *, today: date | None = None) -> str:
    """若绝对区间恰好等于某个快捷区间，返回其 key。"""
    today_value = today or app_today()
    for key, _label in DATE_SHORTCUTS:
        bounds = date_range_for_shortcut(key, today=today_value)
        if bounds == (start, end):
            return key
    return ""


def resolved_date_range(
    value: ColumnFilterValue,
    *,
    today: date | None = None,
) -> tuple[date | None, date | None]:
    """把日期筛选取值展开为闭区间；快捷区间按当天计算。"""
    normalized = value.normalized()
    today_value = today or app_today()
    if normalized.shortcut:
        bounds = date_range_for_shortcut(normalized.shortcut, today=today_value)
        if bounds is None:
            return None, None
        return bounds
    return parse_iso_date(normalized.start), parse_iso_date(normalized.end)


def parse_column_filter_value(raw: Any) -> ColumnFilterValue:
    """把快照解码为列筛选取值。"""
    if isinstance(raw, ColumnFilterValue):
        return raw.normalized()
    if isinstance(raw, dict):
        return ColumnFilterValue(
            keyword=str(raw.get("keyword") or ""),
            empty=bool(raw.get("empty")),
            shortcut=str(raw.get("shortcut") or ""),
            start=_first_present(raw, "start", "from", "min"),
            end=_first_present(raw, "end", "to", "max"),
            selected=_parse_selected(raw.get("selected") if "selected" in raw else raw.get("values")),
            selected_labels=_parse_label_list(raw.get("labels")),
        ).normalized()
    if isinstance(raw, str):
        return ColumnFilterValue(keyword=raw).normalized()
    return ColumnFilterValue()


def dump_column_filter_value(
    value: ColumnFilterValue,
    spec: ColumnFilterSpec | None = None,
) -> dict[str, Any] | None:
    """把列筛选取值编码为可序列化快照；未生效返回 None。"""
    normalized = value.normalized()
    if spec is not None and spec.is_select() and normalized.selected:
        normalized = selected_value_for_spec(spec, normalized.selected)
    if not normalized.is_active():
        return None
    if normalized.empty:
        return {"keyword": "", "empty": True}
    if normalized.selected:
        payload: dict[str, Any] = {
            "kind": ColumnFilterKind.SELECT,
            "selected": list(normalized.selected),
        }
        if normalized.selected_labels:
            payload["labels"] = list(normalized.selected_labels)
        return payload
    if normalized.shortcut:
        return {"kind": ColumnFilterKind.DATE, "shortcut": normalized.shortcut}
    if normalized.start or normalized.end:
        kind = (
            ColumnFilterKind.DATE
            if parse_iso_date(normalized.start) is not None or parse_iso_date(normalized.end) is not None
            else ColumnFilterKind.NUMBER
        )
        payload = {"kind": kind}
        if normalized.start:
            payload["start"] = normalized.start
        if normalized.end:
            payload["end"] = normalized.end
        return payload
    return {"keyword": normalized.keyword, "empty": False}


def active_column_filters(
    values: Mapping[str, ColumnFilterValue] | None,
) -> dict[str, ColumnFilterValue]:
    """只返回已生效的列筛选。"""
    result: dict[str, ColumnFilterValue] = {}
    for name, raw in dict(values or {}).items():
        key = str(name or "").strip()
        if not key:
            continue
        value = raw.normalized() if isinstance(raw, ColumnFilterValue) else ColumnFilterValue()
        if value.is_active():
            result[key] = value
    return result


def apply_column_filter_q(
    query: Q,
    specs: Sequence[ColumnFilterSpec],
    values: Mapping[str, ColumnFilterValue] | None,
) -> Q:
    """把列筛选 AND 进已有 Q；无生效条件时原样返回。"""
    part = build_column_filter_q(specs, values)
    if part is None:
        return query
    return query & part


def build_column_filter_q(
    specs: Sequence[ColumnFilterSpec],
    values: Mapping[str, ColumnFilterValue] | None,
) -> Q | None:
    """把列筛选编译为 Q：列之间 AND。

    字符串列：空格分隔的多个关键词之间 OR，字段之间 OR；空值 AND。
    日期列：空值为字段 IS NULL；否则多字段区间 OR，按当天展开快捷区间，右开到次日零点。
    数字列：空值为字段 IS NULL；否则闭区间，缺左为 ≤、缺右为 ≥，多字段 OR。
    选择列：空值为字段 IS NULL（字符串选项同时匹配空串）；否则选项值 IN，多字段 OR。
    关联展示列：空值为没有任何中间表/从表行；关键词按关联文本 icontains 反查主表 id。
    无生效条件时返回 None，调用方不要把它当成空 Q 去 OR。
    """
    spec_map = {spec.name: spec for spec in specs if spec.name}
    combined: Q | None = None
    today_value = app_today()
    for name, value in active_column_filters(values).items():
        spec = spec_map.get(name)
        if spec is None:
            continue
        part = _column_q(spec, value, today=today_value)
        if part is None:
            continue
        combined = part if combined is None else combined & part
    return combined


def _column_q(spec: ColumnFilterSpec, value: ColumnFilterValue, *, today: date) -> Q | None:
    """编译单列条件。"""
    if spec.is_related():
        return _relation_column_q(spec, value)
    field_names = [str(name or "").strip() for name in spec.fields if str(name or "").strip()]
    if not field_names:
        return None
    if value.empty:
        return _empty_column_q(field_names, match_blank=spec.match_blank_empty())
    if spec.is_date():
        return _date_column_q(field_names, value, today=today)
    if spec.is_number():
        return _number_column_q(field_names, value)
    if spec.is_select():
        return _select_column_q(field_names, spec, value)
    terms = split_keywords(value.keyword)
    if not terms:
        return None
    contains: Q | None = None
    for term in terms:
        term_q: Q | None = None
        for field_name in field_names:
            field_q = Q(**{f"{field_name}__icontains": term})
            term_q = field_q if term_q is None else term_q | field_q
        contains = term_q if contains is None else contains | term_q
    return contains


def _relation_column_q(spec: ColumnFilterSpec, value: ColumnFilterValue) -> Q | None:
    """编译关联展示列：关键词命中关联文本，空值表示无关联行。"""
    relation = spec.relation
    if relation is None:
        return None
    owner_field = str(relation.owner_field or "id").strip() or "id"
    owner_fk = str(relation.owner_fk or "").strip()
    if not owner_fk:
        return None
    if value.empty:
        assigned = relation.through_model.all().values(owner_fk)
        return Q(**{f"{owner_field}__not_in": Subquery(assigned)})
    if spec.is_date() or spec.is_number() or spec.is_select():
        return None
    related_fields = [
        str(name or "").strip() for name in relation.related_fields if str(name or "").strip()
    ]
    terms = split_keywords(value.keyword)
    if not related_fields or not terms:
        return None
    term_q: Q | None = None
    for term in terms:
        for field_name in related_fields:
            field_q = Q(**{f"{field_name}__icontains": term})
            term_q = field_q if term_q is None else term_q | field_q
    if term_q is None:
        return None
    owner_ids = _related_owner_values(relation, term_q)
    if owner_ids is None:
        return None
    return Q(**{f"{owner_field}__in": Subquery(owner_ids)})


def _related_owner_values(relation: ColumnFilterRelation, term_q: Q) -> Any | None:
    """按关联文本条件取出中间表/从表上的主表外键查询。"""
    owner_fk = str(relation.owner_fk or "").strip()
    if relation.related_model is None:
        return relation.through_model.filter(term_q).values(owner_fk)
    related_fk = str(relation.related_fk or "").strip()
    if not related_fk:
        return None
    pk_attr = str(relation.related_model._meta.pk_attr or "id").strip() or "id"
    related_ids = relation.related_model.filter(term_q).values(pk_attr)
    return relation.through_model.filter(
        **{f"{related_fk}__in": Subquery(related_ids)}
    ).values(owner_fk)


def _empty_column_q(field_names: Sequence[str], *, match_blank: bool) -> Q | None:
    """编译空值条件：默认只匹配 NULL；match_blank 时同时匹配空串。"""
    empty_q: Q | None = None
    for field_name in field_names:
        field_empty = Q(**{f"{field_name}__isnull": True})
        if match_blank:
            field_empty = field_empty | Q(**{field_name: ""})
        empty_q = field_empty if empty_q is None else empty_q & field_empty
    return empty_q


def _select_column_q(
    field_names: Sequence[str],
    spec: ColumnFilterSpec,
    value: ColumnFilterValue,
) -> Q | None:
    """编译选择列条件：字段值属于所选选项。"""
    decoded = decode_selected_values(spec, value.selected)
    if not decoded:
        return None
    combined: Q | None = None
    for field_name in field_names:
        field_q = Q(**{f"{field_name}__in": decoded})
        combined = field_q if combined is None else combined | field_q
    return combined


def _number_column_q(field_names: Sequence[str], value: ColumnFilterValue) -> Q | None:
    """编译数字列条件：闭区间 [start, end]，缺一端则为 ≥ 或 ≤。"""
    start, end = resolved_number_range(value)
    if start is None and end is None:
        return None
    combined: Q | None = None
    for field_name in field_names:
        field_q: Q | None = None
        if start is not None:
            field_q = Q(**{f"{field_name}__gte": start})
        if end is not None:
            end_q = Q(**{f"{field_name}__lte": end})
            field_q = end_q if field_q is None else field_q & end_q
        if field_q is None:
            continue
        combined = field_q if combined is None else combined | field_q
    return combined


def _date_column_q(field_names: Sequence[str], value: ColumnFilterValue, *, today: date) -> Q | None:
    """编译日期列条件：闭开区间 [start, end+1day)。"""
    start, end = resolved_date_range(value, today=today)
    if start is None and end is None:
        return None
    start_dt = _day_start(start) if start is not None else None
    end_dt = _day_start(end) + timedelta(days=1) if end is not None else None
    combined: Q | None = None
    for field_name in field_names:
        field_q = Q()
        if start_dt is not None:
            field_q &= Q(**{f"{field_name}__gte": start_dt})
        if end_dt is not None:
            field_q &= Q(**{f"{field_name}__lt": end_dt})
        combined = field_q if combined is None else combined | field_q
    return combined


def related_text_spec(
    *,
    name: str,
    label: str,
    related_model: type[Model],
    related_fields: Sequence[str],
    owner_field: str,
    related_pk: str = "",
) -> ColumnFilterSpec:
    """声明逻辑外键展示列的字符串筛选。

    主表只有外键、展示文本在关联表时使用，例如操作日志的姓名、账号。
    交互复用字符串弹窗，按关联文本反查主表；空值表示没有任何关联行。
    """
    fields = tuple(str(item or "").strip() for item in related_fields if str(item or "").strip())
    pk_name = str(related_pk or "").strip() or str(related_model._meta.pk_attr or "id").strip() or "id"
    return ColumnFilterSpec(
        name=name,
        label=label,
        relation=ColumnFilterRelation(
            through_model=related_model,
            owner_fk=pk_name,
            related_fields=fields,
            owner_field=str(owner_field or "").strip(),
        ),
    )


def options_from_mapping(mapping: Mapping[Any, str]) -> tuple[ColumnFilterOption, ...]:
    """把取值到文案的映射转为选择列选项。"""
    items: list[ColumnFilterOption] = []
    seen: set[str] = set()
    for raw_key, raw_label in dict(mapping).items():
        key = encode_select_key(raw_key)
        label = str(raw_label or "").strip()
        if not key or not label or key in seen:
            continue
        seen.add(key)
        items.append(ColumnFilterOption(value=key, label=label))
    return tuple(items)


def selected_value_for_spec(spec: ColumnFilterSpec, keys: Sequence[str]) -> ColumnFilterValue:
    """按声明选项裁剪多选键，并补上文案。"""
    mapping = spec.option_map()
    selected: list[str] = []
    labels: list[str] = []
    seen: set[str] = set()
    for raw in keys:
        key = str(raw or "").strip()
        if not key or key in seen or key not in mapping:
            continue
        seen.add(key)
        selected.append(key)
        labels.append(mapping[key])
    if not selected:
        return ColumnFilterValue()
    return ColumnFilterValue(selected=tuple(selected), selected_labels=tuple(labels))


def encode_select_key(value: Any) -> str:
    """把选项原始值编码为存储键。"""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip()


def decode_selected_values(spec: ColumnFilterSpec, keys: Sequence[str]) -> list[Any]:
    """把多选键解码为查询取值，跳过未知或非法项。"""
    allowed = set(spec.option_map())
    decoded: list[Any] = []
    for raw in keys:
        key = str(raw or "").strip()
        if not key or key not in allowed:
            continue
        value = decode_select_value(key, value_type=spec.value_type)
        if value is _UNSET:
            continue
        decoded.append(value)
    return decoded


def decode_select_value(raw: str, *, value_type: str) -> Any:
    """把单个选项键解码为字段取值。"""
    key = str(raw or "").strip()
    if value_type == ColumnFilterValueType.BOOL:
        if key == "true":
            return True
        if key == "false":
            return False
        return _UNSET
    if value_type == ColumnFilterValueType.INT:
        try:
            return int(key, 10)
        except ValueError:
            return _UNSET
    return key or _UNSET


def normalize_selected(
    selected: Sequence[str] | None,
    labels: Sequence[str] | None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """去空、去重并保序；文案与键对齐。"""
    keys: list[str] = []
    texts: list[str] = []
    seen: set[str] = set()
    label_list = [str(item or "").strip() for item in tuple(labels or ())]
    for index, raw in enumerate(tuple(selected or ())):
        key = str(raw or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        keys.append(key)
        if index < len(label_list) and label_list[index]:
            texts.append(label_list[index])
        else:
            texts.append(key)
    return tuple(keys), tuple(texts)


def _parse_selected(raw: Any) -> tuple[str, ...]:
    """从快照读取多选键，去空去重保序。"""
    if raw is None or raw == "":
        return ()
    if isinstance(raw, str):
        text = raw.strip()
        return (text,) if text else ()
    if isinstance(raw, (list, tuple, set)):
        keys: list[str] = []
        seen: set[str] = set()
        for item in raw:
            if isinstance(item, dict):
                key = str(item.get("value") or item.get("key") or "").strip()
            else:
                key = str(item).strip()
            if not key or key in seen:
                continue
            seen.add(key)
            keys.append(key)
        return tuple(keys)
    return ()


def _parse_label_list(raw: Any) -> tuple[str, ...]:
    """从快照读取与多选键对齐的文案，不去重。"""
    if not isinstance(raw, (list, tuple)):
        return ()
    return tuple(str(item or "").strip() for item in raw)


def _first_present(raw: Mapping[str, Any], *keys: str) -> str:
    """按候选键读取第一个非空取值，0 视为有效。"""
    for key in keys:
        if key not in raw:
            continue
        value = raw[key]
        if value is None or value == "":
            continue
        return str(value).strip()
    return ""


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    """返回指定年月的首末日。"""
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def _day_start(day: date) -> datetime:
    """把日期转为当天零点。"""
    return datetime(day.year, day.month, day.day)
