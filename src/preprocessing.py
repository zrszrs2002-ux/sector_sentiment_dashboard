"""Data-preprocessing utilities.

Handle UTC timestamp normalization, parse-error retention, basic deduplication,
and safe CSV writes.
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

# Common mojibake sequences created when UTF-8 text is incorrectly decoded as cp1252, mapped to correct characters.
# Audit conclusion on 2026-07-12: current stored data contains no mojibake. The previously observed "It??s"
# was a GBK-console display artifact for the U+2019 curly apostrophe; the data itself is valid Unicode.
# No stored-data migration is needed. This table only protects future collection from malformed RSS encodings.
_MOJIBAKE_REPLACEMENTS = {
    "â€™": "'",    # Right single quotation mark
    "â€˜": "'",    # Left single quotation mark
    "â€œ": '"',    # Left double quotation mark
    "â€": '"',    # Right double quotation mark
    "â€“": "-",    # â€“ → en dash
    "â€”": "-",    # â€” → em dash
    "â€¦": "...",  # Ellipsis
    "Â ": " ",     # Non-breaking space
}


def repair_mojibake(text: str) -> str:
    """Repair common cp1252 mojibake and remove U+FFFD replacement characters; preserve valid text."""
    value = str(text or "")
    for broken, fixed in _MOJIBAKE_REPLACEMENTS.items():
        if broken in value:
            value = value.replace(broken, fixed)
    return value.replace("�", "")


def parse_utc_datetime(value: object) -> datetime:
    """Parse input as a UTC datetime; raise explicitly on failure to avoid corrupting time weights."""
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
    """Return a normalized ISO 8601 UTC timestamp string."""
    return parse_utc_datetime(value).isoformat(timespec="seconds")


def format_utc_datetime_or_fallback(value: object, fallback: datetime) -> tuple[str, str]:
    """Return normalized UTC time and a parse error; record fallbacks instead of silently preserving invalid input."""
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
    """Normalize a title for exact and similarity-based deduplication."""
    lowered = str(title or "").lower()
    lowered = re.sub(r"https?://\S+", "", lowered)
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def title_similarity(left: str, right: str) -> float:
    """Calculate similarity between two normalized titles."""
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def is_similar_reprint(candidate_title: str, previous_title: str) -> bool:
    """Detect near-duplicate coverage while avoiding false matches between structurally similar template articles."""
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
    """Ensure every record contains the expected fields so pages do not fail on missing columns."""
    return {column: record.get(column, "") for column in EXPECTED_ARTICLE_COLUMNS}


def preprocess_records(records: list[dict[str, str]]) -> list[dict[str, str]]:
    """Normalize timestamps and mark duplicate URLs, exact titles, and highly similar titles."""
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
    """Read an article CSV file."""
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
    """Atomically write CSV columns in a fixed order, backing up the prior file before replacement."""
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
    """Retain only the latest N backups for each source file."""
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
    """Generate a processed article CSV from a raw demo CSV."""
    records = read_article_csv(input_path)
    processed = preprocess_records(records)
    write_article_csv(output_path, processed)
    return processed
