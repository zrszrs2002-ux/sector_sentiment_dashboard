"""公司、ticker 与板块映射。

第一版使用 JSON 词典、别名匹配和 ticker regex。若新闻没有明确公司，
则退回到板块关键词映射。
"""

from __future__ import annotations

import json
import re
from collections import Counter
from functools import lru_cache

from src.config import DICTIONARY_DIR, RELEVANCE_WEIGHTS


WORD_BOUNDARY_TEMPLATE = r"(?<![A-Za-z0-9]){term}(?![A-Za-z0-9])"


@lru_cache(maxsize=1)
def load_company_mapping() -> dict:
    path = DICTIONARY_DIR / "company_sector_mapping.json"
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def contains_term(text: str, term: str, ignore_case: bool = True) -> bool:
    escaped = re.escape(term)
    pattern = WORD_BOUNDARY_TEMPLATE.format(term=escaped)
    flags = re.IGNORECASE if ignore_case else 0
    return re.search(pattern, text, flags=flags) is not None


def detect_companies(text: str) -> list[dict[str, str]]:
    """识别文本中出现的公司和 ticker。"""
    normalized_text = normalize_text(text)
    mapping = load_company_mapping()
    matches: list[dict[str, str]] = []

    for item in mapping["companies"]:
        alias_hit = any(contains_term(normalized_text, alias, ignore_case=True) for alias in item["aliases"])
        ticker_hit = contains_term(normalized_text, item["ticker"], ignore_case=False)
        if alias_hit or ticker_hit:
            matches.append(
                {
                    "company": item["company"],
                    "ticker": item["ticker"],
                    "sector": item["sector"],
                    "match_type": "ticker_or_company" if ticker_hit else "company",
                }
            )

    return matches


def infer_sector_from_keywords(text: str) -> str:
    """在未识别到公司时，根据主题关键词推断板块。"""
    normalized_text = normalize_text(text).lower()
    mapping = load_company_mapping()
    sector_scores: Counter[str] = Counter()

    for sector, keywords in mapping["sector_keywords"].items():
        for keyword in keywords:
            if keyword.lower() in normalized_text:
                sector_scores[sector] += 1

    if not sector_scores:
        return ""
    return sector_scores.most_common(1)[0][0]


def map_article(text: str) -> dict[str, str]:
    """返回文章的公司、ticker、板块和相关性权重。"""
    company_matches = detect_companies(text)
    if company_matches:
        sector_counts = Counter(match["sector"] for match in company_matches)
        sector = sector_counts.most_common(1)[0][0]
        companies = sorted({match["company"] for match in company_matches})
        tickers = sorted({match["ticker"] for match in company_matches})
        return {
            "companies": ";".join(companies),
            "tickers": ";".join(tickers),
            "sector": sector,
            "mapping_method": "company_or_ticker",
            "relevance_weight": str(RELEVANCE_WEIGHTS["company_or_ticker"]),
        }

    inferred_sector = infer_sector_from_keywords(text)
    if inferred_sector:
        return {
            "companies": "",
            "tickers": "",
            "sector": inferred_sector,
            "mapping_method": "topic_only",
            "relevance_weight": str(RELEVANCE_WEIGHTS["topic_only"]),
        }

    return {
        "companies": "",
        "tickers": "",
        "sector": "Unmapped",
        "mapping_method": "unmapped",
        "relevance_weight": "0.5",
    }
