"""文章处理流水线。

把第二阶段的原始 demo CSV 转换为第三阶段的结构化新闻输出：
公司/ticker/板块映射、主题标签、风险标签、词典情绪 fallback 和文章级基础分数。
"""

from __future__ import annotations

import re

from src.config import DATA_DIR, EXPECTED_ARTICLE_COLUMNS, RELEVANCE_WEIGHTS
from src.mapping import map_article
from src.preprocessing import preprocess_records, read_article_csv, write_article_csv
from src.scoring import score_article
from src.sentiment_model import analyze_article_sentiment
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


def article_text(record: dict[str, str]) -> str:
    return join_sentence_parts(article_parts(record, ["title", "summary", "content"]))


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


def enrich_record(record: dict[str, str]) -> dict[str, str]:
    text = article_text(record)
    mapping_result = map_article(text)
    tag_result = tag_article(text)
    sentiment = analyze_article_sentiment(
        record.get("title", ""),
        record.get("summary", ""),
        record.get("content", ""),
    )

    sector = mapping_result["sector"]
    companies = mapping_result["companies"] or record.get("companies", "")
    tickers = mapping_result["tickers"] or record.get("tickers", "")
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


def process_articles(input_path=None, output_path=None) -> list[dict[str, str]]:
    input_path = input_path or DATA_DIR / "demo_articles.csv"
    output_path = output_path or DATA_DIR / "processed_articles.csv"
    raw_records = read_article_csv(input_path)
    deduped_records = preprocess_records(raw_records)
    enriched_records = [enrich_record(record) for record in deduped_records]
    write_article_csv(output_path, enriched_records)
    return enriched_records


def main() -> None:
    records = process_articles()
    print(f"处理完成: {len(records)} 条")


if __name__ == "__main__":
    main()
