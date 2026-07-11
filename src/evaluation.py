import pandas as pd

from src.aggregation import (
    attention_history_day_counts,
    polarity_mix,
    safe_weights,
    sector_metrics,
    weighted_mean,
)
from src.config import (
    ATTENTION_MIN_HISTORY_DAYS,
    BASELINE_WEIGHTS,
    ENHANCED_WEIGHTS,
    FORMULA_COMPONENT_COLUMNS,
    METRIC_COLUMNS,
    METRIC_LABELS,
)
from src.keyword_signals import matched_signal_terms
from src.scoring import formula_values_from_record


def coverage_summary(df: pd.DataFrame) -> dict[str, int]:
    """最小覆盖统计；正式评估接口将在后续阶段扩展。"""
    if df.empty:
        return {
            "新闻数量": 0,
            "来源数量": 0,
            "板块覆盖数量": 0,
            "Unmapped 新闻数量": 0,
            "重复新闻数量": 0,
            "时间解析错误数量": 0,
            "处理错误数量": 0,
        }

    return {
        "新闻数量": int(len(df)),
        "来源数量": int(df["source"].nunique()) if "source" in df else 0,
        "板块覆盖数量": int(df["sector"].nunique()) if "sector" in df else 0,
        "Unmapped 新闻数量": int((df["sector"].astype(str) == "Unmapped").sum()) if "sector" in df else 0,
        "重复新闻数量": int(df["is_duplicate"].sum()) if "is_duplicate" in df else 0,
        "时间解析错误数量": int(df["time_parse_error"].fillna("").astype(str).str.len().gt(0).sum()) if "time_parse_error" in df else 0,
        "处理错误数量": int(df["processing_error"].fillna("").astype(str).str.len().gt(0).sum()) if "processing_error" in df else 0,
    }


def coverage_summary_table(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [{"指标": key, "值": value} for key, value in coverage_summary(df).items()]
    )


def output_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """输出核心数值字段的分布摘要。"""
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
            rows.append({"字段": column, "数量": 0})
            continue
        rows.append(
            {
                "字段": column,
                "数量": int(values.count()),
                "最小值": float(values.min()),
                "P10": float(values.quantile(0.1)),
                "中位数": float(values.median()),
                "均值": float(values.mean()),
                "P90": float(values.quantile(0.9)),
                "最大值": float(values.max()),
            }
        )
    return pd.DataFrame(rows)


def sentiment_label_from_score(score: float, threshold: float = 0.05) -> str:
    if score > threshold:
        return "positive"
    if score < -threshold:
        return "negative"
    return "neutral"


def annotation_template(df: pd.DataFrame, limit: int = 200) -> pd.DataFrame:
    """生成可下载的人工标注 CSV 模板。"""
    columns = ["article_id", "title", "url", "sector", "risk_category", "sentiment_score"]
    existing_columns = [column for column in columns if column in df.columns]
    template = df[existing_columns].head(limit).copy()
    template["label_sentiment"] = ""
    template["label_sector"] = ""
    template["label_risk_category"] = ""
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
        return {"任务": task_name, "标注数量": 0, "命中数量": 0, "准确率": 0.0}

    labels = merged[label_column].fillna("").astype(str).str.strip().str.lower()
    predictions = merged[prediction_column].fillna("").astype(str).str.strip().str.lower()
    valid_mask = labels.ne("")
    total = int(valid_mask.sum())
    if total == 0:
        return {"任务": task_name, "标注数量": 0, "命中数量": 0, "准确率": 0.0}

    correct = int((labels[valid_mask] == predictions[valid_mask]).sum())
    return {
        "任务": task_name,
        "标注数量": total,
        "命中数量": correct,
        "准确率": round(correct / total, 4),
    }


