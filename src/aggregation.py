import pandas as pd

from src.config import METRIC_COLUMNS


def sector_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """按板块汇总 demo 指标，后续会替换为带时间衰减和去重权重的聚合逻辑。"""
    if df.empty:
        return pd.DataFrame(columns=["sector", "article_count", *METRIC_COLUMNS])

    grouped = (
        df.groupby("sector", as_index=False)
        .agg(
            article_count=("article_id", "count"),
            optimism=("optimism", "mean"),
            fear=("fear", "mean"),
            uncertainty=("uncertainty", "mean"),
            attention_weight=("attention_weight", "mean"),
            disagreement_input=("disagreement_input", "mean"),
            risk_intensity=("risk_intensity", "mean"),
        )
        .sort_values("sector")
    )
    return grouped


def market_metrics(df: pd.DataFrame) -> dict[str, float]:
    """计算市场级 demo 指标，当前使用简单平均作为第一阶段占位方案。"""
    if df.empty:
        return {column: 0.0 for column in METRIC_COLUMNS}
    return {column: float(df[column].mean()) for column in METRIC_COLUMNS}


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
