"""RSS 新闻采集模块。

第一版只读取 RSS 中的标题、摘要、链接、发布时间和来源，不抓新闻正文页面，
避免反爬、版权和登录限制。抓取结果累积保存到 `data/raw_articles.csv`，
再复用现有文章处理流水线生成 `data/real_processed_articles.csv`。
"""

from __future__ import annotations

import argparse
import hashlib
import html
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from time import struct_time
from time import perf_counter
from typing import Any

try:
    import feedparser
    import requests
except ImportError:  # pragma: no cover - 运行环境未安装依赖时给中文提示
    feedparser = None
    requests = None

from src.article_pipeline import (
    data_source_for_output_path,
    process_articles_incremental,
    write_pipeline_outputs,
)
from src.brief_generator import maybe_generate_daily_brief
from src.config import (
    EXPECTED_ARTICLE_COLUMNS,
    RAW_ARTICLES_PATH,
    RAW_SQLITE_WARNING_MB,
    REAL_PROCESSED_ARTICLES_PATH,
    RSS_REQUEST_TIMEOUT_SECONDS,
    RSS_USER_AGENT,
)
from src.mapping import load_company_mapping
from src.preprocessing import read_article_csv, repair_mojibake, write_article_csv
from src.rss_sources import (
    RssSource,
    enabled_rss_sources,
    source_weight_for_names,
    split_multi_value,
)


@dataclass(frozen=True)
class FeedConfig:
    source: str
    url: str
    source_weight: float
    max_entries: int
    fulltext_allowed: bool
    ticker: str = ""
    company: str = ""
    sector: str = ""


def require_dependencies() -> None:
    if feedparser is None or requests is None:
        raise RuntimeError(
            "缺少 RSS 抓取依赖。请先运行 `pip install -r requirements.txt`，"
            "确保 feedparser 和 requests 已安装。"
        )


def strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    text = html.unescape(text)
    text = repair_mojibake(text)
    return re.sub(r"\s+", " ", text).strip()


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


RSS_PUBLISHED_AT_ERROR = "published_at: missing/unparseable in RSS; fallback=collected_at"


def parsed_time_to_utc(value: Any, collected_at: str) -> tuple[str, str]:
    """把 RSS 发布时间统一转换为 UTC ISO 8601；失败时回落采集时间并返回错误说明。"""
    if isinstance(value, struct_time):
        parsed = datetime(*value[:6], tzinfo=UTC)
        return parsed.isoformat(timespec="seconds"), ""

    if value:
        try:
            parsed = parsedate_to_datetime(str(value))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC).isoformat(timespec="seconds"), ""
        except (TypeError, ValueError, OverflowError):
            pass

    return collected_at, RSS_PUBLISHED_AT_ERROR


def article_id_for(url: str, title: str) -> str:
    digest = hashlib.sha1(f"{url}|{title}".encode("utf-8")).hexdigest()[:16]
    return f"rss-{digest}"


def build_feed_configs() -> list[FeedConfig]:
    mapping = load_company_mapping()
    configs: list[FeedConfig] = []
    for source in enabled_rss_sources():
        if source.kind == "market":
            configs.append(feed_config_from_source(source))
            continue

        seen_tickers: set[str] = set()
        for item in mapping["companies"]:
            ticker = item["ticker"].strip().upper()
            if not ticker or ticker in seen_tickers:
                continue
            seen_tickers.add(ticker)
            configs.append(
                feed_config_from_source(
                    source,
                    ticker=ticker,
                    company=item["company"],
                    sector=item["sector"],
                )
            )
    return configs


def feed_config_from_source(
    source: RssSource,
    ticker: str = "",
    company: str = "",
    sector: str = "",
) -> FeedConfig:
    return FeedConfig(
        source=source.name,
        url=source.url.format(ticker=ticker) if ticker else source.url,
        source_weight=source.source_weight,
        max_entries=source.max_entries,
        fulltext_allowed=source.fulltext_allowed,
        ticker=ticker,
        company=company,
        sector=sector,
    )


def entry_publisher(entry: Any, fallback: str) -> str:
    for key in ("source", "publisher", "dc_publisher"):
        value = entry.get(key)
        if hasattr(value, "get"):
            value = value.get("title") or value.get("name") or value.get("value")
        cleaned = strip_html(value)
        if cleaned:
            return cleaned
    return fallback