def evaluate_annotations(predictions: pd.DataFrame, annotations: pd.DataFrame) -> pd.DataFrame:
    """基于人工标注 CSV 计算最小准确率指标。"""
    if predictions.empty or annotations.empty or "article_id" not in annotations.columns:
        return pd.DataFrame(columns=["任务", "标注数量", "命中数量", "准确率"])

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
                    "指标": METRIC_LABELS[metric],
                    "公式版本": version,
                    "均值": float(values.mean()),
                    "标准差": float(values.std(ddof=0)),
                    "最小值": float(values.min()),
                    "最大值": float(values.max()),
                    "范围": float(values.max() - values.min()),
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
        result[str(sector)]["polarity_mix"] = polarity_mix(
            group.get("sentiment_score", pd.Series(0.0, index=group.index)),
            weights,
        )
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
            return "成长与多头立场词未命中；变化来自 FinBERT 概率权重由 1.0 调整为 0.7"
        leading = "多头立场" if 0.2 * bull >= 0.1 * growth else "成长主题"
        return f"主要增强项：{leading}（B_bull={bull:.2f}, G_growth={growth:.2f}）"
    if metric == "fear":
        bear = values.get("b_bear", 0.0)
        shock = values.get("s_shock", 0.0)
        if bear == 0 and shock == 0:
            return "冲击与空头立场词未命中；变化来自 FinBERT 概率权重由 1.0 调整为 0.7"
        leading = "空头立场" if 0.2 * bear >= 0.1 * shock else "恐慌冲击"
        return f"主要增强项：{leading}（B_bear={bear:.2f}, S_shock={shock:.2f}）"
    if metric == "uncertainty":
        uncertainty = values.get("k_unc", 0.0)
        return (
            f"LM 不确定性词组件 K_unc={uncertainty:.2f}，并重配 neutral/entropy 权重"
            if uncertainty
            else "未命中 LM 不确定性词；变化来自 neutral/entropy 权重重配"
        )
    if metric == "attention":
        days = history_days.get(sector, 0)
        if days < ATTENTION_MIN_HISTORY_DAYS:
            return f"历史 {days} 天，未达 {ATTENTION_MIN_HISTORY_DAYS} 天；两组均使用冷启动排名"
        return f"历史 {days} 天；Enhanced 在自身历史 ECDF 中加入 30% 新闻量增长率"
    if metric == "disagreement":
        return f"Enhanced 加入 50% 正负极性混合度（PolarityMix={values.get('polarity_mix', 0):.2f}）"
    return "Risk Intensity 本批两组权重相同，公式与排名不变"


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
                    "指标": METRIC_LABELS[metric],
                    "板块": sector,
                    "Baseline 排名": float(row["baseline_rank"]),
                    "Enhanced 排名": float(row["enhanced_rank"]),
                    "排名变化（正数=上升）": float(row["rank_change"]),
                    "Baseline 分数": float(row[f"{metric}_baseline"]),
                    "Enhanced 分数": float(row[f"{metric}_enhanced"]),
                    "主要原因": _rank_change_reason(
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
        "b_bull": "多头立场",
        "b_bear": "空头立场",
        "g_growth": "成长",
        "s_shock": "冲击",
        "k_unc": "不确定性",
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
                "新闻": str(record.get("title", "")),
                "板块": str(record.get("sector", "")),
                "命中增强词": "；".join(term_parts) or "无",
                "Baseline 乐观度": baseline_values["optimism"],
                "Enhanced 乐观度": enhanced_values["optimism"],
                "乐观度变化": enhanced_values["optimism"] - baseline_values["optimism"],
                "Baseline 恐惧度": baseline_values["fear"],
                "Enhanced 恐惧度": enhanced_values["fear"],
                "恐惧度变化": enhanced_values["fear"] - baseline_values["fear"],
                "Baseline 不确定性": baseline_values["uncertainty"],
                "Enhanced 不确定性": enhanced_values["uncertainty"],
                "不确定性变化": enhanced_values["uncertainty"] - baseline_values["uncertainty"],
            }
        )
    return pd.DataFrame(rows)
