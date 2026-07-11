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
    FULLTEXT_SENTIMENT_COLUMNS,
    REAL_PROCESSED_ARTICLES_PATH,
    RELEVANCE_WEIGHTS,
)
from src.daily_snapshots import write_daily_snapshots
from src.data_loader import DEMO_DATA_LABEL, REAL_DATA_LABEL
from src.event_clustering import cluster_articles, cluster_articles_incremental
from src.mapping import map_article
from src.preprocessing import preprocess_records, read_article_csv, write_article_csv
from src.scoring import (
    calculate_article_formula_values,
    calculate_formula_components_from_probabilities,
    score_article,
)
from src.rss_sources import source_weight_for_names
from src.sentiment_model import ArticleSentiment, analyze_article_sentiment, analyze_articles_sentiment
from src.topic_risk_tagger import split_sentences, tag_article
from src.topic_risk_tagger import TagResult


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


def merge_tag_results(summary: TagResult, fulltext: TagResult | None) -> TagResult:
    if fulltext is None:
        return summary

    summary_categories = split_semicolon_values(summary.risk_category)
    fulltext_categories = split_semicolon_values(fulltext.risk_category)
    strengths = dict(summary.risk_strengths)
    for category, strength in fulltext.risk_strengths.items():
        strengths[category] = max(strengths.get(category, 0.0), float(strength))

    topic = summary.topic
    sector_hint = summary.sector_hint
    if (
        fulltext.topic
        and fulltext.topic != "general market sentiment"
        and summary.topic == "general market sentiment"
    ):
        topic = fulltext.topic
        sector_hint = summary.sector_hint or fulltext.sector_hint

    added_risk = bool(set(fulltext_categories) - set(summary_categories))
    return TagResult(
        topic=topic,
        sector_hint=sector_hint,
        risk_category=merge_semicolon_values(summary.risk_category, fulltext.risk_category),
        risk_evidence_sentence=(
            fulltext.risk_evidence_sentence if added_risk else summary.risk_evidence_sentence
        ),
        risk_severity=max(summary.risk_severity, fulltext.risk_severity),
        risk_strengths=strengths,
    )


def article_text(record: dict[str, str]) -> str:
    fields = ["title", "summary", "body_text"] if record.get("body_text") else ["title", "summary", "content"]
    return join_sentence_parts(article_parts(record, fields))

def summary_article_text(record: dict[str, str]) -> str:
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
    fields = ["body_text", "summary"] if record.get("body_text") else ["summary", "content"]
    return join_sentence_parts(article_parts(record, fields))


def sentiment_content(record: dict[str, str]) -> str:
    return str(record.get("content", "") or record.get("summary", "") or "")


def fulltext_sentiment_content(record: dict[str, str]) -> str:
    return str(record.get("body_text", "") or "")


