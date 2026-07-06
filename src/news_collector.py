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
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from time import struct_time
from typing import Any

try:
    import feedparser
    import requests
except ImportError:  # pragma: no cover - 运行环境未安装依赖时给中文提示
    feedparser = None
    requests = None

from src.article_pipeline import process_articles
from src.config import EXPECTED_ARTICLE_COLUMNS, RAW_ARTICLES_PATH, REAL_PROCESSED_ARTICLES_PATH
from src.mapping import load_company_mapping
from src.preprocessing import read_article_csv, write_article_csv


USER_AGENT = (
    "SectorSentimentDashboard/0.1 "
    "(course research demo; contact: local-user; RSS title-summary-url only)"
)
REQUEST_TIMEOUT_SECONDS = 12
MAX_ENTRIES_PER_FEED = 20

CNBC_TOP_NEWS_RSS = "https://www.cnbc.com/id/100003114/device/rss/rss.html"
MARKETWATCH_TOP_STORIES_RSS = "https://feeds.marketwatch.com/marketwatch/topstories"
YAHOO_FINANCE_RSS_TEMPLATE = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"


@dataclass(frozen=True)
class FeedConfig:
    source: str
    url: str
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
    return re.sub(r"\s+", " ", text).strip()


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def parsed_time_to_utc(value: Any) -> str:
    """把 RSS 发布时间统一转换为 UTC ISO 8601。"""
    if isinstance(value, struct_time):
        parsed = datetime(*value[:6], tzinfo=UTC)
        return parsed.isoformat(timespec="seconds")

    if value:
        try:
            parsed = parsedate_to_datetime(str(value))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC).isoformat(timespec="seconds")
        except (TypeError, ValueError, OverflowError):
            pass

    return utc_now_iso()


def article_id_for(url: str, title: str) -> str:
    digest = hashlib.sha1(f"{url}|{title}".encode("utf-8")).hexdigest()[:16]
    return f"rss-{digest}"


def build_feed_configs() -> list[FeedConfig]:
    mapping = load_company_mapping()
    configs: list[FeedConfig] = []

    seen_tickers: set[str] = set()
    for item in mapping["companies"]:
        ticker = item["ticker"].strip().upper()
        if not ticker or ticker in seen_tickers:
            continue
        seen_tickers.add(ticker)
        configs.append(
            FeedConfig(
                source="Yahoo Finance RSS",
                url=YAHOO_FINANCE_RSS_TEMPLATE.format(ticker=ticker),
                ticker=ticker,
                company=item["company"],
                sector=item["sector"],
            )
        )

    configs.extend(
        [
            FeedConfig(source="CNBC Top News RSS", url=CNBC_TOP_NEWS_RSS),
            FeedConfig(source="MarketWatch Top Stories RSS", url=MARKETWATCH_TOP_STORIES_RSS),
        ]
    )
    return configs


def entry_to_record(entry: Any, feed_config: FeedConfig, collected_at: str) -> dict[str, str]:
    title = strip_html(entry.get("title", ""))
    summary = strip_html(entry.get("summary", "") or entry.get("description", ""))
    url = str(entry.get("link", "")).strip()
    published_value = entry.get("published_parsed") or entry.get("updated_parsed") or entry.get("published") or entry.get("updated")
    published_at = parsed_time_to_utc(published_value)

    record = {
        "article_id": article_id_for(url, title),
        "source": feed_config.source,
        "title": title,
        "summary": summary,
        "content": summary,
        "url": url,
        "published_at": published_at,
        "collected_at": collected_at,
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
            headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        parsed_feed = feedparser.parse(response.content)
        if not parsed_feed.entries:
            return [], "RSS 返回成功，但没有解析到新闻条目。"

        collected_at = utc_now_iso()
        records = [
            entry_to_record(entry, feed_config, collected_at)
            for entry in parsed_feed.entries[:MAX_ENTRIES_PER_FEED]
            if strip_html(entry.get("title", "")) and str(entry.get("link", "")).strip()
        ]
        return records, None
    except Exception as exc:  # noqa: BLE001 - 采集层需要逐源容错
        return [], str(exc)


def raw_record_key(record: dict[str, str]) -> tuple[str, str]:
    return (str(record.get("url", "")).strip().lower(), str(record.get("title", "")).strip().lower())


def read_existing_raw_records() -> list[dict[str, str]]:
    if not RAW_ARTICLES_PATH.exists() or RAW_ARTICLES_PATH.stat().st_size == 0:
        return []
    return read_article_csv(RAW_ARTICLES_PATH)


def merge_raw_records(existing: list[dict[str, str]], fetched: list[dict[str, str]]) -> tuple[list[dict[str, str]], int]:
    """累积存储新 RSS 记录；完全相同 URL+标题不重复追加。"""
    seen_keys = {raw_record_key(record) for record in existing}
    new_records: list[dict[str, str]] = []

    for record in fetched:
        key = raw_record_key(record)
        if not key[0] and not key[1]:
            continue
        if key in seen_keys:
            continue
        seen_keys.add(key)
        new_records.append(record)

    return existing + new_records, len(new_records)


def collect_rss_news(process: bool = True) -> dict[str, Any]:
    """抓取全部配置的 RSS 源，并刷新真实新闻处理结果。"""
    require_dependencies()
    feed_configs = build_feed_configs()
    fetched_records: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    successful_feed_count = 0

    for feed_config in feed_configs:
        records, error = fetch_feed(feed_config)
        if error:
            failures.append({"source": feed_config.source, "url": feed_config.url, "error": error})
        if records:
            successful_feed_count += 1
            fetched_records.extend(records)

    existing_records = read_existing_raw_records()
    merged_records, new_record_count = merge_raw_records(existing_records, fetched_records)
    if merged_records:
        write_article_csv(RAW_ARTICLES_PATH, merged_records)

    processed_count = 0
    if process and merged_records:
        processed_records = process_articles(RAW_ARTICLES_PATH, REAL_PROCESSED_ARTICLES_PATH)
        processed_count = len(processed_records)

    all_failed = successful_feed_count == 0
    return {
        "feed_count": len(feed_configs),
        "successful_feed_count": successful_feed_count,
        "failed_feed_count": len(failures),
        "fetched_count": len(fetched_records),
        "new_record_count": new_record_count,
        "raw_total_count": len(merged_records),
        "processed_count": processed_count,
        "all_failed": all_failed,
        "failures": failures,
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
        f"raw 累计 {result['raw_total_count']} 条，"
        f"processed {result['processed_count']} 条。"
    )
    if result["all_failed"]:
        print(result["message"])
    if result["failures"]:
        print("失败源摘要：")
        for failure in result["failures"][:10]:
            print(f"- {failure['source']} | {failure['url']} | {failure['error']}")


if __name__ == "__main__":
    main()
