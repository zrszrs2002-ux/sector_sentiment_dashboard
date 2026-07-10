"""文章处理流水线。

把原始新闻 CSV 转换为结构化新闻输出：公司/ticker/板块映射、主题标签、
风险标签、词典情绪 fallback 和文章级基础分数。
"""

from __future__ import annotations

import re
from pathlib import Path

from src.config import (
    DATA_DIR,
    DEMO_PROCESSED_ARTICLES_PATH,
    ERROR_RECORDS_PATH,
    EXPECTED_ARTICLE_COLUMNS,
    REAL_PROCESSED_ARTICLES_PATH,
    RELEVANCE_WEIGHTS,
)
from src.daily_snapshots import write_daily_snapshots
from src.data_loader import DEMO_DATA_LABEL, REAL_DATA_LABEL
from src.event_clustering import cluster_articles, cluster_articles_incremental
from src.mapping import map_article
from src.preprocessing import preprocess_records, read_article_csv, write_article_csv
from src.scoring import score_article
from src.sentiment_model import ArticleSentiment, analyze_article_sentiment, analyze_articles_sentiment
from src.topic_risk_tagger import split_sentences, tag_article


def normalize_evidence_text(value: str) -> str:
    lowered = str(value or "").lower()
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def article_parts(record: dict[str, str], fields: list[str]) -> list[str]:
    parts: list[str] = []
    seen: set[str] = set()
    for field in fields:
        value = str(record.get(field, "") or "").strip()
        key = normalize_evidence_text(value)
        if not value or not key or key in seen:
            continue
        seen.add(key)
        parts.append(value)
    return parts


def join_sentence_parts(parts: list[str]) -> str:
    normalized_parts: list[str] = []
    for part in parts:
        if part[-1] in ".!?":
            normalized_parts.append(part)
        else:
            normalized_parts.append(f"{part}.")
    return " ".join(normalized_parts)


def split_semicolon_values(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(";") if item.strip()]


def merge_semicolon_values(*values: str) -> str:
    merged: list[str] = []
    seen: set[str] = set()
    for value in values:
        for item in split_semicolon_values(value):
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return ";".join(merged)


def article_text(record: dict[str, str]) -> str:
    return join_sentence_parts(article_parts(record, ["title", "summary", "content"]))


def mapping_text(record: dict[str, str]) -> str:
    raw_context = " ".join(
        item
        for item in [
            str(record.get("companies", "") or "").replace(";", " "),
            str(record.get("tickers", "") or "").replace(";", " "),
        ]
        if item.strip()
    )
    return " ".join([article_text(record), raw_context]).strip()


def article_body_text(record: dict[str, str]) -> str:
    return join_sentence_parts(article_parts(record, ["summary", "content"]))


def strip_title_from_evidence(sentence: str, title: str) -> str:
    sentence = str(sentence or "").strip()
    title = str(title or "").strip()
    if not sentence:
        return ""

    sentence_key = normalize_evidence_text(sentence)
    title_key = normalize_evidence_text(title)
    if title_key and sentence_key == title_key:
        return ""

    if title and sentence.lower().startswith(title.lower()):
        remainder = sentence[len(title) :].lstrip(" .:-")
        if normalize_evidence_text(remainder):
            return remainder

    return sentence


def first_body_sentence(record: dict[str, str]) -> str:
    title = str(record.get("title", "") or "")
    for sentence in split_sentences(article_body_text(record)):
        cleaned = strip_title_from_evidence(sentence, title)
        if cleaned:
            return cleaned
    return ""


def choose_evidence_sentence(record: dict[str, str], tag_result, sentiment) -> str:
    title = str(record.get("title", "") or "")
    body = article_body_text(record)
    body_tag_result = tag_article(body) if body else None

    candidates: list[str] = []
    if body_tag_result and body_tag_result.risk_category == tag_result.risk_category:
        candidates.append(body_tag_result.risk_evidence_sentence)
    candidates.extend(
        [
            tag_result.risk_evidence_sentence,
            sentiment.evidence_sentence,
            first_body_sentence(record),
        ]
    )

    for candidate in candidates:
        cleaned = strip_title_from_evidence(candidate, title)
        if cleaned:
            return cleaned
    return title


def enrich_record(record: dict[str, str], sentiment: ArticleSentiment | None = None) -> dict[str, str]:
    text = article_text(record)
    mapping_result = map_article(mapping_text(record))
    tag_result = tag_article(text)
    if sentiment is None:
        sentiment = analyze_article_sentiment(
            record.get("title", ""),
            record.get("summary", ""),
            record.get("content", ""),
        )

    sector = mapping_result["sector"]
    companies = merge_semicolon_values(mapping_result["companies"], record.get("companies", ""))
    tickers = merge_semicolon_values(mapping_result["tickers"], record.get("tickers", ""))
    relevance_weight = float(mapping_result["relevance_weight"])
    if sector == "Unmapped" and record.get("sector"):
        sector = record.get("sector", "")
        relevance_weight = RELEVANCE_WEIGHTS["company_or_ticker"]
    elif sector == "Unmapped" and tag_result.sector_hint:
        sector = tag_result.sector_hint

    scores = score_article(
        sentiment=sentiment,
        risk_category=tag_result.risk_category,
        published_at=record.get("published_at", ""),
        collected_at=record.get("collected_at", ""),
        relevance_weight=relevance_weight,
        dedup_factor=float(record.get("dedup_factor") or 1.0),
    )

    evidence_sentence = choose_evidence_sentence(record, tag_result, sentiment)

    enriched = {column: record.get(column, "") for column in EXPECTED_ARTICLE_COLUMNS}
    enriched.update(
        {
            "tickers": tickers,
            "companies": companies,
            "sector": sector,
            "topic": tag_result.topic,
            "risk_category": tag_result.risk_category,
            "evidence_sentence": evidence_sentence,
        }
    )
    enriched.update(scores)
    return enriched


