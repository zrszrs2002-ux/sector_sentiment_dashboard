"""数据预处理工具。

第二阶段先实现稳定的 UTC 时间标准化和基础去重。后续真实新闻抓取、
正文清洗、分句和相似文本聚类会继续在本模块扩展。
"""

from __future__ import annotations

import csv
import re
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path

from src.config import DEFAULT_DEDUP_FACTORS, EXPECTED_ARTICLE_COLUMNS


UTC_TIME_COLUMNS = ["published_at", "collected_at"]
SIMILAR_TITLE_THRESHOLD = 0.9
SIMILAR_PREFIX_TOKEN_COUNT = 5


def parse_utc_datetime(value: str) -> datetime:
    """把输入时间解析为 UTC datetime。解析失败时使用当前 UTC 时间兜底。"""
    if not value:
        return datetime.now(UTC)

    normalized = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.now(UTC)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def format_utc_datetime(value: str) -> str:
    """统一输出 ISO 8601 UTC 时间字符串。"""
    return parse_utc_datetime(value).isoformat(timespec="seconds")


def normalize_title(title: str) -> str:
    """把标题规范化后用于精确与相似去重。"""
    lowered = str(title or "").lower()
    lowered = re.sub(r"https?://\S+", "", lowered)
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def title_similarity(left: str, right: str) -> float:
    """计算两个规范化标题的相似度。"""
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def is_similar_reprint(candidate_title: str, previous_title: str) -> bool:
    """判断是否是近似同题转载，避免把模板结构相似的不同新闻误判为重复。"""
    candidate_tokens = candidate_title.split()
    previous_tokens = previous_title.split()
    if len(candidate_tokens) < SIMILAR_PREFIX_TOKEN_COUNT:
        return False
    if len(previous_tokens) < SIMILAR_PREFIX_TOKEN_COUNT:
        return False
    if candidate_tokens[:SIMILAR_PREFIX_TOKEN_COUNT] != previous_tokens[:SIMILAR_PREFIX_TOKEN_COUNT]:
        return False
    return title_similarity(candidate_title, previous_title) >= SIMILAR_TITLE_THRESHOLD


def ensure_article_columns(record: dict[str, str]) -> dict[str, str]:
    """确保每条记录都包含约定字段，避免页面读取时报缺列。"""
    return {column: record.get(column, "") for column in EXPECTED_ARTICLE_COLUMNS}


def preprocess_records(records: list[dict[str, str]]) -> list[dict[str, str]]:
    """标准化时间并标记 URL、标题和高相似标题重复。"""
    processed: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    seen_titles: dict[str, str] = {}

    for raw_record in records:
        record = ensure_article_columns(raw_record)

        for column in UTC_TIME_COLUMNS:
            record[column] = format_utc_datetime(record[column])

        url_key = str(record.get("url", "")).strip().lower()
        title_key = normalize_title(record.get("title", ""))

        dedup_reason = "unique"
        if url_key and url_key in seen_urls:
            dedup_reason = "duplicate"
        elif title_key and title_key in seen_titles:
            dedup_reason = "duplicate"
        else:
            for previous_title in seen_titles:
                if is_similar_reprint(title_key, previous_title):
                    dedup_reason = "similar_reprint"
                    break

        record["is_duplicate"] = "True" if dedup_reason != "unique" else "False"
        record["dedup_factor"] = str(DEFAULT_DEDUP_FACTORS[dedup_reason])

        if url_key:
            seen_urls.add(url_key)
        if title_key:
            seen_titles.setdefault(title_key, record["article_id"])

        processed.append(record)

    return processed


def read_article_csv(path: Path) -> list[dict[str, str]]:
    """读取文章 CSV。"""
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_article_csv(path: Path, records: list[dict[str, str]]) -> None:
    """按固定字段顺序写出文章 CSV。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=EXPECTED_ARTICLE_COLUMNS)
        writer.writeheader()
        writer.writerows([ensure_article_columns(record) for record in records])


def preprocess_csv(input_path: Path, output_path: Path) -> list[dict[str, str]]:
    """从原始 demo CSV 生成处理后的文章 CSV。"""
    records = read_article_csv(input_path)
    processed = preprocess_records(records)
    write_article_csv(output_path, processed)
    return processed
