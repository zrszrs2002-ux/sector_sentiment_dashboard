"""One-at-a-time sensitivity analysis for enhanced six-dimension weights.

Production execution is intentionally hard-wired to real_processed_articles.csv.
Persisted sentiment probabilities and formula components are reused, so this
module never runs FinBERT and never falls back to demo data.
"""

from __future__ import annotations

import json
from contextlib import redirect_stdout
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.errors import EmptyDataError, ParserError

from src.aggregation import attention_volume_by_sector, sector_metrics
from src.config import (
    ENHANCED_WEIGHTS,
    FORMULA_COMPONENT_COLUMNS,
    FORMULA_VERSION_ENHANCED,
    METRIC_COLUMNS,
    REAL_PROCESSED_ARTICLES_PATH,
    SECTORS,
    SENSITIVITY_ANALYSIS_PATH,
    SENSITIVITY_PERTURBATION_FACTORS,
    SENSITIVITY_TOP_K,
)
from src.data_loader import load_real_articles
from src.preprocessing import write_csv_atomic
from src.scoring import WeightGroup


SENSITIVITY_DATA_SOURCE = REAL_PROCESSED_ARTICLES_PATH.name
SENSITIVITY_RESULT_FIELDS = [
    "generated_at",
    "formula_version",
    "data_source",
    "target_dimension",
    "target_component",
    "perturbation_factor",
    "original_weight",
    "perturbed_weight",
    "normalized_dimension_weights",
    "day_count",
    "sector_day_count",
    "mean_daily_spearman",
    "mean_absolute_score_change",
    "mean_daily_top3_jaccard",
]
SENSITIVITY_NUMERIC_FIELDS = [
    "perturbation_factor",
    "original_weight",
    "perturbed_weight",
    "day_count",
    "sector_day_count",
    "mean_daily_spearman",
    "mean_absolute_score_change",
    "mean_daily_top3_jaccard",
]
SENSITIVITY_REQUIRED_ARTICLE_COLUMNS = {
    "article_id",
    "sector",
    "published_at",
    "p_positive",
    "p_neutral",
    "p_negative",
    "sentiment_score",
    "risk_intensity",
    "agg_weight",
    *FORMULA_COMPONENT_COLUMNS,
}


def perturb_dimension_weights(
    dimension: str,
    component: str,
    factor: float,
    base_weights: WeightGroup = ENHANCED_WEIGHTS,
) -> dict[str, dict[str, float]]:
    """Perturb one component and renormalize only its dimension."""
    if dimension not in base_weights:
        raise KeyError(f"Unknown sensitivity analysis dimension: {dimension}")
    if component not in base_weights[dimension]:
        raise KeyError(f"Component not found in {dimension}: {component}")
    numeric_factor = float(factor)
    if not np.isfinite(numeric_factor) or numeric_factor < 0:
        raise ValueError("The perturbation factor must be a finite, non-negative number.")

    adjusted = {
        name: {key: float(value) for key, value in components.items()}
        for name, components in base_weights.items()
    }
    if numeric_factor == 1.0:
        return adjusted

    target = adjusted[dimension]
    target[component] *= numeric_factor
    total = float(sum(target.values()))
    if total <= 0:
        raise ValueError(f"The weight sum for {dimension} after perturbation must be greater than 0.")
    adjusted[dimension] = {
        name: float(value / total)
        for name, value in target.items()
    }
    return adjusted