def numeric_or_default(value: object, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


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


def fulltext_evidence_sentence(record: dict[str, str], sentiment: ArticleSentiment | None) -> str:
    if sentiment is None:
        return ""
    body_key = normalize_evidence_text(record.get("body_text", ""))
    body_candidates = [
        result
        for result in sentiment.sentence_results
        if normalize_evidence_text(result.sentence)
        and normalize_evidence_text(result.sentence) in body_key
    ]
    if not body_candidates:
        return ""
    best = max(
        body_candidates,
        key=lambda result: abs(result.sentiment_score) * max(result.model_confidence, 0.01),
    )
    return best.sentence


def choose_preferred_evidence_sentence(
    record: dict[str, str],
    tag_result: TagResult,
    sentiment: ArticleSentiment,
    fulltext_tag_result: TagResult | None = None,
    fulltext_sentiment: ArticleSentiment | None = None,
) -> str:
    title = str(record.get("title", "") or "")

    candidates: list[str] = []
    if fulltext_tag_result is not None:
        candidates.append(fulltext_tag_result.risk_evidence_sentence)
    candidates.append(fulltext_evidence_sentence(record, fulltext_sentiment))
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


def enrich_record(
    record: dict[str, str],
    sentiment: ArticleSentiment | None = None,
    fulltext_sentiment: ArticleSentiment | None = None,
) -> dict[str, str]:
    summary_text = summary_article_text(record)
    mapping_result = map_article(mapping_text(record))
    summary_tag_result = tag_article(summary_text)
    body_text = fulltext_sentiment_content(record)
    fulltext_tag_result = tag_article(body_text) if body_text else None
    tag_result = merge_tag_results(summary_tag_result, fulltext_tag_result)
    if sentiment is None:
        sentiment = analyze_article_sentiment(
            record.get("title", ""),
            record.get("summary", ""),
            sentiment_content(record),
        )
    if body_text and fulltext_sentiment is None:
        fulltext_sentiment = analyze_article_sentiment(
            record.get("title", ""),
            record.get("summary", ""),
            body_text,
        )

    sector = mapping_result["sector"]
    companies = merge_semicolon_values(mapping_result["companies"], record.get("companies", ""))
    tickers = merge_semicolon_values(mapping_result["tickers"], record.get("tickers", ""))
    relevance_weight = float(mapping_result["relevance_weight"])
    source_weight = numeric_or_default(
        record.get("source_weight"),
        source_weight_for_names(record.get("source", "")),
    )
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
        source_weight=source_weight,
        text=summary_text,
        risk_strengths=tag_result.risk_strengths,
    )

    evidence_sentence = choose_preferred_evidence_sentence(
        record,
        tag_result,
        sentiment,
        fulltext_tag_result,
        fulltext_sentiment,
    )

    enriched = {column: record.get(column, "") for column in EXPECTED_ARTICLE_COLUMNS}
    enriched.update(
        {
            "tickers": tickers,
            "companies": companies,
            "publisher": record.get("publisher", "") or record.get("source", ""),
            "content_level": record.get("content_level", "") or (
                "fulltext" if record.get("body_text") else "summary"
            ),
            "rescored": record.get("rescored", "") or "False",
            "sector": sector,
            "topic": tag_result.topic,
            "risk_category": tag_result.risk_category,
            "evidence_sentence": evidence_sentence,
        }
    )
    enriched.update(scores)
    if body_text and fulltext_sentiment is not None:
        enriched.update(
            {
                "sentiment_score_fulltext": f"{fulltext_sentiment.sentiment_score:.3f}",
                "p_positive_fulltext": f"{fulltext_sentiment.p_positive:.3f}",
                "p_neutral_fulltext": f"{fulltext_sentiment.p_neutral:.3f}",
                "p_negative_fulltext": f"{fulltext_sentiment.p_negative:.3f}",
            }
        )
    else:
        enriched.update({column: "" for column in FULLTEXT_SENTIMENT_COLUMNS})
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
            "b_bull": "0.000000",
            "b_bear": "0.000000",
            "g_growth": "0.000000",
            "s_shock": "0.000000",
            "k_unc": "0.000000",
            "entropy_norm": "0.000000",
            "optimism": "0.0",
            "fear": "0.0",
            "uncertainty": "40.0",
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


