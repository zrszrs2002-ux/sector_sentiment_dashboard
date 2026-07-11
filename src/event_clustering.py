"""Event-level clustering for display-time article folding.

The module assigns persistent event IDs without changing article weights or the
six-dimensional aggregation. Embeddings are computed in memory only for
articles that participate in a 48-hour candidate pair.
"""

from __future__ import annotations

import argparse
from bisect import bisect_left, bisect_right
import html
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from src.config import (
    EVENT_EMBED_BATCH_SIZE,
    EVENT_EMBED_MODEL_NAME,
    EVENT_EMBED_THRESHOLD,
    EVENT_LEXICAL_THRESHOLD,
    EVENT_MAX_SPAN_HOURS,
    EVENT_POLARITY_GUARD_THRESHOLD,
    EVENT_SIMILARITY_ENGINE,
    EVENT_TIME_WINDOW_HOURS,
    EVENT_UNMAPPED_EMBED_THRESHOLD,
    EVENT_UNMAPPED_LEXICAL_THRESHOLD,
    REAL_PROCESSED_ARTICLES_PATH,
    get_hf_token,
)
from src.preprocessing import parse_utc_datetime, read_article_csv, write_article_csv
from src.sentiment_model import resolve_device


CONTENT_STOPWORDS = {
    "a", "about", "after", "again", "against", "all", "also", "an", "and", "any",
    "are", "as", "at", "be", "because", "been", "before", "being", "between", "but",
    "by", "can", "could", "did", "do", "does", "doing", "during", "each", "for",
    "from", "further", "had", "has", "have", "having", "he", "her", "here", "hers",
    "him", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself",
    "just", "may", "more", "most", "no", "nor", "not", "now", "of", "off", "on",
    "once", "only", "or", "other", "our", "out", "over", "own", "said", "same",
    "she", "should", "so", "some", "such", "than", "that", "the", "their", "them",
    "then", "there", "these", "they", "this", "those", "through", "to", "too", "under",
    "up", "very", "was", "we", "were", "what", "when", "where", "which", "while",
    "who", "why", "will", "with", "would", "you", "your",
}


class SimilarityIndex(Protocol):
    engine_name: str
    device: str

    def score(self, left_index: int, right_index: int) -> float:
        ...

    def is_similar(self, left_index: int, right_index: int, strict: bool = False) -> bool:
        ...


@dataclass(frozen=True)
class SimilarityBuild:
    index: SimilarityIndex
    requested_engine: str
    used_engine: str
    device: str
    fallback_reason: str = ""


@dataclass(frozen=True)
class ClusterRunInfo:
    requested_engine: str
    used_engine: str
    device: str
    fallback_reason: str
    incremental: bool
    candidate_pair_count: int
    matched_pair_count: int
    compared_article_count: int


@dataclass(frozen=True)
class ClusterResult:
    records: list[dict[str, str]]
    info: ClusterRunInfo


class UnionFind:
    def __init__(self, size: int, timestamps: list[float | None] | None = None) -> None:
        self.parent = list(range(size))
        self.rank = [0] * size
        values = timestamps or [None] * size
        self.min_timestamp = list(values)
        self.max_timestamp = list(values)

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int, max_span_hours: float | None = None) -> bool:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return True

        timestamps = [
            value
            for value in (
                self.min_timestamp[left_root],
                self.max_timestamp[left_root],
                self.min_timestamp[right_root],
                self.max_timestamp[right_root],
            )
            if value is not None
        ]
        merged_min = min(timestamps) if timestamps else None
        merged_max = max(timestamps) if timestamps else None
        if (
            max_span_hours is not None
            and merged_min is not None
            and merged_max is not None
            and merged_max - merged_min > max_span_hours * 3600
        ):
            return False
        if self.rank[left_root] < self.rank[right_root]:
            left_root, right_root = right_root, left_root
        self.parent[right_root] = left_root
        self.min_timestamp[left_root] = merged_min
        self.max_timestamp[left_root] = merged_max
        if self.rank[left_root] == self.rank[right_root]:
            self.rank[left_root] += 1
        return True


def _clean_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def event_text(record: dict[str, str]) -> str:
    title = _clean_text(record.get("title", ""))
    summary = _clean_text(record.get("summary", ""))
    if summary.lower() == title.lower():
        summary = ""
    return " ".join(part for part in (title, summary) if part).strip()