def _prepare_articles(articles: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(SENSITIVITY_REQUIRED_ARTICLE_COLUMNS.difference(articles.columns))
    if missing:
        raise ValueError(f"Real news is missing sensitivity analysis fields: {missing}")

    prepared = articles.copy()
    prepared["published_at"] = pd.to_datetime(
        prepared["published_at"], utc=True, errors="coerce"
    )
    prepared = prepared.dropna(subset=["published_at"])
    prepared["sector"] = prepared["sector"].fillna("").astype(str)
    prepared = prepared[prepared["sector"].isin(SECTORS)].copy()
    if prepared.empty:
        raise ValueError("No target sector records in real news are usable for sensitivity analysis.")

    numeric_columns = [
        "p_positive",
        "p_neutral",
        "p_negative",
        "sentiment_score",
        "risk_intensity",
        "agg_weight",
        *FORMULA_COMPONENT_COLUMNS,
    ]
    for column in numeric_columns:
        prepared[column] = pd.to_numeric(
            prepared[column], errors="coerce"
        ).fillna(0.0)
    prepared["_analysis_date"] = prepared["published_at"].dt.strftime("%Y-%m-%d")
    return prepared.sort_values(
        ["_analysis_date", "published_at", "article_id"],
        kind="stable",
    ).reset_index(drop=True)


def recompute_sector_day_scores(
    articles: pd.DataFrame,
    weights: WeightGroup = ENHANCED_WEIGHTS,
) -> pd.DataFrame:
    """Replay every UTC publication day through the official sector aggregator."""
    prepared = _prepare_articles(articles)
    history_rows: list[dict[str, object]] = []
    score_frames: list[pd.DataFrame] = []

    for analysis_date, group in prepared.groupby("_analysis_date", sort=True):
        day_articles = group.drop(columns="_analysis_date").copy()
        day_articles["collected_at"] = day_articles["published_at"].max()
        history = pd.DataFrame(history_rows)
        with redirect_stdout(StringIO()):
            day_scores = sector_metrics(
                day_articles,
                weights=weights,
                data_source=None,
                attention_history=history,
            )
        day_scores.insert(0, "analysis_date", analysis_date)
        score_frames.append(
            day_scores[["analysis_date", "sector", *METRIC_COLUMNS]].copy()
        )

        attention_volume = attention_volume_by_sector(day_articles)
        article_counts = day_scores.set_index("sector")["article_count"]
        history_rows.extend(
            {
                "snapshot_date": analysis_date,
                "sector": sector,
                "article_count": int(article_counts.get(sector, 0)),
                "attention_volume": float(attention_volume.get(sector, 0.0)),
            }
            for sector in SECTORS
        )

    return pd.concat(score_frames, ignore_index=True).sort_values(
        ["analysis_date", "sector"],
        kind="stable",
    ).reset_index(drop=True)


def _daily_spearman(default_values: pd.Series, perturbed_values: pd.Series) -> float:
    default_ranks = default_values.rank(method="average", ascending=False)
    perturbed_ranks = perturbed_values.rank(method="average", ascending=False)
    if np.allclose(default_ranks, perturbed_ranks, rtol=0.0, atol=1e-12):
        return 1.0
    if (
        default_ranks.nunique(dropna=True) < 2
        or perturbed_ranks.nunique(dropna=True) < 2
    ):
        return 0.0
    correlation = default_ranks.corr(perturbed_ranks)
    return 0.0 if pd.isna(correlation) else float(correlation)


def _top_sector_set(frame: pd.DataFrame, metric: str, top_k: int) -> set[str]:
    ordered = frame.assign(
        _metric_value=pd.to_numeric(frame[metric], errors="coerce").fillna(0.0)
    ).sort_values(
        ["_metric_value", "sector"],
        ascending=[False, True],
        kind="stable",
    )
    return set(ordered.head(min(top_k, len(ordered)))["sector"].astype(str))


def stability_metrics(
    default_scores: pd.DataFrame,
    perturbed_scores: pd.DataFrame,
    dimension: str,
    top_k: int = SENSITIVITY_TOP_K,
) -> dict[str, float | int]:
    """Compare one perturbed dimension against enhanced defaults."""
    keys = ["analysis_date", "sector"]
    merged = default_scores[keys + [dimension]].merge(
        perturbed_scores[keys + [dimension]],
        on=keys,
        how="inner",
        suffixes=("_default", "_perturbed"),
        validate="one_to_one",
    )
    if merged.empty:
        raise ValueError("No sector-day records could be aligned between the default and perturbed results.")

    daily_spearman: list[float] = []
    daily_jaccard: list[float] = []
    for _, day in merged.groupby("analysis_date", sort=True):
        default_values = day[f"{dimension}_default"]
        perturbed_values = day[f"{dimension}_perturbed"]
        daily_spearman.append(_daily_spearman(default_values, perturbed_values))

        default_frame = day[["sector", f"{dimension}_default"]].rename(
            columns={f"{dimension}_default": dimension}
        )
        perturbed_frame = day[["sector", f"{dimension}_perturbed"]].rename(
            columns={f"{dimension}_perturbed": dimension}
        )
        default_top = _top_sector_set(default_frame, dimension, top_k)
        perturbed_top = _top_sector_set(perturbed_frame, dimension, top_k)
        union = default_top | perturbed_top
        daily_jaccard.append(
            1.0 if not union else len(default_top & perturbed_top) / len(union)
        )

    absolute_change = (
        merged[f"{dimension}_default"] - merged[f"{dimension}_perturbed"]
    ).abs()
    return {
        "day_count": int(merged["analysis_date"].nunique()),
        "sector_day_count": int(len(merged)),
        "mean_daily_spearman": float(np.mean(daily_spearman)),
        "mean_absolute_score_change": float(absolute_change.mean()),
        "mean_daily_top3_jaccard": float(np.mean(daily_jaccard)),
    }


def compute_sensitivity_analysis(
    articles: pd.DataFrame,
    *,
    data_source: str = SENSITIVITY_DATA_SOURCE,
    factors: tuple[float, ...] = SENSITIVITY_PERTURBATION_FACTORS,
    generated_at: str | None = None,
) -> pd.DataFrame:
    """Compute all OAT perturbations for the real-news enhanced formula."""
    if data_source != SENSITIVITY_DATA_SOURCE:
        raise ValueError(
            "Weight sensitivity analysis only allows real_processed_articles.csv; Demo data is strictly forbidden."
        )
    timestamp = generated_at or datetime.now(UTC).isoformat(timespec="seconds")
    default_scores = recompute_sector_day_scores(articles, ENHANCED_WEIGHTS)
    rows: list[dict[str, object]] = []

    for dimension, components in ENHANCED_WEIGHTS.items():
        for component, original_weight in components.items():
            for factor in factors:
                perturbed_weights = perturb_dimension_weights(
                    dimension,
                    component,
                    factor,
                    ENHANCED_WEIGHTS,
                )
                perturbed_scores = recompute_sector_day_scores(
                    articles,
                    perturbed_weights,
                )
                metrics = stability_metrics(
                    default_scores,
                    perturbed_scores,
                    dimension,
                )
                rows.append(
                    {
                        "generated_at": timestamp,
                        "formula_version": FORMULA_VERSION_ENHANCED,
                        "data_source": data_source,
                        "target_dimension": dimension,
                        "target_component": component,
                        "perturbation_factor": float(factor),
                        "original_weight": float(original_weight),
                        "perturbed_weight": float(
                            perturbed_weights[dimension][component]
                        ),
                        "normalized_dimension_weights": json.dumps(
                            perturbed_weights[dimension],
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        **metrics,
                    }
                )
    return pd.DataFrame(rows, columns=SENSITIVITY_RESULT_FIELDS)


def persist_sensitivity_results(
    results: pd.DataFrame,
    output_path: Path = SENSITIVITY_ANALYSIS_PATH,
) -> None:
    missing = [
        field for field in SENSITIVITY_RESULT_FIELDS
        if field not in results.columns
    ]
    if missing:
        raise ValueError(f"Sensitivity analysis results are missing fields: {missing}")
    write_csv_atomic(
        output_path,
        SENSITIVITY_RESULT_FIELDS,
        results[SENSITIVITY_RESULT_FIELDS].to_dict("records"),
    )


def load_sensitivity_results(
    path: Path = SENSITIVITY_ANALYSIS_PATH,
) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=SENSITIVITY_RESULT_FIELDS)
    try:
        results = pd.read_csv(path, encoding="utf-8-sig")
    except (OSError, EmptyDataError, ParserError, UnicodeDecodeError) as exc:
        raise ValueError(f"Failed to read sensitivity analysis results: {exc}") from exc
    missing = [
        field for field in SENSITIVITY_RESULT_FIELDS
        if field not in results.columns
    ]
    if missing:
        raise ValueError(f"Sensitivity analysis results are missing fields: {missing}")
    if not results["data_source"].astype(str).eq(SENSITIVITY_DATA_SOURCE).all():
        raise ValueError("Sensitivity analysis results contain a non-real-news data source; loading was refused.")
    for field in SENSITIVITY_NUMERIC_FIELDS:
        results[field] = pd.to_numeric(results[field], errors="coerce")
    return results[SENSITIVITY_RESULT_FIELDS].copy()


def most_sensitive_components(results: pd.DataFrame) -> pd.DataFrame:
    """Select one component per dimension by its maximum score change."""
    if results.empty:
        return pd.DataFrame(
            columns=[
                "dimension",
                "most_sensitive_component",
                "worst_factor",
                "minimum_daily_spearman",
                "maximum_score_change",
                "minimum_top3_jaccard",
            ]
        )

    component_rows: list[dict[str, object]] = []
    for (dimension, component), group in results.groupby(
        ["target_dimension", "target_component"],
        sort=False,
    ):
        ordered = group.sort_values(
            [
                "mean_absolute_score_change",
                "mean_daily_spearman",
                "mean_daily_top3_jaccard",
                "perturbation_factor",
            ],
            ascending=[False, True, True, True],
            kind="stable",
        )
        worst = ordered.iloc[0]
        component_rows.append(
            {
                "dimension": dimension,
                "most_sensitive_component": component,
                "worst_factor": float(worst["perturbation_factor"]),
                "minimum_daily_spearman": float(
                    group["mean_daily_spearman"].min()
                ),
                "maximum_score_change": float(
                    group["mean_absolute_score_change"].max()
                ),
                "minimum_top3_jaccard": float(
                    group["mean_daily_top3_jaccard"].min()
                ),
            }
        )

    summary = pd.DataFrame(component_rows)
    summary["_dimension_order"] = summary["dimension"].map(
        {dimension: index for index, dimension in enumerate(METRIC_COLUMNS)}
    )
    return summary.sort_values(
        [
            "_dimension_order",
            "maximum_score_change",
            "minimum_daily_spearman",
            "minimum_top3_jaccard",
            "most_sensitive_component",
        ],
        ascending=[True, False, True, True, True],
        kind="stable",
    ).drop_duplicates("dimension", keep="first").drop(
        columns="_dimension_order"
    ).reset_index(drop=True)


def run_sensitivity_analysis(
    output_path: Path = SENSITIVITY_ANALYSIS_PATH,
) -> pd.DataFrame:
    """Run and persist the production analysis from real news only."""
    articles = load_real_articles(load_all_history=True)
    if articles.empty:
        raise ValueError(
            "real_processed_articles.csv is empty or unreadable; sensitivity analysis will not fall back to Demo data."
        )
    results = compute_sensitivity_analysis(
        articles,
        data_source=SENSITIVITY_DATA_SOURCE,
    )
    persist_sensitivity_results(results, output_path)
    return results
