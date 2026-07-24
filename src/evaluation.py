from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.aggregation import (
    attention_history_day_counts,
    safe_weights,
    sector_metrics,
    weighted_mean,
)
from src.config import (
    ATTENTION_MIN_HISTORY_DAYS,
    ANNOTATION_ERRORS_PATH,
    ANNOTATION_SAMPLE_SIZE,
    BASELINE_WEIGHTS,
    CALIBRATION_BIN_COUNT,
    ENHANCED_WEIGHTS,
    FORMULA_COMPONENT_COLUMNS,
    METRIC_COLUMNS,
    METRIC_LABELS,
    RISK_SEVERITY_WEIGHTS,
)
from src.keyword_signals import matched_signal_terms
from src.preprocessing import write_csv_atomic
from src.rss_sources import distinct_value_count
from src.scoring import formula_values_from_record
from src.sentiment_model import analyze_articles_sentiment_lexicon


SENTIMENT_LABELS = ["negative", "neutral", "positive"]
SENTIMENT_ERROR_FIELDS = [
    "article_id",
    "title",
    "true_sentiment",
    "predicted_sentiment",
    "confidence",
]


def coverage_summary(df: pd.DataFrame) -> dict[str, int]:
    """Minimal coverage statistics; later phases extend the formal evaluation interface."""
    if df.empty:
        return {
            "article_count": 0,
            "source_count": 0,
            "sector_coverage_count": 0,
            "unmapped_article_count": 0,
            "duplicate_article_count": 0,
            "time_parse_error_count": 0,
            "processing_error_count": 0,
        }

    return {
        "article_count": int(len(df)),
        "source_count": distinct_value_count(
            df["publisher"] if "publisher" in df else df.get("source", []),
            df.get("source", []),
        ),
        "sector_coverage_count": int(df["sector"].nunique()) if "sector" in df else 0,
        "unmapped_article_count": int((df["sector"].astype(str) == "Unmapped").sum()) if "sector" in df else 0,
        "duplicate_article_count": int(df["is_duplicate"].sum()) if "is_duplicate" in df else 0,
        "time_parse_error_count": int(df["time_parse_error"].fillna("").astype(str).str.len().gt(0).sum()) if "time_parse_error" in df else 0,
        "processing_error_count": int(df["processing_error"].fillna("").astype(str).str.len().gt(0).sum()) if "processing_error" in df else 0,
    }


def coverage_summary_table(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [{"Metric": key, "Value": value} for key, value in coverage_summary(df).items()]
    )


