"""文章级六维基础分数。

根据情绪概率、风险标签、时间衰减和相关性生成单篇新闻分数。
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

from src.config import (
    RISK_NEGATIVE_PRESSURE_WEIGHT,
    RISK_SEVERITY_WEIGHTS,
    RISK_SENTIMENT_SEVERITY_WEIGHT,
    RISK_UNCERTAINTY_PRESSURE_WEIGHT,
    RISK_USE_SENTIMENT_PRESSURE,
    TIME_DECAY_TAU_HOURS,
    UNCERTAINTY_ENTROPY_WEIGHT,
    UNCERTAINTY_NEUTRAL_WEIGHT,
)
from src.preprocessing import parse_utc_datetime
from src.sentiment_model import ArticleSentiment


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def entropy(values: list[float]) -> float:
    return -sum(value * math.log(value) for value in values if value > 0)


def calculate_uncertainty(sentiment: ArticleSentiment) -> float:
    probabilities = [sentiment.p_positive, sentiment.p_neutral, sentiment.p_negative]
    entropy_norm = entropy(probabilities) / math.log(3)
    return clamp(
        (
            UNCERTAINTY_NEUTRAL_WEIGHT * sentiment.p_neutral
            + UNCERTAINTY_ENTROPY_WEIGHT * entropy_norm
        )
        * 100
    )


def calculate_time_weight(published_at: str, collected_at: str) -> float:
    try:
        published = parse_utc_datetime(published_at)
    except (TypeError, ValueError):
        published = datetime.now(UTC)
    try:
        collected = parse_utc_datetime(collected_at) if collected_at else datetime.now(UTC)
    except (TypeError, ValueError):
        collected = datetime.now(UTC)
    age_hours = max((collected - published).total_seconds() / 3600, 0)
    return math.exp(-age_hours / TIME_DECAY_TAU_HOURS)


def calculate_risk_intensity(risk_category: str, sentiment: ArticleSentiment) -> float:
    severity = RISK_SEVERITY_WEIGHTS.get(risk_category, 3)
    severity_score = severity / 5 * 100
    if not RISK_USE_SENTIMENT_PRESSURE:
        return clamp(severity_score)

    negative_pressure = max(sentiment.p_negative - sentiment.p_positive, 0) * RISK_NEGATIVE_PRESSURE_WEIGHT
    uncertainty_pressure = sentiment.p_neutral * RISK_UNCERTAINTY_PRESSURE_WEIGHT
    return clamp(
        severity_score * RISK_SENTIMENT_SEVERITY_WEIGHT
        + negative_pressure
        + uncertainty_pressure
    )


def score_article(
    sentiment: ArticleSentiment,
    risk_category: str,
    published_at: str,
    collected_at: str,
    relevance_weight: float,
    dedup_factor: float,
) -> dict[str, str]:
    """生成当前数据结构需要的文章级指标字段。"""
    optimism = clamp(sentiment.p_positive * 100)
    fear = clamp(sentiment.p_negative * 100)
    uncertainty = calculate_uncertainty(sentiment)
    time_weight = calculate_time_weight(published_at, collected_at)
    risk_intensity = calculate_risk_intensity(risk_category, sentiment)
    agg_weight = time_weight * relevance_weight * dedup_factor

    return {
        "p_positive": f"{sentiment.p_positive:.3f}",
        "p_neutral": f"{sentiment.p_neutral:.3f}",
        "p_negative": f"{sentiment.p_negative:.3f}",
        "sentiment_score": f"{sentiment.sentiment_score:.3f}",
        "optimism": f"{optimism:.1f}",
        "fear": f"{fear:.1f}",
        "uncertainty": f"{uncertainty:.1f}",
        "attention": "0.0",
        "attention_weight": "0.0",
        "disagreement": "0.0",
        "disagreement_input": f"{sentiment.sentiment_score:.3f}",
        "risk_intensity": f"{risk_intensity:.1f}",
        "model_confidence": f"{sentiment.model_confidence:.3f}",
        "relevance_weight": f"{relevance_weight:.3f}",
        "time_weight": f"{time_weight:.6f}",
        "agg_weight": f"{agg_weight:.6f}",
    }
