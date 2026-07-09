"""主题与风险标签识别。

第一版使用独立 JSON 关键词词典。识别结果会给出命中的主题、风险类别、
风险证据句和可选板块提示。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache

from src.config import DICTIONARY_DIR, RISK_SEVERITY_WEIGHTS


@dataclass
class TagResult:
    topic: str
    sector_hint: str
    risk_category: str
    risk_evidence_sentence: str
    risk_severity: int


@lru_cache(maxsize=1)
def load_topic_rules() -> list[dict]:
    path = DICTIONARY_DIR / "topic_keywords.json"
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)["topics"]
    except (OSError, KeyError, json.JSONDecodeError):
        return []


@lru_cache(maxsize=1)
def load_risk_rules() -> list[dict]:
    path = DICTIONARY_DIR / "risk_keywords.json"
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)["risks"]
    except (OSError, KeyError, json.JSONDecodeError):
        return []


def split_sentences(text: str) -> list[str]:
    """轻量分句，避免为本地运行引入 nltk 依赖。"""
    compact = re.sub(r"\s+", " ", str(text or "")).strip()
    if not compact:
        return []
    sentences = re.split(r"(?<=[.!?。！？])\s+", compact)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def keyword_hits(text: str, keywords: list[str]) -> int:
    lowered = text.lower()
    return sum(1 for keyword in keywords if keyword.lower() in lowered)


def choose_topic(text: str) -> tuple[str, str]:
    best_topic = "general market sentiment"
    best_sector_hint = ""
    best_score = 0
    for rule in load_topic_rules():
        score = keyword_hits(text, rule["keywords"])
        if score > best_score:
            best_score = score
            best_topic = rule["topic"]
            best_sector_hint = rule.get("sector_hint", "")
    return best_topic, best_sector_hint


def choose_risk(text: str) -> tuple[str, str, int]:
    best_category = "macro risk"
    best_sentence = ""
    best_score = 0
    sentences = split_sentences(text)

    for rule in load_risk_rules():
        score = keyword_hits(text, rule["keywords"])
        if score > best_score:
            best_score = score
            best_category = rule["risk_category"]
            best_sentence = ""
            for sentence in sentences:
                if keyword_hits(sentence, rule["keywords"]):
                    best_sentence = sentence
                    break

    severity = RISK_SEVERITY_WEIGHTS.get(best_category, 3)
    return best_category, best_sentence, severity


def tag_article(text: str) -> TagResult:
    topic, sector_hint = choose_topic(text)
    risk_category, risk_sentence, severity = choose_risk(text)
    return TagResult(
        topic=topic,
        sector_hint=sector_hint,
        risk_category=risk_category,
        risk_evidence_sentence=risk_sentence,
        risk_severity=severity,
    )