def output_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Return distribution summaries for core numeric fields."""
    numeric_columns = [
        "sentiment_score",
        "p_positive",
        "p_neutral",
        "p_negative",
        *FORMULA_COMPONENT_COLUMNS,
        "optimism",
        "fear",
        "uncertainty",
        "risk_intensity",
        "model_confidence",
        "agg_weight",
    ]
    rows: list[dict[str, float | str | int]] = []
    for column in numeric_columns:
        if column not in df:
            continue
        values = pd.to_numeric(df[column], errors="coerce").dropna()
        if values.empty:
            rows.append({"field": column, "count": 0})
            continue
        rows.append(
            {
                "field": column,
                "count": int(values.count()),
                "min": float(values.min()),
                "P10": float(values.quantile(0.1)),
                "median": float(values.median()),
                "mean": float(values.mean()),
                "P90": float(values.quantile(0.9)),
                "max": float(values.max()),
            }
        )
    return pd.DataFrame(rows)


def sentiment_label_from_score(score: float, threshold: float = 0.05) -> str:
    if score > threshold:
        return "positive"
    if score < -threshold:
        return "negative"
    return "neutral"


def annotation_template(
    df: pd.DataFrame,
    limit: int = ANNOTATION_SAMPLE_SIZE,
) -> pd.DataFrame:
    """Compatibility helper that never exposes model outputs; use the sampler for stratification."""
    columns = ["article_id", "title", "summary", "content", "url", "published_at"]
    template = df.reindex(columns=columns).head(limit).copy()
    template["label_sentiment"] = ""
    template["label_sector_ok"] = ""
    template["label_risk_categories"] = ""
    template["label_evidence_ok"] = ""
    template["notes"] = ""
    return template


def first_existing_column(df: pd.DataFrame, candidates: list[str]) -> str:
    for column in candidates:
        if column in df.columns:
            return column
    return ""


def accuracy_row(
    merged: pd.DataFrame,
    task_name: str,
    prediction_column: str,
    label_column: str,
) -> dict[str, float | str | int]:
    if not label_column or prediction_column not in merged:
        return {"task": task_name, "labelled_count": 0, "correct_count": 0, "accuracy": 0.0}

    labels = merged[label_column].fillna("").astype(str).str.strip().str.lower()
    predictions = merged[prediction_column].fillna("").astype(str).str.strip().str.lower()
    valid_mask = labels.ne("")
    total = int(valid_mask.sum())
    if total == 0:
        return {"task": task_name, "labelled_count": 0, "correct_count": 0, "accuracy": 0.0}

    correct = int((labels[valid_mask] == predictions[valid_mask]).sum())
    return {
        "task": task_name,
        "labelled_count": total,
        "correct_count": correct,
        "accuracy": round(correct / total, 4),
    }


def evaluate_annotations(predictions: pd.DataFrame, annotations: pd.DataFrame) -> pd.DataFrame:
    """Calculate minimal accuracy metrics from human-annotation CSV files."""
    if predictions.empty or annotations.empty or "article_id" not in annotations.columns:
        return pd.DataFrame(columns=["task", "labelled_count", "correct_count", "accuracy"])

    prepared_predictions = predictions.copy()
    sentiment_scores = pd.to_numeric(prepared_predictions["sentiment_score"], errors="coerce").fillna(0)
    prepared_predictions["predicted_sentiment"] = sentiment_scores.apply(sentiment_label_from_score)
    prepared_predictions = prepared_predictions.rename(
        columns={
            "sector": "predicted_sector",
            "risk_category": "predicted_risk_category",
        }
    )
    merged = annotations.merge(
        prepared_predictions[["article_id", "predicted_sentiment", "predicted_sector", "predicted_risk_category"]],
        on="article_id",
        how="inner",
    )

    sentiment_label = first_existing_column(merged, ["label_sentiment", "sentiment_label"])
    sector_label = first_existing_column(merged, ["label_sector", "sector_label"])
    risk_label = first_existing_column(merged, ["label_risk_category", "risk_category_label"])
    return pd.DataFrame(
        [
            accuracy_row(merged, "sentiment", "predicted_sentiment", sentiment_label),
            accuracy_row(merged, "sector", "predicted_sector", sector_label),
            accuracy_row(merged, "risk_category", "predicted_risk_category", risk_label),
        ]
    )


def formula_sector_outputs(
    df: pd.DataFrame,
    data_source: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the shared formula implementation with baseline and enhanced weights."""
    baseline = sector_metrics(df, weights=BASELINE_WEIGHTS, data_source=data_source)
    enhanced = sector_metrics(df, weights=ENHANCED_WEIGHTS, data_source=data_source)
    return baseline, enhanced