def upgrade_formula_fields(record: dict[str, str]) -> bool:
    """Backfill reusable components and ACTIVE scores without rerunning FinBERT."""
    component_columns = ["b_bull", "b_bear", "g_growth", "s_shock", "k_unc", "entropy_norm"]
    if all(str(record.get(column, "")).strip() for column in component_columns):
        return False

    def numeric(name: str) -> float:
        try:
            return float(record.get(name, 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    p_positive = numeric("p_positive")
    p_neutral = numeric("p_neutral")
    p_negative = numeric("p_negative")
    components = calculate_formula_components_from_probabilities(
        p_positive,
        p_neutral,
        p_negative,
        article_text(record),
    )
    formula_values = calculate_article_formula_values(
        p_positive,
        p_neutral,
        p_negative,
        components,
    )
    record.update({column: f"{value:.6f}" for column, value in components.items()})
    record.update({column: f"{value:.1f}" for column, value in formula_values.items()})
    return True


def upgrade_source_fields(record: dict[str, str]) -> bool:
    """Backfill publisher/source weight and r3 aggregation weight without rerunning models."""
    before = (
        str(record.get("publisher", "")),
        str(record.get("source_weight", "")),
        str(record.get("agg_weight", "")),
        str(record.get("content_level", "")),
        str(record.get("rescored", "")),
    )
    record["publisher"] = str(record.get("publisher", "") or record.get("source", ""))
    source_weight = numeric_or_default(
        record.get("source_weight"),
        source_weight_for_names(record.get("source", "")),
    )
    record["source_weight"] = f"{source_weight:.3f}"
    try:
        agg_weight = (
            float(record.get("time_weight", 0) or 0)
            * float(record.get("relevance_weight", 0) or 0)
            * float(record.get("dedup_factor", 1) or 1)
            * source_weight
        )
    except (TypeError, ValueError):
        agg_weight = 0.0
    record["agg_weight"] = f"{agg_weight:.6f}"
    record["content_level"] = str(record.get("content_level", "") or (
        "fulltext" if record.get("body_text") else "summary"
    ))
    record["rescored"] = str(record.get("rescored", "") or "False")
    after = (
        record["publisher"],
        record["source_weight"],
        record["agg_weight"],
        record["content_level"],
        record["rescored"],
    )
    return before != after


def sync_source_context_from_raw(
    processed_records: list[dict[str, str]], raw_records: list[dict[str, str]]
) -> int:
    raw_by_id = {
        str(record.get("article_id", "")): record
        for record in raw_records
        if str(record.get("article_id", ""))
    }
    updated = 0
    for record in processed_records:
        raw = raw_by_id.get(str(record.get("article_id", "")))
        if not raw:
            continue
        before = (record.get("source", ""), record.get("publisher", ""), record.get("source_weight", ""))
        record["source"] = raw.get("source", "") or record.get("source", "")
        record["publisher"] = raw.get("publisher", "") or record.get("publisher", "")
        record["source_weight"] = raw.get("source_weight", "") or record.get("source_weight", "")
        after = (record.get("source", ""), record.get("publisher", ""), record.get("source_weight", ""))
        updated += before != after
    return updated


def enrich_records_batch(records: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    sentiment_inputs = [
        (
            record.get("title", ""),
            record.get("summary", ""),
            sentiment_content(record),
        )
        for record in records
    ]
    sentiment_results = analyze_articles_sentiment(sentiment_inputs) if sentiment_inputs else []
    fulltext_positions = [
        index for index, record in enumerate(records) if fulltext_sentiment_content(record)
    ]
    fulltext_inputs = [
        (
            records[index].get("title", ""),
            records[index].get("summary", ""),
            fulltext_sentiment_content(records[index]),
        )
        for index in fulltext_positions
    ]
    fulltext_results = analyze_articles_sentiment(fulltext_inputs) if fulltext_inputs else []
    fulltext_by_position = dict(zip(fulltext_positions, fulltext_results, strict=True))
    enriched_records: list[dict[str, str]] = []
    error_records: list[dict[str, str]] = []

    for index, (record, sentiment) in enumerate(zip(records, sentiment_results, strict=True)):
        try:
            enriched_records.append(
                enrich_record(record, sentiment, fulltext_by_position.get(index))
            )
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
    enriched_records, error_records = enrich_records_batch(deduped_records)

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
    source_context_count = sync_source_context_from_raw(existing_records, raw_records)
    if source_context_count:
        print(f"来源上下文同步完成：{source_context_count} 条历史 processed 记录吸收 raw 中的新 publisher/source。")
    source_upgrade_count = sum(1 for record in existing_records if upgrade_source_fields(record))
    if source_upgrade_count:
        print(
            f"来源字段迁移完成：为 {source_upgrade_count} 条历史新闻补齐 publisher/source_weight，"
            "并按 r3 公式重算 agg_weight。"
        )
    upgraded_count = sum(1 for record in existing_records if upgrade_formula_fields(record))
    if upgraded_count:
        print(f"公式组件迁移完成：复用现有模型概率，为 {upgraded_count} 条历史新闻补齐 enhanced 组件。")
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
