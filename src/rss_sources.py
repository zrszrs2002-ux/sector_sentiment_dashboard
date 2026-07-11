"""Validated RSS source configuration and publisher helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable

from src.config import RSS_SOURCES_PATH


@dataclass(frozen=True)
class RssSource:
    name: str
    url: str
    kind: str
    source_weight: float
    enabled: bool
    max_entries: int
    fulltext_allowed: bool = True


def split_multi_value(value: object) -> set[str]:
    return {
        item.strip()
        for item in re.split(r"[;|]+", str(value or ""))
        if item.strip()
    }


@lru_cache(maxsize=1)
def load_rss_sources() -> list[RssSource]:
    try:
        payload = json.loads(RSS_SOURCES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"RSS 源配置读取失败：{exc}") from exc

    sources: list[RssSource] = []
    for index, item in enumerate(payload.get("sources", []), start=1):
        try:
            source = RssSource(
                name=str(item["name"]).strip(),
                url=str(item["url"]).strip(),
                kind=str(item["kind"]).strip(),
                source_weight=float(item.get("source_weight", 1.0)),
                enabled=bool(item.get("enabled", True)),
                max_entries=max(1, int(item.get("max_entries", 20))),
                fulltext_allowed=bool(item.get("fulltext_allowed", True)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"RSS 源配置第 {index} 项无效：{exc}") from exc
        if not source.name or not source.url or source.kind not in {"ticker_template", "market"}:
            raise RuntimeError(f"RSS 源配置第 {index} 项缺少名称/URL，或 kind 非法。")
        if not 0 < source.source_weight <= 1:
            raise RuntimeError(f"RSS 源 {source.name} 的 source_weight 必须在 (0, 1]。")
        sources.append(source)
    return sources


def enabled_rss_sources() -> list[RssSource]:
    return [source for source in load_rss_sources() if source.enabled]


def source_weight_for_names(value: object) -> float:
    configured = {source.name: source.source_weight for source in load_rss_sources()}
    weights = [configured.get(name, 1.0) for name in split_multi_value(value)]
    return max(weights, default=1.0)


def fulltext_allowed_for_names(value: object) -> bool:
    configured = {source.name: source.fulltext_allowed for source in load_rss_sources()}
    names = split_multi_value(value)
    return any(configured.get(name, False) for name in names)


def distinct_value_count(
    values: Iterable[object], fallback_values: Iterable[object] | None = None
) -> int:
    distinct: set[str] = set()
    primary = list(values)
    fallback = list(fallback_values) if fallback_values is not None else [""] * len(primary)
    for index, value in enumerate(primary):
        resolved = split_multi_value(value)
        if not resolved and index < len(fallback):
            resolved = split_multi_value(fallback[index])
        distinct.update(resolved)
    return len(distinct)
