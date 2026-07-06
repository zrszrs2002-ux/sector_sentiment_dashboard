from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import (
    ATTENTION_WINDOW_DAYS,
    METRIC_COLUMNS,
    RISK_AVG_WEIGHT,
    RISK_P90_WEIGHT,
    SECTORS,
)


WEIGHT_COLUMN = "agg_weight"


def safe_weights(df: pd.DataFrame) -> pd.Series:
    """返回可用的聚合权重；缺失或全零时回退到等权。"""
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
    """计算加权标准差；样本少于 2 条时返回 0。"""
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


def rank_percentile_scale(weighted_volume: pd.Series) -> pd.Series:
    """用平均排名分位数映射到 0-100，避免 min-max 的 0/100 极端挤压。"""
    if weighted_volume.empty:
        return weighted_volume
    ranks = weighted_volume.rank(method="average", ascending=True)
    sector_count = len(weighted_volume)
    return 100 * (ranks - 0.5) / sector_count


def attention_by_sector(df: pd.DataFrame) -> dict[str, float]:
    """用当前窗口内板块加权新闻量的横向排名分位数计算 Attention。"""
    if df.empty:
        return {sector: 0.0 for sector in SECTORS}

    working = df.copy()
    working["published_at"] = pd.to_datetime(working["published_at"], utc=True, errors="coerce")
    working["collected_at"] = pd.to_datetime(working["collected_at"], utc=True, errors="coerce")
    reference_time = working["collected_at"].max()
    if pd.isna(reference_time):
        reference_time = working["published_at"].max()

    if pd.isna(reference_time):
        current_window = working
    else:
        window_start = reference_time - pd.Timedelta(days=ATTENTION_WINDOW_DAYS)
        current_window = working[working["published_at"] >= window_start]

    current_window = current_window.copy()
    current_window["_weighted_news_volume"] = safe_weights(current_window)
    weighted_volume = (
        current_window.groupby("sector")["_weighted_news_volume"]
        .sum()
        .reindex(SECTORS, fill_value=0.0)
    )
    scaled = rank_percentile_scale(weighted_volume)
    return {sector: float(score) for sector, score in scaled.items()}


def sector_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """计算板块级六维雷达指标。"""
    if df.empty:
        return pd.DataFrame(columns=["sector", "article_count", *METRIC_COLUMNS])

    attention_scores = attention_by_sector(df)
    rows: list[dict[str, float | str | int]] = []

    for sector in SECTORS:
        group = df[df["sector"] == sector].copy()
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

        weights = safe_weights(group)
        weighted_risk = weighted_mean(group["risk_intensity"], weights)
        if len(group) < 3:
            risk_p90 = weighted_risk
        else:
            risk_p90 = float(pd.to_numeric(group["risk_intensity"], errors="coerce").fillna(0).quantile(0.9))

        sentiment_std = weighted_std(group["sentiment_score"], weights)
        rows.append(
            {
                "sector": sector,
                "article_count": int(len(group)),
                "optimism": weighted_mean(group["optimism"], weights),
                "fear": weighted_mean(group["fear"], weights),
                "uncertainty": weighted_mean(group["uncertainty"], weights),
                "attention": attention_scores.get(sector, 0.0),
                "disagreement": float(np.clip(sentiment_std, 0, 1) * 100),
                "risk_intensity": RISK_AVG_WEIGHT * weighted_risk + RISK_P90_WEIGHT * risk_p90,
            }
        )

    return pd.DataFrame(rows)


def market_metrics(df: pd.DataFrame) -> dict[str, float]:
    """市场级雷达采用板块等权平均，避免新闻量过度集中到少数板块。"""
    sectors = sector_metrics(df)
    if sectors.empty:
        return {column: 0.0 for column in METRIC_COLUMNS}
    return {column: float(sectors[column].mean()) for column in METRIC_COLUMNS}


def top_articles(
    df: pd.DataFrame,
    sort_column: str,
    limit: int = 5,
    ascending: bool = False,
) -> pd.DataFrame:
    """返回指定指标下的重点新闻。"""
    if df.empty or sort_column not in df.columns:
        return df.head(0)
    return df.sort_values(sort_column, ascending=ascending).head(limit)
