"""Topic and risk label detection.

The first version uses separate JSON keyword dictionaries. Results include
matched topics, risk categories, risk evidence sentences, and an optional
sector hint.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache

from src.config import (
    DICTIONARY_DIR,
    RISK_KEYWORD_SENTENCE_SCORE_MULTIPLIER,
    RISK_SEVERITY_WEIGHTS,
)
from src.keyword_matching import distinct_matched_terms, matched_terms_in_sentence, normalized_sentence_hit_score


@dataclass
class TagResult:
    topic: str
    sector_hint: str
    risk_category: str
    risk_evidence_sentence: str
    risk_severity: int
    risk_strengths: dict[str, float]


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
    """Split sentences lightly without adding an nltk dependency for local runs."""
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


def choose_risk(text: str) -> tuple[str, str, int, dict[str, float]]:
    """Return every triggered risk and its sentence-density intensity."""
    sentences = split_sentences(text)
    matches: list[tuple[str, str, int, float]] = []

    for rule in load_risk_rules():
        strong_terms = [str(term) for term in rule.get("keywords", [])]
        weak_terms = [str(term) for term in rule.get("weak_keywords", [])]
        strong_hits = distinct_matched_terms(sentences, strong_terms)
        weak_hits = distinct_matched_terms(sentences, weak_terms)
        min_distinct_hits = max(1, int(rule.get("min_distinct_hits", 1)))
        triggered_terms = strong_terms if strong_hits else []
        if not strong_hits and len(weak_hits) >= min_distinct_hits:
            triggered_terms = weak_terms
        if not triggered_terms:
            continue

        category = str(rule.get("risk_category", "")).strip()
        severity = RISK_SEVERITY_WEIGHTS.get(category)
        if not category or severity is None:
            continue
        intensity = normalized_sentence_hit_score(
            sentences,
            triggered_terms,
            RISK_KEYWORD_SENTENCE_SCORE_MULTIPLIER,
        )
        if intensity <= 0:
            continue
        evidence = next(
            (sentence for sentence in sentences if matched_terms_in_sentence(sentence, triggered_terms)),
            "",
        )
        matches.append((category, evidence, severity, intensity))

    categories = ";".join(match[0] for match in matches)
    evidence = matches[0][1] if matches else ""
    severity = max((match[2] for match in matches), default=0)
    strengths = {match[0]: match[3] for match in matches}
    return categories, evidence, severity, strengths


def tag_article(text: str) -> TagResult:
    topic, sector_hint = choose_topic(text)
    risk_category, risk_sentence, severity, risk_strengths = choose_risk(text)
    return TagResult(
        topic=topic,
        sector_hint=sector_hint,
        risk_category=risk_category,
        risk_evidence_sentence=risk_sentence,
        risk_severity=severity,
        risk_strengths=risk_strengths,
    )