def content_tokens(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", text.lower())
    return {token for token in tokens if len(token) > 1 and token not in CONTENT_STOPWORDS}


class LexicalSimilarityIndex:
    engine_name = "lexical"
    device = "cpu"

    def __init__(self, texts: list[str]) -> None:
        self.tokens = [content_tokens(text) for text in texts]

    def score(self, left_index: int, right_index: int) -> float:
        left = self.tokens[left_index]
        right = self.tokens[right_index]
        if not left or not right:
            return 0.0
        return len(left & right) / len(left | right)

    def is_similar(self, left_index: int, right_index: int, strict: bool = False) -> bool:
        threshold = EVENT_UNMAPPED_LEXICAL_THRESHOLD if strict else EVENT_LEXICAL_THRESHOLD
        return self.score(left_index, right_index) >= threshold


class EmbeddingSimilarityIndex:
    engine_name = "embedding"

    def __init__(self, embeddings: np.ndarray, device: str) -> None:
        self.embeddings = np.asarray(embeddings, dtype=np.float32)
        self.device = device

    def score(self, left_index: int, right_index: int) -> float:
        value = float(np.dot(self.embeddings[left_index], self.embeddings[right_index]))
        return max(-1.0, min(1.0, value))

    def is_similar(self, left_index: int, right_index: int, strict: bool = False) -> bool:
        threshold = EVENT_UNMAPPED_EMBED_THRESHOLD if strict else EVENT_EMBED_THRESHOLD
        return self.score(left_index, right_index) >= threshold


@lru_cache(maxsize=3)
def _load_embedding_model(model_name: str, device: str, token: str) -> Any:
    from sentence_transformers import SentenceTransformer

    kwargs: dict[str, Any] = {"device": device}
    if token:
        kwargs["token"] = token
    return SentenceTransformer(model_name, **kwargs)


def _build_embedding_index(texts: list[str]) -> EmbeddingSimilarityIndex:
    import torch

    device = resolve_device(torch)
    model = _load_embedding_model(EVENT_EMBED_MODEL_NAME, device, get_hf_token())
    embeddings = model.encode(
        texts,
        batch_size=EVENT_EMBED_BATCH_SIZE,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return EmbeddingSimilarityIndex(embeddings, device)


def build_similarity_index(texts: list[str], engine: str | None = None) -> SimilarityBuild:
    requested = str(engine or EVENT_SIMILARITY_ENGINE).strip().lower()
    if requested == "lexical":
        print("当前事件聚类引擎：lexical（内容词 Jaccard）。")
        return SimilarityBuild(LexicalSimilarityIndex(texts), requested, "lexical", "cpu")
    if requested != "embedding":
        reason = f"未知事件相似度引擎 {requested!r}"
        print(f"{reason}，已回退 lexical。")
        return SimilarityBuild(LexicalSimilarityIndex(texts), requested, "lexical", "cpu", reason)

    try:
        index = _build_embedding_index(texts)
    except Exception as exc:  # noqa: BLE001 - optional model must not break the pipeline
        reason = f"{type(exc).__name__}: {exc}"[:300]
        print(f"事件 embedding 模型不可用，已回退 lexical：{reason}")
        return SimilarityBuild(LexicalSimilarityIndex(texts), requested, "lexical", "cpu", reason)

    print(f"当前事件聚类引擎：embedding ({index.device})，模型 {EVENT_EMBED_MODEL_NAME}。")
    return SimilarityBuild(index, requested, "embedding", index.device)


def split_tickers(value: object) -> set[str]:
    return {
        token.upper()
        for token in re.split(r"[;,|\s]+", str(value or ""))
        if token.strip()
    }


def split_sources(value: object) -> set[str]:
    return {
        source.strip()
        for source in re.split(r"[;|]+", str(value or ""))
        if source.strip()
    }


def _context_mode(left: dict[str, str], right: dict[str, str]) -> str | None:
    left_tickers = split_tickers(left.get("tickers", ""))
    right_tickers = split_tickers(right.get("tickers", ""))
    if left_tickers and right_tickers:
        return "normal" if left_tickers & right_tickers else None

    left_unmapped = str(left.get("sector", "")).strip() in {"", "Unmapped"}
    right_unmapped = str(right.get("sector", "")).strip() in {"", "Unmapped"}
    if not left_tickers and not right_tickers and left_unmapped and right_unmapped:
        return "strict"
    return None


def _published_timestamp(record: dict[str, str]) -> float | None:
    try:
        return parse_utc_datetime(record.get("published_at", "")).timestamp()
    except (TypeError, ValueError):
        return None


def _sentiment_score(record: dict[str, str]) -> float:
    try:
        return float(record.get("sentiment_score", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _has_polarity_conflict(left: dict[str, str], right: dict[str, str]) -> bool:
    left_score = _sentiment_score(left)
    right_score = _sentiment_score(right)
    threshold = EVENT_POLARITY_GUARD_THRESHOLD
    return (left_score > threshold and right_score < -threshold) or (
        right_score > threshold and left_score < -threshold
    )


def _candidate_pairs(
    records: list[dict[str, str]],
    new_indices: set[int] | None,
) -> list[tuple[int, int, bool]]:
    times = [_published_timestamp(record) for record in records]
    ordered = sorted((timestamp, index) for index, timestamp in enumerate(times) if timestamp is not None)
    window_seconds = EVENT_TIME_WINDOW_HOURS * 3600
    pairs: list[tuple[int, int, bool]] = []

    if new_indices is not None:
        if not new_indices:
            return pairs
        ordered_times = [timestamp for timestamp, _index in ordered]
        seen_pairs: set[tuple[int, int]] = set()
        time_by_index = {index: timestamp for timestamp, index in ordered}
        for new_index in new_indices:
            new_time = time_by_index.get(new_index)
            if new_time is None:
                continue
            start = bisect_left(ordered_times, new_time - window_seconds)
            end = bisect_right(ordered_times, new_time + window_seconds)
            for _other_time, other_index in ordered[start:end]:
                if other_index == new_index:
                    continue
                left_index, right_index = sorted((new_index, other_index))
                pair_key = (left_index, right_index)
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                mode = _context_mode(records[left_index], records[right_index])
                if mode is not None:
                    pairs.append((left_index, right_index, mode == "strict"))
        return pairs

    for left_position, (left_time, left_index) in enumerate(ordered):
        right_position = left_position + 1
        while right_position < len(ordered):
            right_time, right_index = ordered[right_position]
            if right_time - left_time > window_seconds:
                break
            mode = _context_mode(records[left_index], records[right_index])
            if mode is not None:
                pairs.append((left_index, right_index, mode == "strict"))
            right_position += 1
    return pairs


def _numeric_weight(record: dict[str, str]) -> float:
    try:
        return max(0.0, float(record.get("agg_weight", 0) or 0))
    except (TypeError, ValueError):
        return 0.0


def _preunion_existing_events(
    union_find: UnionFind,
    records: list[dict[str, str]],
    existing_count: int,
) -> None:
    first_by_event: dict[str, int] = {}
    for index, record in enumerate(records[:existing_count]):
        event_id = str(record.get("event_id", "") or record.get("article_id", "")).strip()
        if not event_id:
            continue
        if event_id in first_by_event:
            union_find.union(
                first_by_event[event_id],
                index,
                max_span_hours=EVENT_MAX_SPAN_HOURS,
            )
        else:
            first_by_event[event_id] = index


def _assign_cluster_fields(records: list[dict[str, str]], union_find: UnionFind) -> None:
    members_by_root: dict[int, list[int]] = {}
    for index in range(len(records)):
        members_by_root.setdefault(union_find.find(index), []).append(index)

    for members in members_by_root.values():
        representative_index = min(
            members,
            key=lambda index: (
                -_numeric_weight(records[index]),
                str(records[index].get("article_id", "")),
            ),
        )
        event_id = str(records[representative_index].get("article_id", "")).strip()
        if not event_id:
            event_id = f"missing-event-{representative_index}"
        sources: set[str] = set()
        for index in members:
            sources.update(
                split_sources(
                    records[index].get("publisher", "") or records[index].get("source", "")
                )
            )
        source_count = str(len(sources))
        for index in members:
            records[index]["event_id"] = event_id
            records[index]["source_count"] = source_count


def _cluster_records(
    records: list[dict[str, str]],
    engine: str | None,
    existing_count: int | None,
) -> ClusterResult:
    clustered = [dict(record) for record in records]
    timestamps = [_published_timestamp(record) for record in clustered]
    union_find = UnionFind(len(clustered), timestamps)
    incremental = existing_count is not None
    new_indices = set(range(existing_count or 0, len(clustered))) if incremental else None
    if incremental:
        _preunion_existing_events(union_find, clustered, existing_count or 0)

    candidate_pairs = _candidate_pairs(clustered, new_indices)
    active_indices = sorted({index for left, right, _strict in candidate_pairs for index in (left, right)})
    matched_pair_count = 0
    requested = str(engine or EVENT_SIMILARITY_ENGINE).strip().lower()
    used_engine = requested
    device = "not-needed"
    fallback_reason = ""

    if candidate_pairs:
        local_index = {record_index: position for position, record_index in enumerate(active_indices)}
        texts = [event_text(clustered[index]) for index in active_indices]
        similarity = build_similarity_index(texts, engine=requested)
        used_engine = similarity.used_engine
        device = similarity.device
        fallback_reason = similarity.fallback_reason
        for left, right, strict in candidate_pairs:
            if _has_polarity_conflict(clustered[left], clustered[right]):
                continue
            if similarity.index.is_similar(local_index[left], local_index[right], strict=strict):
                if union_find.union(left, right, max_span_hours=EVENT_MAX_SPAN_HOURS):
                    matched_pair_count += 1
    else:
        print("事件聚类候选对为 0，无需计算文本向量。")

    _assign_cluster_fields(clustered, union_find)
    return ClusterResult(
        records=clustered,
        info=ClusterRunInfo(
            requested_engine=requested,
            used_engine=used_engine,
            device=device,
            fallback_reason=fallback_reason,
            incremental=incremental,
            candidate_pair_count=len(candidate_pairs),
            matched_pair_count=matched_pair_count,
            compared_article_count=len(active_indices),
        ),
    )


def cluster_articles(records: list[dict[str, str]], engine: str | None = None) -> ClusterResult:
    """Recompute event clusters for the complete supplied history."""
    return _cluster_records(records, engine=engine, existing_count=None)


def cluster_articles_incremental(
    existing_records: list[dict[str, str]],
    new_records: list[dict[str, str]],
    engine: str | None = None,
) -> ClusterResult:
    """Compare only new articles with new/nearby existing articles.

    Existing event memberships are pre-unioned. Legacy data without event IDs is
    migrated with one full clustering pass.
    """
    combined = [dict(record) for record in existing_records + new_records]
    if existing_records and not all(str(record.get("event_id", "")).strip() for record in existing_records):
        print("检测到历史 processed 数据缺少 event_id，本次执行一次全量事件聚类迁移。")
        return cluster_articles(combined, engine=engine)
    return _cluster_records(combined, engine=engine, existing_count=len(existing_records))


def event_groups(records: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    groups: dict[str, list[dict[str, str]]] = {}
    for record in records:
        event_id = str(record.get("event_id", "") or record.get("article_id", "")).strip()
        groups.setdefault(event_id, []).append(record)
    return groups


def clustering_summary(records: list[dict[str, str]]) -> dict[str, Any]:
    groups = event_groups(records)
    multi_groups = [members for members in groups.values() if len(members) > 1]
    clustered_articles = sum(len(members) for members in multi_groups)
    largest = max(groups.items(), key=lambda item: len(item[1]), default=("", []))
    return {
        "article_count": len(records),
        "cluster_count": len(groups),
        "multi_article_cluster_count": len(multi_groups),
        "multi_cluster_ratio": len(multi_groups) / len(groups) if groups else 0.0,
        "clustered_article_count": clustered_articles,
        "clustered_article_coverage": clustered_articles / len(records) if records else 0.0,
        "largest_event_id": largest[0],
        "largest_cluster_size": len(largest[1]),
        "largest_cluster_titles": [str(record.get("title", "")) for record in largest[1]],
    }


def cluster_csv(path: Path, engine: str | None = None, write: bool = True) -> ClusterResult:
    records = read_article_csv(path)
    result = cluster_articles(records, engine=engine)
    if write:
        write_article_csv(path, result.records)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="为 processed 新闻计算事件级聚类。")
    parser.add_argument("--input", type=Path, default=REAL_PROCESSED_ARTICLES_PATH)
    parser.add_argument("--engine", choices=["embedding", "lexical"], default=EVENT_SIMILARITY_ENGINE)
    parser.add_argument("--dry-run", action="store_true", help="只计算和汇报，不写回 CSV")
    args = parser.parse_args()

    result = cluster_csv(args.input, engine=args.engine, write=not args.dry_run)
    summary = clustering_summary(result.records)
    print(
        "事件聚类完成："
        f"请求引擎 {result.info.requested_engine}，实际引擎 {result.info.used_engine}，"
        f"文章 {summary['article_count']}，事件簇 {summary['cluster_count']}，"
        f"多篇簇 {summary['multi_article_cluster_count']}，最大簇 {summary['largest_cluster_size']} 篇。"
    )


if __name__ == "__main__":
    main()
