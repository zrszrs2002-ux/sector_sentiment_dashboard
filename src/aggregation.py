from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.errors import EmptyDataError, ParserError

from src.config import (
    ATTENTION_GROWTH_LOOKBACK_DAYS,
    ATTENTION_MIN_HISTORY_DAYS,
    ATTENTION_WINDOW_DAYS,
    DISAGREEMENT_POLARITY_THRESHOLD,
    METRIC_COLUMNS,
    SECTOR_DAILY_SCORES_PATH,
    SECTORS,
)
from src.scoring import WeightGroup, formula_values_from_record, resolve_weights


WEIGHT_COLUMN = "agg_weight"


def safe_weights(df: pd.DataFrame) -> pd.Series:
    """Return usable aggregation weights, falling back to equal weights."""
    if WEIGHT_COLUMN not in df.columns:
        return pd.Series(1.0, index=df.index)

    weights = pd.to_numeric(df[WEIGHT_COLUMN], errors="coerce").fillna(0).clip(lower=0)
    if float(weights.sum()) <= 0:
        return pd.Series(1.0, index=df.index)
    return weights


def weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    clean_values = pd.to_numeric(values, errors="coerce").fillna(0)
    clean_weights = weights.reindex(clean_values.index).fillna(0)
    total_weight = float(clean_weights.sum())
    if total_weight <= 0:
        return float(clean_values.mean()) if len(clean_values) else 0.0
    return float((clean_values * clean_weights).sum() / total_weight)


def weighted_std(values: pd.Series, weights: pd.Series) -> float:
    """Calculate weighted population standard deviation; n < 2 returns zero."""
    clean_values = pd.to_numeric(values, errors="coerce").fillna(0)
    if len(clean_values) < 2:
        return 0.0

    clean_weights = weights.reindex(clean_values.index).fillna(0)
    total_weight = float(clean_weights.sum())
    if total_weight <= 0:
        return float(clean_values.std(ddof=0))

    mean_value = weighted_mean(clean_values, clean_weights)
    variance = float((clean_weights * (clean_values - mean_value) ** 2).sum() / total_weight)
    return float(np.sqrt(max(variance, 0.0)))


def apply_article_formula(df: pd.DataFrame, weights: WeightGroup | None = None) -> pd.DataFrame:
    """Recalculate O/F/U from persisted probabilities and components only."""
    if df.empty:
        return df.copy()
    recalculated = df.copy()
    values = [formula_values_from_record(row, weights) for row in recalculated.to_dict("records")]
    formula_df = pd.DataFrame(values, index=recalculated.index)
    for column in ["optimism", "fear", "uncertainty"]:
        recalculated[column] = formula_df[column]
    return recalculated


def rank_percentile_scale(weighted_volume: pd.Series) -> pd.Series:
    """Map cross-sector average ranks to 0-100 without endpoint pileups."""
    if weighted_volume.empty:
        return weighted_volume
    ranks = weighted_volume.rank(method="average", ascending=True)
    sector_count = len(weighted_volume)
    return 100 * (ranks - 0.5) / sector_count


