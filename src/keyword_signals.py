"""Sentence-level financial keyword components used by enhanced formulas."""

from __future__ import annotations

import json
from functools import lru_cache

from src.config import DICTIONARY_DIR, KEYWORD_SENTENCE_SCORE_MULTIPLIER
from src.keyword_matching import (
    matched_terms_in_sentence,
    normalize_for_keyword_match,
    normalized_sentence_hit_score as _normalized_sentence_hit_score,
)
from src.sentiment_model import load_sentiment_lexicon
from src.topic_risk_tagger import split_sentences


SIGNAL_KEYS = ("b_bull", "b_bear", "g_growth", "s_shock", "k_unc")


@lru_cache(maxsize=4)
def _load_json(path_name: str) -> dict[str, list[str]]:
    path = DICTIONARY_DIR / path_name
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        str(key): [str(term).strip().lower() for term in value if str(term).strip()]
        for key, value in payload.items()
        if isinstance(value, list)
    }


@lru_cache(maxsize=1)
def signal_terms() -> dict[str, list[str]]:
    stance = _load_json("stance_keywords.json")
    growth = _load_json("growth_keywords.json")
    shock = _load_json("shock_keywords.json")
    uncertainty = load_sentiment_lexicon().get("uncertainty", [])
    return {
        "b_bull": stance.get("bullish", []),
        "b_bear": stance.get("bearish", []),
        "g_growth": growth.get("growth", []),
        "s_shock": shock.get("shock", []),
        "k_unc": [str(term).strip().lower() for term in uncertainty if str(term).strip()],
    }


def normalized_sentence_hit_score(
    sentences: list[str],
    terms: list[str],
    multiplier: float = KEYWORD_SENTENCE_SCORE_MULTIPLIER,
) -> float:
    """Return min(hit sentence count / total sentence count * multiplier, 1)."""
    return _normalized_sentence_hit_score(sentences, terms, multiplier)


def keyword_signal_components(text: str) -> dict[str, float]:
    sentences = split_sentences(text)
    terms_by_signal = signal_terms()
    return {
        signal: normalized_sentence_hit_score(sentences, terms_by_signal.get(signal, []))
        for signal in SIGNAL_KEYS
    }


def matched_signal_terms(text: str) -> dict[str, list[str]]:
    sentences = split_sentences(text)
    terms_by_signal = signal_terms()
    result: dict[str, list[str]] = {}
    for signal in SIGNAL_KEYS:
        matches: list[str] = []
        seen: set[str] = set()
        for sentence in sentences:
            for term in matched_terms_in_sentence(sentence, terms_by_signal.get(signal, [])):
                if term not in seen:
                    seen.add(term)
                    matches.append(term)
        result[signal] = matches
    return result
