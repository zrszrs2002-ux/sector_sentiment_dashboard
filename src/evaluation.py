import pandas as pd


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