def entry_to_record(entry: Any, feed_config: FeedConfig, collected_at: str) -> dict[str, str]:
    title = strip_html(entry.get("title", ""))
    summary = strip_html(entry.get("summary", "") or entry.get("description", ""))
    url = str(entry.get("link", "")).strip()
    published_value = entry.get("published_parsed") or entry.get("updated_parsed") or entry.get("published") or entry.get("updated")
    published_at, time_parse_error = parsed_time_to_utc(published_value, collected_at)

    record = {
        "article_id": article_id_for(url, title),
        "source": feed_config.source,
        "publisher": entry_publisher(entry, feed_config.source),
        "title": title,
        "summary": summary,
        "content": summary,
        "body_text": "",
        "content_level": "summary",
        "rescored": "False",
        "url": url,
        "published_at": published_at,
        "collected_at": collected_at,
        "time_parse_error": time_parse_error,
        "language": "en",
        "tickers": feed_config.ticker,
        "companies": feed_config.company,
        "sector": feed_config.sector,
        "topic": "",
        "sentiment_score": "0",
        "p_positive": "0",
        "p_neutral": "0",
        "p_negative": "0",
        "optimism": "0",
        "fear": "0",
        "uncertainty": "0",
        "attention": "0",
        "attention_weight": "0",
        "disagreement": "0",
        "disagreement_input": "0",
        "risk_intensity": "0",
        "risk_category": "",
        "evidence_sentence": "",
        "model_confidence": "0",
        "relevance_weight": "0",
        "time_weight": "0",
        "source_weight": f"{feed_config.source_weight:.3f}",
        "agg_weight": "0",
        "is_duplicate": "False",
        "dedup_factor": "1.0",
    }
    return {column: record.get(column, "") for column in EXPECTED_ARTICLE_COLUMNS}