def error_record(record: dict[str, str], error: Exception) -> dict[str, str]:
    fallback = {column: record.get(column, "") for column in EXPECTED_ARTICLE_COLUMNS}
    fallback.update(
        {
            "event_id": record.get("article_id", ""),
            "source_count": "1" if record.get("source") else "0",
            "sector": record.get("sector", "") or "Unmapped",
            "topic": record.get("topic", "") or "processing error",
            "sentiment_score": "0.000",
            "p_positive": "0.000",
            "p_neutral": "1.000",
            "p_negative": "0.000",
            "optimism": "0.0",
            "fear": "0.0",
            "uncertainty": "100.0",
            "attention": "0.0",
            "attention_weight": "0.0",
            "disagreement": "0.0",
            "disagreement_input": "0.000",
            "risk_intensity": "0.0",
            "risk_category": record.get("risk_category", "") or "processing error",
            "evidence_sentence": record.get("summary", "") or record.get("title", ""),
            "model_confidence": "0.000",
            "relevance_weight": "0.000",
            "time_weight": "0.000000",
            "agg_weight": "0.000000",
            "processing_error": f"{type(error).__name__}: {error}"[:500],
        }
    )
    return fallback


def enrich_records_batch(records: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    sentiment_inputs = [
        (
            record.get("title", ""),
            record.get("summary", ""),
            record.get("content", ""),
        )
        for record in records
    ]
    sentiment_results = analyze_articles_sentiment(sentiment_inputs) if sentiment_inputs else []
    enriched_records: list[dict[str, str]] = []
    error_records: list[dict[str, str]] = []

    for record, sentiment in zip(records, sentiment_results, strict=True):
        try:
            enriched_records.append(enrich_record(record, sentiment))
        except Exception as exc:  # noqa: BLE001 - 单条失败不应中断整批处理
            fallback = error_record(record, exc)
            enriched_records.append(fallback)
            error_records.append(fallback)

    return enriched_records, error_records


def data_source_for_output_path(output_path: Path) -> str:
    resolved = Path(output_path).resolve()
    if resolved == REAL_PROCESSED_ARTICLES_PATH.resolve():
        return REAL_DATA_LABEL
    if resolved == DEMO_PROCESSED_ARTICLES_PATH.resolve():
        return DEMO_DATA_LABEL
    return str(output_path)


def write_pipeline_outputs(output_path: Path, records: list[dict[str, str]], data_source: str) -> None:
    write_article_csv(output_path, records)
    write_article_csv(ERROR_RECORDS_PATH, [record for record in records if record.get("processing_error")])
    write_daily_snapshots(records, data_source)


def process_articles(input_path=None, output_path=None) -> list[dict[str, str]]:
    input_path = input_path or DATA_DIR / "demo_articles.csv"
    output_path = output_path or DATA_DIR / "processed_articles.csv"
    output_path = Path(output_path)
    raw_records = read_article_csv(input_path)
    deduped_records = preprocess_records(raw_records)
    sentiment_inputs = [
        (
            record.get("title", ""),
            record.get("summary", ""),
            record.get("content", ""),
        )
        for record in deduped_records
    ]
    sentiment_results = analyze_articles_sentiment(sentiment_inputs) if sentiment_inputs else []
    enriched_records: list[dict[str, str]] = []
    error_records: list[dict[str, str]] = []

    for record, sentiment in zip(deduped_records, sentiment_results, strict=True):
        try:
            enriched_records.append(enrich_record(record, sentiment))
        except Exception as exc:  # noqa: BLE001 - 单条新闻失败不能中断整批处理
            fallback = error_record(record, exc)
            enriched_records.append(fallback)
            error_records.append(fallback)

    cluster_result = cluster_articles(enriched_records)
    enriched_records = cluster_result.records
    write_article_csv(output_path, enriched_records)
    write_article_csv(ERROR_RECORDS_PATH, error_records)
    write_daily_snapshots(enriched_records, data_source_for_output_path(output_path))
    return enriched_records


def process_articles_incremental(input_path, output_path, new_raw_records=None) -> dict[str, object]:
    output_path = Path(output_path)
    raw_records = read_article_csv(input_path)
    existing_records = read_article_csv(output_path)
    processed_ids = {
        str(record.get("article_id", "")).strip()
        for record in existing_records
        if str(record.get("article_id", "")).strip()
    }

    deduped_records = preprocess_records(raw_records)
    candidate_records = [
        record
        for record in deduped_records
        if str(record.get("article_id", "")).strip() not in processed_ids
    ]
    enriched_new_records, _error_records = enrich_records_batch(candidate_records)

    cluster_result = cluster_articles_incremental(existing_records, enriched_new_records)
    merged_records = cluster_result.records

    write_pipeline_outputs(output_path, merged_records, data_source_for_output_path(output_path))
    new_count = len(enriched_new_records)
    reused_count = len(existing_records)
    print(f"增量处理完成：本次新增 {new_count} 条，复用 {reused_count} 条。")
    return {
        "records": merged_records,
        "new_count": new_count,
        "reused_count": reused_count,
        "total_count": len(merged_records),
    }


def main() -> None:
    records = process_articles()
    print(f"处理完成: {len(records)} 条")


if __name__ == "__main__":
    main()
