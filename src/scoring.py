"""Article-level formula components and scores.

Baseline and enhanced outputs share one implementation. The selected weight
group changes only arithmetic coefficients; model probabilities and keyword
components remain reusable inputs persisted in processed CSV files.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import UTC, datetime

from src.config import (
    ACTIVE_WEIGHTS,
    BASELINE_WEIGHTS,
    ENHANCED_WEIGHTS,
    FORMULA_COMPONENT_COLUMNS,
    FORMULA_VERSION_BASELINE,
    FORMULA_VERSION_ENHANCED,
    RISK_COMBINE,
    RISK_NEGATIVE_PRESSURE_WEIGHT,
    RISK_SEVERITY_SCALE_MAX,
    RISK_SENTIMENT_SEVERITY_WEIGHT,
    RISK_SEVERITY_WEIGHTS,
    RISK_UNCERTAINTY_PRESSURE_WEIGHT,
    RISK_USE_SENTIMENT_PRESSURE,
    TIME_DECAY_TAU_HOURS,
)
from src.keyword_signals import keyword_signal_components
from src.preprocessing import parse_utc_datetime
from src.sentiment_model import ArticleSentiment


WeightGroup = Mapping[str, Mapping[str, float]]


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def entropy(values: list[float]) -> float:
    return -sum(value * math.log(value) for value in values if value > 0)


def normalized_entropy(probabilities: list[float]) -> float:
    return clamp(entropy(probabilities) / math.log(3), 0.0, 1.0)


def resolve_weights(weights: WeightGroup | None = None) -> WeightGroup:
    return weights or ACTIVE_WEIGHTS


def formula_version_for_weights(weights: WeightGroup | None = None) -> str:
    resolved = resolve_weights(weights)
    if resolved is BASELINE_WEIGHTS or resolved == BASELINE_WEIGHTS:
        return FORMULA_VERSION_BASELINE
    if resolved is ENHANCED_WEIGHTS or resolved == ENHANCED_WEIGHTS:
        return FORMULA_VERSION_ENHANCED
    return "custom"


def calculate_formula_components_from_probabilities(
    p_positive: float,
    p_neutral: float,
    p_negative: float,
    text: str,
) -> dict[str, float]:
    components = keyword_signal_components(text)
    components["entropy_norm"] = normalized_entropy(
        [p_positive, p_neutral, p_negative]
    )
    return {column: float(components.get(column, 0.0)) for column in FORMULA_COMPONENT_COLUMNS}


def calculate_formula_components(sentiment: ArticleSentiment, text: str) -> dict[str, float]:
    return calculate_formula_components_from_probabilities(
        sentiment.p_positive,
        sentiment.p_neutral,
        sentiment.p_negative,
        text,
    )


def calculate_article_formula_values(
    p_positive: float,
    p_neutral: float,
    p_negative: float,
    components: Mapping[str, float],
    weights: WeightGroup | None = None,
) -> dict[str, float]:
    resolved = resolve_weights(weights)
    optimism_weights = resolved["optimism"]
    fear_weights = resolved["fear"]
    uncertainty_weights = resolved["uncertainty"]

    optimism = 100 * clamp(
        optimism_weights["p_positive"] * p_positive
        + optimism_weights["b_bull"] * float(components.get("b_bull", 0.0))
        + optimism_weights["g_growth"] * float(components.get("g_growth", 0.0)),
        0.0,
        1.0,
    )
    fear = 100 * clamp(
        fear_weights["p_negative"] * p_negative
        + fear_weights["b_bear"] * float(components.get("b_bear", 0.0))
        + fear_weights["s_shock"] * float(components.get("s_shock", 0.0)),
        0.0,
        1.0,
    )
    uncertainty = 100 * clamp(
        uncertainty_weights["p_neutral"] * p_neutral
        + uncertainty_weights["entropy_norm"] * float(components.get("entropy_norm", 0.0))
        + uncertainty_weights["k_unc"] * float(components.get("k_unc", 0.0)),
        0.0,
        1.0,
    )
    return {
        "optimism": optimism,
        "fear": fear,
        "uncertainty": uncertainty,
    }


def calculate_uncertainty(
    sentiment: ArticleSentiment,
    components: Mapping[str, float] | None = None,
    weights: WeightGroup | None = None,
) -> float:
    resolved_components = dict(components or {})
    resolved_components.setdefault(
        "entropy_norm",
        normalized_entropy([sentiment.p_positive, sentiment.p_neutral, sentiment.p_negative]),
    )
    return calculate_article_formula_values(
        sentiment.p_positive,
        sentiment.p_neutral,
        sentiment.p_negative,
        resolved_components,
        weights,
    )["uncertainty"]


def formula_values_from_record(
    record: Mapping[str, object],
    weights: WeightGroup | None = None,
) -> dict[str, float]:
    def numeric(name: str) -> float:
        try:
            return float(record.get(name, 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    components = {column: numeric(column) for column in FORMULA_COMPONENT_COLUMNS}
    return calculate_article_formula_values(
        numeric("p_positive"),
        numeric("p_neutral"),
        numeric("p_negative"),
        components,
        weights,
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


def calculate_risk_intensity(
    risk_category: str,
    sentiment: ArticleSentiment,
    risk_strengths: Mapping[str, float] | None = None,
) -> float:
    categories = [item.strip() for item in str(risk_category or "").split(";") if item.strip()]
    strengths = risk_strengths or {}
    risk_probabilities = [
        (RISK_SEVERITY_WEIGHTS[category] / RISK_SEVERITY_SCALE_MAX)
        * clamp(float(strengths.get(category, 0.0)), 0.0, 1.0)
        for category in categories
        if category in RISK_SEVERITY_WEIGHTS
    ]
    if RISK_COMBINE == "sum":
        combined_risk = clamp(sum(risk_probabilities), 0.0, 1.0)
    elif RISK_COMBINE == "noisy_or":
        combined_risk = 1.0 - math.prod(1.0 - probability for probability in risk_probabilities)
    else:
        raise ValueError(f"Unsupported RISK_COMBINE: {RISK_COMBINE}")
    severity_score = 100 * combined_risk
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
    source_weight: float = 1.0,
    text: str = "",
    weights: WeightGroup | None = None,
    risk_strengths: Mapping[str, float] | None = None,
) -> dict[str, str]:
    """Generate persisted active metrics plus reusable formula components."""
    components = calculate_formula_components(sentiment, text)
    formula_values = calculate_article_formula_values(
        sentiment.p_positive,
        sentiment.p_neutral,
        sentiment.p_negative,
        components,
        weights,
    )
    time_weight = calculate_time_weight(published_at, collected_at)
    risk_intensity = calculate_risk_intensity(risk_category, sentiment, risk_strengths)
    agg_weight = time_weight * relevance_weight * dedup_factor * source_weight

    return {
        "p_positive": f"{sentiment.p_positive:.3f}",
        "p_neutral": f"{sentiment.p_neutral:.3f}",
        "p_negative": f"{sentiment.p_negative:.3f}",
        **{column: f"{components[column]:.6f}" for column in FORMULA_COMPONENT_COLUMNS},
        "sentiment_score": f"{sentiment.sentiment_score:.3f}",
        "optimism": f"{formula_values['optimism']:.1f}",
        "fear": f"{formula_values['fear']:.1f}",
        "uncertainty": f"{formula_values['uncertainty']:.1f}",
        "attention": "0.0",
        "attention_weight": "0.0",
        "disagreement": "0.0",
        "disagreement_input": f"{sentiment.sentiment_score:.3f}",
        "risk_intensity": f"{risk_intensity:.1f}",
        "model_confidence": f"{sentiment.model_confidence:.3f}",
        "relevance_weight": f"{relevance_weight:.3f}",
        "time_weight": f"{time_weight:.6f}",
        "source_weight": f"{source_weight:.3f}",
        "agg_weight": f"{agg_weight:.6f}",
    }