def fetch_feed(feed_config: FeedConfig) -> tuple[list[dict[str, str]], str | None]:
    """抓取单个 feed；失败时返回错误信息，不抛出到外层中断其他源。"""
    require_dependencies()
    try:
        response = requests.get(
            feed_config.url,
            headers={"User-Agent": RSS_USER_AGENT, "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8"},
            timeout=RSS_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        parsed_feed = feedparser.parse(response.content)
        if not parsed_feed.entries:
            return [], "RSS 返回成功，但没有解析到新闻条目。"

        collected_at = utc_now_iso()
        records = [
            entry_to_record(entry, feed_config, collected_at)
            for entry in parsed_feed.entries[:feed_config.max_entries]
            if strip_html(entry.get("title", "")) and str(entry.get("link", "")).strip()
        ]
        return records, None
    except Exception as exc:  # noqa: BLE001 - 采集层需要逐源容错
        return [], str(exc)


def raw_record_key(record: dict[str, str]) -> tuple[str, str]:
    return (str(record.get("url", "")).strip().lower(), str(record.get("title", "")).strip().lower())


def split_context_values(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(";") if item.strip()]


def merge_context_values(left: str, right: str) -> str:
    values: list[str] = []
    seen: set[str] = set()
    for item in split_context_values(left) + split_context_values(right):
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        values.append(item)
    return ";".join(values)


def merge_sector_context(left: str, right: str) -> str:
    left_value = str(left or "").strip()
    right_value = str(right or "").strip()
    if not left_value:
        return right_value
    if not right_value or left_value == right_value:
        return left_value
    # 多 ticker feed 指向不同板块时，清空单一 sector fallback，避免先抓到的 feed 主导归属。
    return ""


def merge_raw_context(target: dict[str, str], incoming: dict[str, str]) -> bool:
    before = (
        target.get("tickers", ""),
        target.get("companies", ""),
        target.get("source", ""),
        target.get("publisher", ""),
        target.get("source_weight", ""),
        target.get("sector", ""),
    )
    target["tickers"] = merge_context_values(target.get("tickers", ""), incoming.get("tickers", ""))
    target["companies"] = merge_context_values(target.get("companies", ""), incoming.get("companies", ""))
    target["source"] = merge_context_values(target.get("source", ""), incoming.get("source", ""))
    target["publisher"] = merge_context_values(
        target.get("publisher", ""), incoming.get("publisher", "")
    )
    try:
        target_weight = float(target.get("source_weight", 0) or 0)
    except (TypeError, ValueError):
        target_weight = 0.0
    try:
        incoming_weight = float(incoming.get("source_weight", 0) or 0)
    except (TypeError, ValueError):
        incoming_weight = 0.0
    target["source_weight"] = f"{max(target_weight, incoming_weight, 1e-9):.3f}"
    target["sector"] = merge_sector_context(target.get("sector", ""), incoming.get("sector", ""))
    target["time_parse_error"] = merge_context_values(target.get("time_parse_error", ""), incoming.get("time_parse_error", ""))
    target["processing_error"] = merge_context_values(target.get("processing_error", ""), incoming.get("processing_error", ""))
    after = (
        target.get("tickers", ""),
        target.get("companies", ""),
        target.get("source", ""),
        target.get("publisher", ""),
        target.get("source_weight", ""),
        target.get("sector", ""),
    )
    return before != after


def read_existing_raw_records() -> list[dict[str, str]]:
    if not RAW_ARTICLES_PATH.exists() or RAW_ARTICLES_PATH.stat().st_size == 0:
        return []
    records = read_article_csv(RAW_ARTICLES_PATH)
    for record in records:
        record["publisher"] = record.get("publisher", "") or record.get("source", "")
        if not str(record.get("source_weight", "")).strip():
            record["source_weight"] = f"{source_weight_for_names(record.get('source', '')):.3f}"
        record["content_level"] = record.get("content_level", "") or (
            "fulltext" if record.get("body_text") else "summary"
        )
        record["rescored"] = record.get("rescored", "") or "False"
    return records


def merge_raw_records(existing: list[dict[str, str]], fetched: list[dict[str, str]]) -> tuple[list[dict[str, str]], int, int, list[dict[str, str]]]:
    """累积保存 RSS 记录；重复 URL+标题时合并 ticker/company 语境，不丢弃后续 feed 信息。"""
    merged_records = [dict(record) for record in existing]
    existing_by_key = {
        raw_record_key(record): record
        for record in merged_records
        if raw_record_key(record) != ("", "")
    }
    new_records: list[dict[str, str]] = []
    merged_context_count = 0

    for record in fetched:
        key = raw_record_key(record)
        if not key[0] and not key[1]:
            continue
        if key in existing_by_key:
            if merge_raw_context(existing_by_key[key], record):
                merged_context_count += 1
            continue
        existing_by_key[key] = record
        new_records.append(record)

    return merged_records + new_records, len(new_records), merged_context_count, new_records


def collect_rss_news(process: bool = True) -> dict[str, Any]:
    """抓取全部配置的 RSS 源，并刷新真实新闻处理结果。"""
    collection_started = perf_counter()
    require_dependencies()
    feed_configs = build_feed_configs()
    fetched_records: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    successful_feed_count = 0
    source_stats: dict[str, dict[str, Any]] = {}

    for feed_config in feed_configs:
        stats = source_stats.setdefault(
            feed_config.source,
            {"source": feed_config.source, "feed_attempts": 0, "successful_feeds": 0, "fetched_count": 0},
        )
        stats["feed_attempts"] += 1
        records, error = fetch_feed(feed_config)
        if error:
            failures.append({"source": feed_config.source, "url": feed_config.url, "error": error})
        if records:
            successful_feed_count += 1
            stats["successful_feeds"] += 1
            stats["fetched_count"] += len(records)
            fetched_records.extend(records)

    feed_elapsed_seconds = perf_counter() - collection_started

    existing_records = read_existing_raw_records()
    merged_records, new_record_count, merged_context_count, new_records = merge_raw_records(existing_records, fetched_records)
    if merged_records:
        write_article_csv(RAW_ARTICLES_PATH, merged_records)

    processed_count = 0
    incremental_new_count = 0
    reused_count = 0
    brief_result: dict[str, str] = {"status": "skipped", "message": "未运行处理管线，跳过简报门闸。"}
    fulltext_result: dict[str, Any] = {
        "selected_count": 0,
        "attempted_count": 0,
        "success_count": 0,
        "failed_count": 0,
        "rescored_count": 0,
        "elapsed_seconds": 0.0,
        "comparisons": [],
    }
    processed_records_for_stats: list[dict[str, str]] = []
    if process and merged_records:
        process_result = process_articles_incremental(RAW_ARTICLES_PATH, REAL_PROCESSED_ARTICLES_PATH, new_records)
        from src.fulltext_fetcher import fetch_and_rescore_fulltext, sync_fulltext_to_raw

        fulltext_result_with_records = fetch_and_rescore_fulltext(process_result["records"])
        final_records = fulltext_result_with_records.pop("records")
        fulltext_result = fulltext_result_with_records
        if fulltext_result["rescored_count"]:
            sync_fulltext_to_raw(merged_records, final_records)
            write_article_csv(RAW_ARTICLES_PATH, merged_records)
            write_pipeline_outputs(
                REAL_PROCESSED_ARTICLES_PATH,
                final_records,
                data_source_for_output_path(REAL_PROCESSED_ARTICLES_PATH),
            )
        processed_count = len(final_records)
        processed_records_for_stats = final_records
        incremental_new_count = int(process_result["new_count"])
        reused_count = int(process_result["reused_count"])
        brief_result = maybe_generate_daily_brief()

    raw_size_warning = ""
    if RAW_ARTICLES_PATH.exists():
        raw_size_mb = RAW_ARTICLES_PATH.stat().st_size / (1024 * 1024)
        if raw_size_mb > RAW_SQLITE_WARNING_MB:
            raw_size_warning = (
                f"raw_articles.csv 当前约 {raw_size_mb:.1f}MB，建议后续迁移到 SQLite；"
                "本版本暂不自动迁移。"
            )
            print(raw_size_warning)

    all_failed = successful_feed_count == 0
    publisher_counts: Counter[str] = Counter()
    for record in processed_records_for_stats:
        publisher_counts.update(
            split_multi_value(record.get("publisher", "") or record.get("source", ""))
        )
    return {
        "feed_count": len(feed_configs),
        "successful_feed_count": successful_feed_count,
        "failed_feed_count": len(failures),
        "fetched_count": len(fetched_records),
        "new_record_count": new_record_count,
        "merged_context_count": merged_context_count,
        "raw_total_count": len(merged_records),
        "processed_count": processed_count,
        "incremental_new_count": incremental_new_count,
        "reused_count": reused_count,
        "brief_result": brief_result,
        "raw_size_warning": raw_size_warning,
        "all_failed": all_failed,
        "failures": failures,
        "source_results": list(source_stats.values()),
        "fulltext_result": fulltext_result,
        "publisher_top15": publisher_counts.most_common(15),
        "feed_elapsed_seconds": round(feed_elapsed_seconds, 3),
        "total_elapsed_seconds": round(perf_counter() - collection_started, 3),
        "message": "全部 RSS 源抓取失败，已保留 demo 数据作为兜底。" if all_failed else "",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="抓取 RSS 财经新闻并刷新真实新闻数据。")
    parser.add_argument("--no-process", action="store_true", help="只更新 raw_articles.csv，不生成 real_processed_articles.csv")
    args = parser.parse_args()

    try:
        result = collect_rss_news(process=not args.no_process)
    except RuntimeError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(
        "RSS 抓取完成："
        f"feed 总数 {result['feed_count']}，"
        f"成功 {result['successful_feed_count']}，"
        f"失败 {result['failed_feed_count']}，"
        f"本次解析 {result['fetched_count']} 条，"
        f"新增 {result['new_record_count']} 条，"
        f"合并重复语境 {result['merged_context_count']} 条，"
        f"raw 累计 {result['raw_total_count']} 条，"
        f"processed {result['processed_count']} 条。"
    )
    if result["all_failed"]:
        print(result["message"])
    print(f"增量处理：本次新增 {result['incremental_new_count']} 条，复用 {result['reused_count']} 条。")
    if result.get("fulltext_result"):
        fulltext = result["fulltext_result"]
        print(
            "正文抓取："
            f"尝试 {fulltext.get('attempted_count', 0)}，成功 {fulltext.get('success_count', 0)}，"
            f"失败 {fulltext.get('failed_count', 0)}，重评分 {fulltext.get('rescored_count', 0)}，"
            f"耗时 {fulltext.get('elapsed_seconds', 0):.1f} 秒。"
        )
        for comparison in fulltext.get("comparisons", [])[:3]:
            print(
                f"- {comparison.get('title', '')} | "
                f"摘要 {comparison.get('summary_sentiment_score', 0):.3f} -> "
                f"正文 {comparison.get('fulltext_sentiment_score', 0):.3f} | "
                f"证据句：{comparison.get('fulltext_evidence_sentence', '')}"
            )
    if result.get("source_results"):
        print("各源实测条数：")
        for source_result in result["source_results"]:
            print(
                f"- {source_result['source']}：{source_result['fetched_count']} 条 "
                f"({source_result['successful_feeds']}/{source_result['feed_attempts']} feeds 成功)"
            )
    if result.get("publisher_top15"):
        print("Publisher Top15：")
        for publisher, count in result["publisher_top15"]:
            print(f"- {publisher}: {count}")
    print(
        f"耗时：RSS {result.get('feed_elapsed_seconds', 0):.1f} 秒，"
        f"正文 {result.get('fulltext_result', {}).get('elapsed_seconds', 0):.1f} 秒，"
        f"总计 {result.get('total_elapsed_seconds', 0):.1f} 秒。"
    )
    if result.get("raw_size_warning"):
        print(result["raw_size_warning"])
    if result.get("brief_result"):
        print(f"简报门闸：{result['brief_result'].get('message', '')}")
    if result["failures"]:
        print("失败源摘要：")
        for failure in result["failures"][:10]:
            print(f"- {failure['source']} | {failure['url']} | {failure['error']}")


if __name__ == "__main__":
    main()