def formula_metric_comparison(
    baseline: pd.DataFrame,
    enhanced: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    for metric in METRIC_COLUMNS:
        for version, frame in [("Baseline", baseline), ("Enhanced", enhanced)]:
            values = pd.to_numeric(frame.get(metric, pd.Series(dtype=float)), errors="coerce").dropna()
            if values.empty:
                continue
            rows.append(
                {
                    "metric": METRIC_LABELS[metric],
                    "formula_version": version,
                    "mean": float(values.mean()),
                    "std": float(values.std(ddof=0)),
                    "min": float(values.min()),
                    "max": float(values.max()),
                    "range": float(values.max() - values.min()),
                }
            )
    return pd.DataFrame(rows)


def _component_means(df: pd.DataFrame) -> dict[str, dict[str, float]]:
    components = ["b_bull", "b_bear", "g_growth", "s_shock", "k_unc"]
    result: dict[str, dict[str, float]] = {}
    if df.empty or "sector" not in df:
        return result
    for sector, group in df.groupby("sector"):
        weights = safe_weights(group)
        result[str(sector)] = {}
        for component in components:
            values = (
                group[component]
                if component in group
                else pd.Series(0.0, index=group.index)
            )
            result[str(sector)][component] = weighted_mean(values, weights)

    return result


def _rank_change_reason(
    metric: str,
    sector: str,
    components: dict[str, dict[str, float]],
    history_days: dict[str, int],
) -> str:
    values = components.get(sector, {})
    if metric == "optimism":
        bull = values.get("b_bull", 0.0)
        growth = values.get("g_growth", 0.0)
        if bull == 0 and growth == 0:
            return "No growth or bullish-stance terms matched; the change comes from the FinBERT probability weight moving from 1.0 to 0.7"
        leading = "bullish stance" if 0.2 * bull >= 0.1 * growth else "growth theme"
        return f"Main driver: {leading} (B_bull={bull:.2f}, G_growth={growth:.2f})"
    if metric == "fear":
        bear = values.get("b_bear", 0.0)
        shock = values.get("s_shock", 0.0)
        if bear == 0 and shock == 0:
            return "No shock or bearish-stance terms matched; the change comes from the FinBERT probability weight moving from 1.0 to 0.7"
        leading = "bearish stance" if 0.2 * bear >= 0.1 * shock else "panic shock"
        return f"Main driver: {leading} (B_bear={bear:.2f}, S_shock={shock:.2f})"
    if metric == "uncertainty":
        uncertainty = values.get("k_unc", 0.0)
        return (
            f"LM uncertainty-term component K_unc={uncertainty:.2f}, plus reweighted neutral/entropy"
            if uncertainty
            else "No LM uncertainty terms matched; the change comes from the neutral/entropy reweighting"
        )
    if metric == "attention":
        days = history_days.get(sector, 0)
        if days < ATTENTION_MIN_HISTORY_DAYS:
            return f"{days} days of history, short of {ATTENTION_MIN_HISTORY_DAYS}; both versions use cold-start ranking"
        return f"{days} days of history; Enhanced adds a 30% article-volume growth rate within its own historical ECDF"
    if metric == "disagreement":
        return "Uses threshold-free weighted pairwise sentiment distance by default; the legacy PolarityMix is kept only as an ablation switch"
    return "Risk Intensity uses identical weights in both versions for this batch, so the formula and ranking are unchanged"


def formula_rank_changes(
    df: pd.DataFrame,
    baseline: pd.DataFrame,
    enhanced: pd.DataFrame,
    data_source: str,
    top_n: int = 3,
) -> pd.DataFrame:
    if baseline.empty or enhanced.empty:
        return pd.DataFrame()
    merged = baseline[["sector", *METRIC_COLUMNS]].merge(
        enhanced[["sector", *METRIC_COLUMNS]],
        on="sector",
        suffixes=("_baseline", "_enhanced"),
    )
    component_means = _component_means(df)
    history_days = attention_history_day_counts(data_source=data_source)
    rows: list[dict[str, float | str]] = []
    for metric in METRIC_COLUMNS:
        metric_rows = merged[["sector", f"{metric}_baseline", f"{metric}_enhanced"]].copy()
        metric_rows["baseline_rank"] = metric_rows[f"{metric}_baseline"].rank(
            method="average", ascending=False
        )
        metric_rows["enhanced_rank"] = metric_rows[f"{metric}_enhanced"].rank(
            method="average", ascending=False
        )
        metric_rows["rank_change"] = metric_rows["baseline_rank"] - metric_rows["enhanced_rank"]
        metric_rows["abs_rank_change"] = metric_rows["rank_change"].abs()
        metric_rows = metric_rows.sort_values(
            ["abs_rank_change", f"{metric}_enhanced"], ascending=[False, False]
        ).head(top_n)
        for row in metric_rows.to_dict("records"):
            sector = str(row["sector"])
            rows.append(
                {
                    "metric": METRIC_LABELS[metric],
                    "sector": sector,
                    "baseline_rank": float(row["baseline_rank"]),
                    "enhanced_rank": float(row["enhanced_rank"]),
                    "rank_change (positive = moved up)": float(row["rank_change"]),
                    "baseline_score": float(row[f"{metric}_baseline"]),
                    "enhanced_score": float(row[f"{metric}_enhanced"]),
                    "main_reason": _rank_change_reason(
                        metric, sector, component_means, history_days
                    ),
                }
            )
    return pd.DataFrame(rows)


def _article_text(row: dict[str, object]) -> str:
    seen: set[str] = set()
    parts: list[str] = []
    for column in ["title", "summary", "content"]:
        value = str(row.get(column, "") or "").strip()
        normalized = " ".join(value.lower().split())
        if value and normalized not in seen:
            seen.add(normalized)
            parts.append(value)
    return ". ".join(parts)


def formula_article_examples(df: pd.DataFrame, limit: int = 3) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    working = df.copy()
    signal_columns = ["b_bull", "b_bear", "g_growth", "s_shock", "k_unc"]
    for column in signal_columns:
        values = working[column] if column in working else pd.Series(0.0, index=working.index)
        working[column] = pd.to_numeric(values, errors="coerce").fillna(0)
    working["_signal_strength"] = working[signal_columns].max(axis=1)
    impacts: list[float] = []
    for record in working.to_dict("records"):
        baseline_values = formula_values_from_record(record, BASELINE_WEIGHTS)
        enhanced_values = formula_values_from_record(record, ENHANCED_WEIGHTS)
        impacts.append(
            max(
                abs(enhanced_values[metric] - baseline_values[metric])
                for metric in ["optimism", "fear", "uncertainty"]
            )
        )
    working["_formula_impact"] = impacts
    candidates = working.sort_values(
        ["_signal_strength", "_formula_impact"], ascending=False
    )
    signalled = candidates[candidates["_signal_strength"] > 0]
    if not signalled.empty:
        candidates = signalled
    candidates = candidates.drop_duplicates("title")
    selected_indexes: list[int] = []
    seen_sectors: set[str] = set()
    for index, row in candidates.iterrows():
        sector = str(row.get("sector", ""))
        if sector in seen_sectors:
            continue
        selected_indexes.append(index)
        seen_sectors.add(sector)
        if len(selected_indexes) == limit:
            break
    if len(selected_indexes) < limit:
        selected_indexes.extend(
            index
            for index in candidates.index
            if index not in selected_indexes
        )
    candidates = candidates.loc[selected_indexes[:limit]]

    labels = {
        "b_bull": "bullish stance",
        "b_bear": "bearish stance",
        "g_growth": "growth",
        "s_shock": "shock",
        "k_unc": "uncertainty",
    }
    rows: list[dict[str, float | str]] = []
    for record in candidates.to_dict("records"):
        baseline_values = formula_values_from_record(record, BASELINE_WEIGHTS)
        enhanced_values = formula_values_from_record(record, ENHANCED_WEIGHTS)
        matched = matched_signal_terms(_article_text(record))
        term_parts = [
            f"{labels[key]}: {', '.join(terms)}"
            for key, terms in matched.items()
            if terms
        ]
        rows.append(
            {
                "article": str(record.get("title", "")),
                "sector": str(record.get("sector", "")),
                "matched_enhanced_terms": "; ".join(term_parts) or "none",
                "baseline_optimism": baseline_values["optimism"],
                "enhanced_optimism": enhanced_values["optimism"],
                "optimism_change": enhanced_values["optimism"] - baseline_values["optimism"],
                "baseline_fear": baseline_values["fear"],
                "enhanced_fear": enhanced_values["fear"],
                "fear_change": enhanced_values["fear"] - baseline_values["fear"],
                "baseline_uncertainty": baseline_values["uncertainty"],
                "enhanced_uncertainty": enhanced_values["uncertainty"],
                "uncertainty_change": enhanced_values["uncertainty"] - baseline_values["uncertainty"],
            }
        )
    return pd.DataFrame(rows)


def normalize_sentiment_label(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    normalized = str(value).strip().lower()
    aliases = {
        "positive": "positive",
        "pos": "positive",
        "\u6b63\u9762": "positive",
        "neutral": "neutral",
        "neu": "neutral",
        "\u4e2d\u6027": "neutral",
        "negative": "negative",
        "neg": "negative",
        "\u8d1f\u9762": "negative",
    }
    return aliases.get(normalized, "")


def normalize_binary_label(value: object) -> bool | None:
    if value is None or pd.isna(value):
        return None
    normalized = str(value).strip().lower()
    if normalized in {
        "1",
        "1.0",
        "true",
        "yes",
        "y",
        "\u662f",
        "\u6b63\u786e",
        "\u5408\u683c",
    }:
        return True
    if normalized in {
        "0",
        "0.0",
        "false",
        "no",
        "n",
        "\u5426",
        "\u9519\u8bef",
        "\u4e0d\u5408\u683c",
    }:
        return False
    return None


def parse_risk_labels(value: object) -> set[str]:
    if value is None or pd.isna(value):
        return set()
    normalized = str(value).strip().lower()
    if not normalized:
        return set()
    parts = {
        part.strip()
        for part in re.split(r"[;,|，、]+", normalized)
        if part.strip()
    }
    legacy_none_labels = {"\u65e0", "\u65e0\u98ce\u9669"}
    return set() if parts <= {"none", *legacy_none_labels} else parts - {"none", *legacy_none_labels}


def safe_ratio(numerator: int | float, denominator: int | float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def classification_report(
    y_true: list[str],
    y_pred: list[str],
    labels: list[str] | None = None,
) -> dict[str, Any]:
    labels = labels or SENTIMENT_LABELS
    matrix = pd.DataFrame(0, index=labels, columns=labels, dtype=int)
    for true_label, predicted_label in zip(y_true, y_pred, strict=True):
        if true_label in labels and predicted_label in labels:
            matrix.loc[true_label, predicted_label] += 1

    rows: list[dict[str, float | int | str]] = []
    for label in labels:
        true_positive = int(matrix.loc[label, label])
        false_positive = int(matrix[label].sum() - true_positive)
        false_negative = int(matrix.loc[label].sum() - true_positive)
        precision = safe_ratio(true_positive, true_positive + false_positive)
        recall = safe_ratio(true_positive, true_positive + false_negative)
        f1 = safe_ratio(2 * precision * recall, precision + recall)
        rows.append(
            {
                "label": label,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "support": int(matrix.loc[label].sum()),
                "predicted_count": int(matrix[label].sum()),
            }
        )

    per_class = pd.DataFrame(rows)
    sample_count = int(matrix.to_numpy().sum())
    return {
        "sample_count": sample_count,
        "accuracy": safe_ratio(int(np.trace(matrix.to_numpy())), sample_count),
        "macro_f1": float(per_class["f1"].mean()) if not per_class.empty else 0.0,
        "per_class": per_class,
        "confusion_matrix": matrix,
    }


def report_comparison_row(model_name: str, report: dict[str, Any]) -> dict[str, object]:
    row: dict[str, object] = {
        "model": model_name,
        "sample_count": int(report["sample_count"]),
        "accuracy": float(report["accuracy"]),
        "macro_f1": float(report["macro_f1"]),
    }
    per_class = report["per_class"].set_index("label")
    for label in SENTIMENT_LABELS:
        row[f"{label}_precision"] = float(per_class.loc[label, "precision"])
        row[f"{label}_recall"] = float(per_class.loc[label, "recall"])
        row[f"{label}_f1"] = float(per_class.loc[label, "f1"])
    return row


def lexicon_sentiment_predictions(frame: pd.DataFrame) -> list[str]:
    articles = [
        (
            str(row.get("title", "") or ""),
            str(row.get("summary", "") or ""),
            str(row.get("content", "") or ""),
        )
        for row in frame.fillna("").to_dict("records")
    ]
    results = analyze_articles_sentiment_lexicon(articles)
    return [
        max(
            {
                "positive": result.p_positive,
                "neutral": result.p_neutral,
                "negative": result.p_negative,
            },
            key={
                "positive": result.p_positive,
                "neutral": result.p_neutral,
                "negative": result.p_negative,
            }.get,
        )
        for result in results
    ]


def align_annotation_key(
    annotations: pd.DataFrame,
    annotation_key: pd.DataFrame,
) -> pd.DataFrame:
    required_annotation = {
        "article_id",
        "title",
        "summary",
        "content",
        "label_sentiment",
        "label_sector_ok",
        "label_risk_categories",
        "label_evidence_ok",
    }
    required_key = {
        "article_id",
        "predicted_sentiment_finbert",
        "predicted_sector",
        "predicted_risk_categories",
        "predicted_evidence_sentence",
        "finbert_confidence",
        "p_positive",
        "p_neutral",
        "p_negative",
    }
    missing_annotation = sorted(required_annotation - set(annotations.columns))
    missing_key = sorted(required_key - set(annotation_key.columns))
    if missing_annotation:
        raise ValueError(f"Annotation CSV is missing fields: {missing_annotation}")
    if missing_key:
        raise ValueError(f"annotation_key is missing fields: {missing_key}")

    prepared_annotations = annotations.copy()
    prepared_key = annotation_key.copy()
    prepared_annotations["article_id"] = prepared_annotations["article_id"].fillna("").astype(str)
    prepared_key["article_id"] = prepared_key["article_id"].fillna("").astype(str)
    if prepared_annotations["article_id"].eq("").any():
        raise ValueError("Annotation CSV has a blank article_id.")
    if prepared_annotations["article_id"].duplicated().any():
        raise ValueError("Annotation CSV has a duplicate article_id.")
    if prepared_key["article_id"].duplicated().any():
        raise ValueError("annotation_key has a duplicate article_id.")
    unmatched = sorted(
        set(prepared_annotations["article_id"]) - set(prepared_key["article_id"])
    )
    if unmatched:
        raise ValueError(f"{len(unmatched)} article_id(s) could not be reconciled against annotation_key.")

    merged = prepared_annotations.merge(
        prepared_key,
        on="article_id",
        how="inner",
        validate="one_to_one",
    )
    if merged.empty:
        raise ValueError("No matching article_id between the annotation CSV and annotation_key.")
    return merged


def risk_multilabel_report(merged: pd.DataFrame) -> dict[str, Any]:
    canonical_labels = list(RISK_SEVERITY_WEIGHTS)
    labelled = merged[
        merged["label_risk_categories"].fillna("").astype(str).str.strip().ne("")
    ].copy()
    if labelled.empty:
        return {"sample_count": 0, "macro_f1": 0.0, "per_class": pd.DataFrame()}

    true_sets = labelled["label_risk_categories"].apply(parse_risk_labels)
    predicted_sets = labelled["predicted_risk_categories"].apply(parse_risk_labels)
    unknown = sorted(set().union(*true_sets.tolist()) - set(canonical_labels))
    if unknown:
        raise ValueError(f"label_risk_categories contains unknown categories: {unknown}")

    rows: list[dict[str, float | int | str]] = []
    for label in canonical_labels:
        true_positive = sum(label in truth and label in prediction for truth, prediction in zip(true_sets, predicted_sets, strict=True))
        false_positive = sum(label not in truth and label in prediction for truth, prediction in zip(true_sets, predicted_sets, strict=True))
        false_negative = sum(label in truth and label not in prediction for truth, prediction in zip(true_sets, predicted_sets, strict=True))
        precision = safe_ratio(true_positive, true_positive + false_positive)
        recall = safe_ratio(true_positive, true_positive + false_negative)
        f1 = safe_ratio(2 * precision * recall, precision + recall)
        rows.append(
            {
                "risk_category": label,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "support": sum(label in truth for truth in true_sets),
                "predicted_count": sum(label in prediction for prediction in predicted_sets),
            }
        )
    per_class = pd.DataFrame(rows)
    return {
        "sample_count": int(len(labelled)),
        "macro_f1": float(per_class["f1"].mean()),
        "per_class": per_class,
    }


def binary_quality_summary(merged: pd.DataFrame, column: str) -> dict[str, float | int]:
    labels = merged[column].apply(normalize_binary_label)
    nonempty = merged[column].fillna("").astype(str).str.strip().ne("")
    invalid = merged.loc[nonempty & labels.isna(), column].astype(str).unique().tolist()
    if invalid:
        raise ValueError(f"{column} contains invalid values: {sorted(invalid)}")
    valid = labels.notna()
    values = labels[valid].astype(bool)
    return {
        "sample_count": int(valid.sum()),
        "positive_count": int(values.sum()),
        "score": float(values.mean()) if not values.empty else 0.0,
    }


def calibration_report(
    sentiment_frame: pd.DataFrame,
    bin_count: int = CALIBRATION_BIN_COUNT,
) -> dict[str, Any]:
    probability_columns = ["p_negative", "p_neutral", "p_positive"]
    probabilities = sentiment_frame[probability_columns].apply(
        pd.to_numeric, errors="coerce"
    ).fillna(0.0).clip(0.0, 1.0)
    row_sums = probabilities.sum(axis=1)
    valid = row_sums.gt(0)
    probabilities = probabilities[valid].div(row_sums[valid], axis=0)
    evaluated = sentiment_frame.loc[valid].copy()
    if evaluated.empty:
        return {"sample_count": 0, "brier_score": 0.0, "reliability": pd.DataFrame()}

    true_labels = evaluated["normalized_true_sentiment"].tolist()
    predicted_labels = evaluated["normalized_finbert_prediction"].tolist()
    probability_confidence = probabilities.max(axis=1)
    confidences = pd.to_numeric(
        evaluated["finbert_confidence"], errors="coerce"
    ).fillna(probability_confidence).clip(0.0, 1.0)
    correctness = pd.Series(
        [true == predicted for true, predicted in zip(true_labels, predicted_labels, strict=True)],
        index=evaluated.index,
        dtype=float,
    )

    targets = np.zeros((len(evaluated), len(SENTIMENT_LABELS)), dtype=float)
    label_to_index = {label: index for index, label in enumerate(SENTIMENT_LABELS)}
    for row_index, label in enumerate(true_labels):
        targets[row_index, label_to_index[label]] = 1.0
    ordered_probabilities = probabilities[[f"p_{label}" for label in SENTIMENT_LABELS]].to_numpy()
    brier_score = float(np.mean(np.sum((ordered_probabilities - targets) ** 2, axis=1)))

    bin_indexes = np.minimum((confidences * bin_count).astype(int), bin_count - 1)
    reliability_rows: list[dict[str, float | int | str]] = []
    for bin_index in range(bin_count):
        mask = bin_indexes.eq(bin_index)
        if not mask.any():
            continue
        lower = bin_index / bin_count
        upper = (bin_index + 1) / bin_count
        reliability_rows.append(
            {
                "bin": f"[{lower:.1f}, {upper:.1f}{']' if bin_index == bin_count - 1 else ')'}",
                "bin_lower": lower,
                "bin_upper": upper,
                "count": int(mask.sum()),
                "mean_confidence": float(confidences[mask].mean()),
                "accuracy": float(correctness[mask].mean()),
            }
        )
    return {
        "sample_count": int(len(evaluated)),
        "brier_score": brier_score,
        "reliability": pd.DataFrame(reliability_rows),
    }


def build_sentiment_errors(sentiment_frame: pd.DataFrame) -> pd.DataFrame:
    errors = sentiment_frame[
        sentiment_frame["normalized_true_sentiment"].ne(
            sentiment_frame["normalized_finbert_prediction"]
        )
    ].copy()
    if errors.empty:
        return pd.DataFrame(columns=SENTIMENT_ERROR_FIELDS)
    probability_confidence = errors[["p_positive", "p_neutral", "p_negative"]].apply(
        pd.to_numeric, errors="coerce"
    ).fillna(0.0).max(axis=1)
    confidence = pd.to_numeric(
        errors["finbert_confidence"], errors="coerce"
    ).fillna(probability_confidence).clip(0.0, 1.0)
    return pd.DataFrame(
        {
            "article_id": errors["article_id"].astype(str),
            "title": errors["title"].fillna("").astype(str),
            "true_sentiment": errors["normalized_true_sentiment"],
            "predicted_sentiment": errors["normalized_finbert_prediction"],
            "confidence": confidence,
        }
    ).reset_index(drop=True)


def write_sentiment_errors(path: Path, errors: pd.DataFrame) -> None:
    prepared = errors.reindex(columns=SENTIMENT_ERROR_FIELDS).copy()
    if path.exists() and path.stat().st_size > 0:
        try:
            existing = pd.read_csv(path, encoding="utf-8-sig").reindex(
                columns=SENTIMENT_ERROR_FIELDS
            )
            if existing.fillna("").astype(str).equals(
                prepared.fillna("").astype(str)
            ):
                return
        except (OSError, UnicodeDecodeError, pd.errors.ParserError):
            pass
    write_csv_atomic(path, SENTIMENT_ERROR_FIELDS, prepared.to_dict("records"))


def evaluate_model_annotations(
    annotations: pd.DataFrame,
    annotation_key: pd.DataFrame,
    error_output_path: Path | None = ANNOTATION_ERRORS_PATH,
) -> dict[str, Any]:
    """Evaluate classification outputs against a completed blind annotation file."""
    merged = align_annotation_key(annotations, annotation_key)
    merged["normalized_true_sentiment"] = merged["label_sentiment"].apply(
        normalize_sentiment_label
    )
    merged["normalized_finbert_prediction"] = merged[
        "predicted_sentiment_finbert"
    ].apply(normalize_sentiment_label)
    raw_sentiment = merged["label_sentiment"].fillna("").astype(str).str.strip()
    invalid_sentiment = merged.loc[
        raw_sentiment.ne("") & merged["normalized_true_sentiment"].eq(""),
        "label_sentiment",
    ].astype(str).unique().tolist()
    if invalid_sentiment:
        raise ValueError(f"label_sentiment contains invalid values: {sorted(invalid_sentiment)}")
    if merged["normalized_finbert_prediction"].eq("").any():
        raise ValueError("annotation_key contains an invalid FinBERT sentiment prediction.")
    sentiment_frame = merged[
        merged["normalized_true_sentiment"].isin(SENTIMENT_LABELS)
        & merged["normalized_finbert_prediction"].isin(SENTIMENT_LABELS)
    ].copy()

    reports: dict[str, dict[str, Any]] = {}
    comparison = pd.DataFrame()
    errors = pd.DataFrame(columns=SENTIMENT_ERROR_FIELDS)
    calibration = {"sample_count": 0, "brier_score": 0.0, "reliability": pd.DataFrame()}
    if not sentiment_frame.empty:
        true_labels = sentiment_frame["normalized_true_sentiment"].tolist()
        predictions = {
            "All-neutral baseline": ["neutral"] * len(sentiment_frame),
            "Lexicon engine": lexicon_sentiment_predictions(sentiment_frame),
            "FinBERT": sentiment_frame["normalized_finbert_prediction"].tolist(),
        }
        reports = {
            model: classification_report(true_labels, predicted)
            for model, predicted in predictions.items()
        }
        comparison = pd.DataFrame(
            [report_comparison_row(model, report) for model, report in reports.items()]
        )
        calibration = calibration_report(sentiment_frame)
        errors = build_sentiment_errors(sentiment_frame)
        if error_output_path is not None:
            write_sentiment_errors(error_output_path, errors)

    sector = binary_quality_summary(merged, "label_sector_ok")
    evidence = binary_quality_summary(merged, "label_evidence_ok")
    risk = risk_multilabel_report(merged)
    return {
        "aligned_count": int(len(merged)),
        "sentiment_labelled_count": int(len(sentiment_frame)),
        "sentiment_reports": reports,
        "sentiment_comparison": comparison,
        "sector_mapping": {
            "sample_count": sector["sample_count"],
            "correct_count": sector["positive_count"],
            "accuracy": sector["score"],
        },
        "risk": risk,
        "evidence": {
            "sample_count": evidence["sample_count"],
            "accepted_count": evidence["positive_count"],
            "precision": evidence["score"],
        },
        "calibration": calibration,
        "sentiment_errors": errors,
    }


def evaluate_annotation_files(
    annotation_path: Path,
    key_path: Path,
    error_output_path: Path | None = ANNOTATION_ERRORS_PATH,
) -> dict[str, Any]:
    annotations = pd.read_csv(annotation_path, encoding="utf-8-sig", dtype=str)
    annotation_key = pd.read_csv(key_path, encoding="utf-8-sig")
    return evaluate_model_annotations(annotations, annotation_key, error_output_path)
