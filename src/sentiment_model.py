"""词典情绪模型 fallback。

本模块不下载 Hugging Face 模型，适合离线 demo。后续接入 FinBERT 时，
可以保留相同输出结构作为替换接口。
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from functools import lru_cache

from src.config import DICTIONARY_DIR
from src.topic_risk_tagger import split_sentences


@dataclass
class SentenceSentiment:
    sentence: str
    p_positive: float
    p_neutral: float
    p_negative: float
    sentiment_score: float
    model_confidence: float


@dataclass
class ArticleSentiment:
    p_positive: float
    p_neutral: float
    p_negative: float
    sentiment_score: float
    model_confidence: float
    evidence_sentence: str
    sentence_results: list[SentenceSentiment]


@lru_cache(maxsize=1)
def load_sentiment_lexicon() -> dict[str, list[str]]:
    path = DICTIONARY_DIR / "sentiment_lexicon.json"
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def count_terms(text: str, terms: list[str]) -> int:
    lowered = text.lower()
    total = 0
    for term in terms:
        pattern = re.escape(term.lower())
        total += len(re.findall(pattern, lowered))
    return total


def softmax(values: list[float]) -> list[float]:
    max_value = max(values)
    exp_values = [math.exp(value - max_value) for value in values]
    total = sum(exp_values)
    return [value / total for value in exp_values]


def score_sentence(sentence: str) -> SentenceSentiment:
    lexicon = load_sentiment_lexicon()
    positive_hits = count_terms(sentence, lexicon["positive"])
    negative_hits = count_terms(sentence, lexicon["negative"])
    uncertainty_hits = count_terms(sentence, lexicon["uncertainty"])

    raw_positive = 0.4 + positive_hits * 1.2
    raw_negative = 0.4 + negative_hits * 1.2
    raw_neutral = 0.8 + uncertainty_hits * 0.5
    p_positive, p_neutral, p_negative = softmax([raw_positive, raw_neutral, raw_negative])
    sentiment_score = p_positive - p_negative
    confidence = max(p_positive, p_neutral, p_negative)

    return SentenceSentiment(
        sentence=sentence,
        p_positive=p_positive,
        p_neutral=p_neutral,
        p_negative=p_negative,
        sentiment_score=sentiment_score,
        model_confidence=confidence,
    )


def weighted_average(values: list[float], weights: list[float]) -> float:
    total_weight = sum(weights)
    if total_weight <= 0:
        return sum(values) / len(values)
    return sum(value * weight for value, weight in zip(values, weights, strict=True)) / total_weight


def analyze_article_sentiment(title: str, summary: str, content: str) -> ArticleSentiment:
    """按句子打分，再聚合为文章级情绪概率。"""
    text = " ".join([str(title or ""), str(summary or ""), str(content or "")]).strip()
    sentences = split_sentences(text) or [str(title or "")]
    sentence_results = [score_sentence(sentence) for sentence in sentences]
    weights = [max(result.model_confidence, 0.1) for result in sentence_results]

    p_positive = weighted_average([result.p_positive for result in sentence_results], weights)
    p_neutral = weighted_average([result.p_neutral for result in sentence_results], weights)
    p_negative = weighted_average([result.p_negative for result in sentence_results], weights)
    total = p_positive + p_neutral + p_negative
    p_positive, p_neutral, p_negative = p_positive / total, p_neutral / total, p_negative / total

    sentiment_score = p_positive - p_negative
    confidence = max(p_positive, p_neutral, p_negative)

    evidence_candidates = [
        result
        for result in sentence_results
        if result.model_confidence >= 0.6
    ]
    if evidence_candidates:
        evidence = max(evidence_candidates, key=lambda item: abs(item.sentiment_score)).sentence
    else:
        evidence = str(title or "")

    return ArticleSentiment(
        p_positive=p_positive,
        p_neutral=p_neutral,
        p_negative=p_negative,
        sentiment_score=sentiment_score,
        model_confidence=confidence,
        evidence_sentence=evidence,
        sentence_results=sentence_results,
    )
