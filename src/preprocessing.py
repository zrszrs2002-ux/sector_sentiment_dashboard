"""数据预处理工具。

负责 UTC 时间标准化、解析错误留档、基础去重和安全 CSV 写入。
"""

from __future__ import annotations

import csv
import re
import shutil
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path

from src.config import (
    BACKUP_RETENTION_COUNT,
    CSV_EXPORT_ENCODING,
    DEFAULT_DEDUP_FACTORS,
    EXPECTED_ARTICLE_COLUMNS,
    SIMILAR_PREFIX_TOKEN_COUNT,
    SIMILAR_TITLE_THRESHOLD,
)

def parse_utc_datetime(value: object) -> datetime:
    """把输入时间解析为 UTC datetime；解析失败时显式抛错，避免污染时间权重。"""
    if not value:
        raise ValueError("empty datetime")

    if isinstance(value, datetime):
        parsed = value
    else:
        normalized = str(value).strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def format_utc_datetime(value: object) -> str:
    """统一输出 ISO 8601 UTC 时间字符串。"""
    return parse_utc_datetime(value).isoformat(timespec="seconds")


def format_utc_datetime_or_fallback(value: object, fallback: datetime) -> tuple[str, str]:
    """返回标准化 UTC 时间和解析错误；fallback 会被记录，不再静默伪装成原始时间。"""
    try:
        return format_utc_datetime(value), ""
    except (TypeError, ValueError) as exc:
        return fallback.astimezone(UTC).isoformat(timespec="seconds"), str(exc)


def normalize_record_times(record: dict[str, str]) -> None:
    errors: list[str] = []
    now = datetime.now(UTC)

    collected_at, collected_error = format_utc_datetime_or_fallback(record.get("collected_at", ""), now)
    if collected_error:
        errors.append(f"collected_at: {collected_error}; fallback=current_utc")
    record["collected_at"] = collected_at

    collected_dt = parse_utc_datetime(collected_at)
    published_at, published_error = format_utc_datetime_or_fallback(record.get("published_at", ""), collected_dt)
    if published_error:
        errors.append(f"published_at: {published_error}; fallback=collected_at")
    record["published_at"] = published_at

    existing_error = str(record.get("time_parse_error", "") or "").strip()
    all_errors = [existing_error] if existing_error else []
    all_errors.extend(errors)
    record["time_parse_error"] = "; ".join(all_errors)


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

        normalize_record_times(record)

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
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            return list(csv.DictReader(file))
    except (OSError, csv.Error, UnicodeDecodeError):
        return []


def normalize_csv_record(fieldnames: list[str], record: dict[str, object]) -> dict[str, object]:
    return {column: record.get(column, "") for column in fieldnames}


def write_csv_atomic(path: Path, fieldnames: list[str], records: list[dict[str, object]]) -> None:
    """Atomically write a CSV with backups and per-source retention."""
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    temp_path = path.with_name(f".{path.name}.{timestamp}.tmp")

    try:
        with temp_path.open("w", encoding=CSV_EXPORT_ENCODING, newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows([normalize_csv_record(fieldnames, record) for record in records])

        if path.exists() and path.stat().st_size > 0:
            backup_dir = path.parent / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / f"{path.stem}.{timestamp}.bak{path.suffix}"
            shutil.copy2(path, backup_path)
            prune_backups(path, backup_dir)

        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def write_article_csv(path: Path, records: list[dict[str, str]]) -> None:
    """按固定字段顺序原子写出 CSV；替换前保留备份，降低历史数据丢失风险。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    temp_path = path.with_name(f".{path.name}.{timestamp}.tmp")

    try:
        with temp_path.open("w", encoding=CSV_EXPORT_ENCODING, newline="") as file:
            writer = csv.DictWriter(file, fieldnames=EXPECTED_ARTICLE_COLUMNS)
            writer.writeheader()
            writer.writerows([ensure_article_columns(record) for record in records])

        if path.exists() and path.stat().st_size > 0:
            backup_dir = path.parent / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / f"{path.stem}.{timestamp}.bak{path.suffix}"
            shutil.copy2(path, backup_path)
            prune_backups(path, backup_dir)

        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def prune_backups(source_path: Path, backup_dir: Path) -> None:
    """每个源文件只保留最近 N 份备份。"""
    if BACKUP_RETENTION_COUNT <= 0:
        return
    pattern = f"{source_path.stem}.*.bak{source_path.suffix}"
    backups = sorted(
        backup_dir.glob(pattern),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for old_backup in backups[BACKUP_RETENTION_COUNT:]:
        try:
            old_backup.unlink()
        except OSError:
            continue


def preprocess_csv(input_path: Path, output_path: Path) -> list[dict[str, str]]:
    """从原始 demo CSV 生成处理后的文章 CSV。"""
    records = read_article_csv(input_path)
    processed = preprocess_records(records)
    write_article_csv(output_path, processed)
    return processed