def attention_window(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    working = df.copy()
    working["published_at"] = pd.to_datetime(working["published_at"], utc=True, errors="coerce")
    working["collected_at"] = pd.to_datetime(working["collected_at"], utc=True, errors="coerce")
    reference_time = working["collected_at"].max()
    if pd.isna(reference_time):
        reference_time = working["published_at"].max()
    if pd.isna(reference_time):
        return working
    window_start = reference_time - pd.Timedelta(days=ATTENTION_WINDOW_DAYS)
    return working[working["published_at"] >= window_start].copy()


def attention_volume_by_sector(df: pd.DataFrame) -> pd.Series:
    current_window = attention_window(df)
    if current_window.empty:
        return pd.Series(0.0, index=SECTORS, dtype=float)
    current_window["_weighted_news_volume"] = safe_weights(current_window)
    return (
        current_window.groupby("sector")["_weighted_news_volume"]
        .sum()
        .reindex(SECTORS, fill_value=0.0)
        .astype(float)
    )


def _read_attention_history(data_source: str | None) -> pd.DataFrame:
    if not data_source or not SECTOR_DAILY_SCORES_PATH.exists():
        return pd.DataFrame()
    try:
        history = pd.read_csv(SECTOR_DAILY_SCORES_PATH)
    except (OSError, EmptyDataError, ParserError, UnicodeDecodeError):
        return pd.DataFrame()
    if "data_source" not in history or "sector" not in history or "snapshot_date" not in history:
        return pd.DataFrame()
    history = history[history["data_source"].astype(str).eq(str(data_source))].copy()
    history["snapshot_date"] = pd.to_datetime(history["snapshot_date"], errors="coerce")
    article_count = pd.to_numeric(history.get("article_count", 0), errors="coerce").fillna(0)
    if "attention_volume" not in history:
        history["attention_volume"] = article_count
    else:
        history["attention_volume"] = pd.to_numeric(
            history["attention_volume"], errors="coerce"
        ).fillna(article_count)
    history = history.dropna(subset=["snapshot_date", "attention_volume"])
    return history.sort_values("snapshot_timestamp" if "snapshot_timestamp" in history else "snapshot_date")


def _prepare_attention_history(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty:
        return pd.DataFrame(columns=["snapshot_date", "sector", "attention_volume"])
    required_columns = {"snapshot_date", "sector"}
    if not required_columns.issubset(history.columns):
        return pd.DataFrame(columns=["snapshot_date", "sector", "attention_volume"])
    prepared = history.copy()
    prepared["snapshot_date"] = pd.to_datetime(prepared["snapshot_date"], errors="coerce")
    article_count = pd.to_numeric(prepared.get("article_count", 0), errors="coerce").fillna(0)
    if "attention_volume" not in prepared:
        prepared["attention_volume"] = article_count
    else:
        prepared["attention_volume"] = pd.to_numeric(
            prepared["attention_volume"], errors="coerce"
        ).fillna(article_count)
    prepared = prepared.dropna(subset=["snapshot_date", "attention_volume"])
    prepared = prepared[prepared["snapshot_date"].dt.date < pd.Timestamp.now(tz="UTC").date()]
    return prepared.sort_values("snapshot_date").drop_duplicates(["snapshot_date", "sector"], keep="last")


def attention_history_day_counts(
    data_source: str | None = None,
    history: pd.DataFrame | None = None,
) -> dict[str, int]:
    prepared = _prepare_attention_history(history if history is not None else _read_attention_history(data_source))
    if prepared.empty:
        return {sector: 0 for sector in SECTORS}
    return {
        sector: int(prepared[prepared["sector"].astype(str).eq(sector)]["snapshot_date"].nunique())
        for sector in SECTORS
    }


def empirical_cdf(value: float, history_values: pd.Series) -> float:
    clean = pd.to_numeric(history_values, errors="coerce").dropna()
    if clean.empty:
        return 0.0
    return float((clean <= value).mean())


def growth_series(volumes: pd.Series) -> pd.Series:
    clean = pd.to_numeric(volumes, errors="coerce").dropna().reset_index(drop=True)
    values: list[float] = []
    for index in range(ATTENTION_GROWTH_LOOKBACK_DAYS, len(clean)):
        previous = clean.iloc[index - ATTENTION_GROWTH_LOOKBACK_DAYS : index]
        previous_mean = float(previous.mean())
        values.append((float(clean.iloc[index]) - previous_mean) / (previous_mean + 1.0))
    return pd.Series(values, dtype=float)


def attention_by_sector(
    df: pd.DataFrame,
    weights: WeightGroup | None = None,
    data_source: str | None = None,
    history: pd.DataFrame | None = None,
) -> dict[str, float]:
    """Use own-history ECDF after 30 days; otherwise use cross-sectional cold start."""
    if df.empty:
        return {sector: 0.0 for sector in SECTORS}

    resolved = resolve_weights(weights)
    current_volume = attention_volume_by_sector(df)
    cold_scores = rank_percentile_scale(current_volume)
    prepared_history = _prepare_attention_history(
        history if history is not None else _read_attention_history(data_source)
    )
    scores = {sector: float(cold_scores.get(sector, 0.0)) for sector in SECTORS}
    switched_sectors: list[str] = []

    for sector in SECTORS:
        sector_history = prepared_history[prepared_history["sector"].astype(str).eq(sector)].copy()
        if sector_history["snapshot_date"].nunique() < ATTENTION_MIN_HISTORY_DAYS:
            continue
        volumes = sector_history.sort_values("snapshot_date")["attention_volume"]
        volume_ecdf = empirical_cdf(float(current_volume.get(sector, 0.0)), volumes)
        previous = volumes.tail(ATTENTION_GROWTH_LOOKBACK_DAYS)
        previous_mean = float(previous.mean())
        current_growth = (float(current_volume.get(sector, 0.0)) - previous_mean) / (previous_mean + 1.0)
        growth_ecdf = empirical_cdf(current_growth, growth_series(volumes))
        attention_weights = resolved["attention"]
        scores[sector] = float(
            np.clip(
                100
                * (
                    attention_weights["volume_ecdf"] * volume_ecdf
                    + attention_weights["growth_ecdf"] * growth_ecdf
                ),
                0,
                100,
            )
        )
        switched_sectors.append(sector)

    if switched_sectors:
        print(
            "Attention 已切换自身历史 ECDF + 增长率路径："
            + "、".join(switched_sectors)
            + f"（历史至少 {ATTENTION_MIN_HISTORY_DAYS} 天）。"
        )
    return scores


def polarity_mix(
    sentiment_scores: pd.Series,
    weights: pd.Series,
    threshold: float = DISAGREEMENT_POLARITY_THRESHOLD,
) -> float:
    scores = pd.to_numeric(sentiment_scores, errors="coerce").fillna(0)
    clean_weights = weights.reindex(scores.index).fillna(0)
    total_weight = float(clean_weights.sum())
    if len(scores) < 2 or total_weight <= 0:
        return 0.0
    positive_share = float(clean_weights[scores > threshold].sum() / total_weight)
    negative_share = float(clean_weights[scores < -threshold].sum() / total_weight)
    return 2 * min(positive_share, negative_share)


def sector_metrics(
    df: pd.DataFrame,
    weights: WeightGroup | None = None,
    data_source: str | None = None,
    attention_history: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Calculate sector metrics with one formula implementation and supplied weights."""
    if df.empty:
        return pd.DataFrame(columns=["sector", "article_count", *METRIC_COLUMNS])

    resolved = resolve_weights(weights)
    working = apply_article_formula(df, resolved)
    attention_scores = attention_by_sector(
        working,
        resolved,
        data_source=data_source,
        history=attention_history,
    )
    rows: list[dict[str, float | str | int]] = []

    for sector in SECTORS:
        group = working[working["sector"] == sector].copy()
        if group.empty:
            rows.append(
                {
                    "sector": sector,
                    "article_count": 0,
                    "optimism": 0.0,
                    "fear": 0.0,
                    "uncertainty": 0.0,
                    "attention": attention_scores.get(sector, 0.0),
                    "disagreement": 0.0,
                    "risk_intensity": 0.0,
                }
            )
            continue

        group_weights = safe_weights(group)
        weighted_risk = weighted_mean(group["risk_intensity"], group_weights)
        if len(group) < 3:
            risk_p90 = weighted_risk
        else:
            risk_p90 = float(pd.to_numeric(group["risk_intensity"], errors="coerce").fillna(0).quantile(0.9))

        sentiment_std = float(np.clip(weighted_std(group["sentiment_score"], group_weights), 0, 1))
        mix = polarity_mix(group["sentiment_score"], group_weights)
        disagreement_weights = resolved["disagreement"]
        disagreement = 100 * (
            disagreement_weights["weighted_std"] * sentiment_std
            + disagreement_weights["polarity_mix"] * mix
        )
        risk_weights = resolved["risk_intensity"]
        rows.append(
            {
                "sector": sector,
                "article_count": int(len(group)),
                "optimism": weighted_mean(group["optimism"], group_weights),
                "fear": weighted_mean(group["fear"], group_weights),
                "uncertainty": weighted_mean(group["uncertainty"], group_weights),
                "attention": attention_scores.get(sector, 0.0),
                "disagreement": float(np.clip(disagreement, 0, 100)),
                "risk_intensity": (
                    risk_weights["weighted_mean"] * weighted_risk
                    + risk_weights["p90"] * risk_p90
                ),
            }
        )

    return pd.DataFrame(rows)


def market_metrics(
    df: pd.DataFrame,
    weights: WeightGroup | None = None,
    data_source: str | None = None,
    attention_history: pd.DataFrame | None = None,
) -> dict[str, float]:
    """Market radar uses an equal average across the 11 sector rows."""
    sectors = sector_metrics(
        df,
        weights=resolve_weights(weights),
        data_source=data_source,
        attention_history=attention_history,
    )
    if sectors.empty:
        return {column: 0.0 for column in METRIC_COLUMNS}
    return {column: float(sectors[column].mean()) for column in METRIC_COLUMNS}


def top_articles(
    df: pd.DataFrame,
    sort_column: str,
    limit: int = 5,
    ascending: bool = False,
) -> pd.DataFrame:
    if df.empty or sort_column not in df.columns:
        return df.head(0)
    return df.sort_values(sort_column, ascending=ascending).head(limit)
