"""系统能力：模糊搜索关键词拆分与 OR 查询。

空格分隔的多个关键词之间为 OR；单个关键词命中任一声明字段即匹配。
数字、时间等非字符串字段按文本包含匹配；布尔/枚举可按展示文案反查。
不访问具体业务表。
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any

from tortoise.expressions import Q
from tortoise.fields import DatetimeField
from tortoise.models import Model

MAX_KEYWORD_COUNT = 10
STATUS_LABELS: dict[bool, str] = {True: "正常", False: "禁用"}
YES_NO_LABELS: dict[bool, str] = {True: "是", False: "否"}
_NUMERIC_UNIT_RE = re.compile(r"^([+-]?\d+(?:\.\d+)?)(ms|s)$", re.IGNORECASE)


def split_keywords(raw: str | None) -> list[str]:
    """按空白拆分关键词，去空、按小写去重并保序。"""
    terms: list[str] = []
    seen: set[str] = set()
    for part in str(raw or "").split():
        term = part.strip()
        if not term:
            continue
        folded = term.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        terms.append(term)
        if len(terms) >= MAX_KEYWORD_COUNT:
            break
    return terms


def or_q(*parts: Q | None) -> Q | None:
    """OR 合并多个可空 Q；全空则返回 None，避免空 Q 匹配全部行。"""
    combined: Q | None = None
    for part in parts:
        if part is None:
            continue
        combined = part if combined is None else combined | part
    return combined


def build_keyword_q(
    fields: Sequence[str],
    keyword: str | None,
    *,
    model: type[Model] | None = None,
    labels: Mapping[str, Mapping[Any, str]] | None = None,
) -> Q | None:
    """把关键词编译为 Tortoise Q：关键词之间 OR，字段之间 OR。

    声明字段一律按文本包含匹配（数据库会把数字/时间 CAST 成文本）。
    时间字段额外按页面展示格式解析区间；labels 把展示文案反查到字段取值。
    无关键词或无字段时返回 None，调用方不要把它当成空 Q 去 OR。
    """
    terms = split_keywords(keyword)
    field_names = [str(name or "").strip() for name in fields if str(name or "").strip()]
    label_map = {
        str(name or "").strip(): mapping
        for name, mapping in dict(labels or {}).items()
        if str(name or "").strip()
    }
    if not terms or not field_names:
        return None

    combined: Q | None = None
    for term in terms:
        term_q: Q | None = None
        for field_name in field_names:
            term_q = or_q(term_q, _field_contains_q(model, field_name, term))
        for field_name, mapping in label_map.items():
            term_q = or_q(term_q, _label_equals_q(field_name, mapping, term))
        combined = or_q(combined, term_q)
    return combined


def row_matches_keywords(values: Sequence[Any], keyword: str | None) -> bool:
    """内存侧按「任一关键词命中任一展示值」判断。"""
    terms = split_keywords(keyword)
    if not terms:
        return True
    haystacks = [_stringify_search_value(value) for value in values]
    return any(any(term.casefold() in haystack for haystack in haystacks) for term in terms)


def _search_stems(term: str) -> list[str]:
    """关键词本身，以及去掉 s/ms 单位后的数值词干。"""
    stems = [term]
    matched = _NUMERIC_UNIT_RE.fullmatch(term)
    if matched is None:
        return stems
    numeric = matched.group(1)
    if numeric and numeric not in stems:
        stems.append(numeric)
    return stems


def _parse_display_window(term: str) -> tuple[datetime, datetime] | None:
    """把页面时间展示文案解析为半开区间。"""
    text = str(term or "").strip().replace("T", " ")
    for fmt, delta in (
        ("%Y-%m-%d %H:%M:%S", timedelta(seconds=1)),
        ("%Y-%m-%d %H:%M", timedelta(minutes=1)),
        ("%Y-%m-%d", timedelta(days=1)),
    ):
        try:
            start = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return start, start + delta
    return None


def _resolve_model_field(model: type[Model] | None, field_name: str) -> Any:
    """沿关联路径解析字段对象，解析失败返回 None。"""
    if model is None:
        return None
    current: type[Model] = model
    parts = field_name.split("__")
    for index, part in enumerate(parts):
        field_obj = current._meta.fields_map.get(part)
        if field_obj is None:
            return None
        if index == len(parts) - 1:
            return field_obj
        related_model = getattr(field_obj, "related_model", None)
        if related_model is None:
            return None
        current = related_model
    return None


def _field_contains_q(model: type[Model] | None, field_name: str, term: str) -> Q:
    """单个字段的包含匹配，必要时叠加时间区间。"""
    contains: Q | None = None
    for stem in _search_stems(term):
        contains = or_q(contains, Q(**{f"{field_name}__icontains": stem}))
    field_obj = _resolve_model_field(model, field_name)
    if isinstance(field_obj, DatetimeField):
        window = _parse_display_window(term)
        if window is not None:
            start, end = window
            contains = or_q(
                contains,
                Q(**{f"{field_name}__gte": start}) & Q(**{f"{field_name}__lt": end}),
            )
    return contains if contains is not None else Q(**{f"{field_name}__icontains": term})


def _label_equals_q(field_name: str, mapping: Mapping[Any, str], term: str) -> Q | None:
    """展示文案包含关键词时，反查到对应字段取值。"""
    term_folded = term.casefold()
    values = [
        value
        for value, label in mapping.items()
        if term_folded in str(label).casefold()
    ]
    if not values:
        return None
    if len(values) == 1:
        return Q(**{field_name: values[0]})
    return Q(**{f"{field_name}__in": values})


def _stringify_search_value(value: Any) -> str:
    """把内存匹配值转成可包含匹配的文本。"""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M").casefold()
    if isinstance(value, bool):
        return str(value).casefold()
    return str(value).casefold()
