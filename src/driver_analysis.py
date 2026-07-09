from __future__ import annotations

import pandas as pd


def macro_articles(df: pd.DataFrame) -> pd.DataFrame:
    """返回未映射到 11 个板块的宏观/市场级新闻。"""
    if df.empty or "sector" not in df:
        return df.head(0).copy()
    return df[df["sector"].fillna("").astype(str).eq("Unmapped")].copy()


def normalized_weight_score(weights: pd.Series) -> pd.Series:
    clean_weights = pd.to_numeric(weights, errors="coerce").fillna(0).clip(lower=0)
    max_weight = float(clean_weights.max()) if len(clean_weights) else 0.0
    if max_weight <= 0:
        return pd.Series(0.0, index=weights.index)
    return clean_weights / max_weight * 100


def driver_reason(row: pd.Series) -> str:
    if str(row.get("sector", "")) == "Unmapped":
        return "宏观/市场级新闻，进入 Market Brief 和 Top Drivers，但不摊入板块聚合。"
    if float(row.get("risk_intensity", 0)) >= 70:
        return "风险强度较高，可能影响板块情绪。"
    if abs(float(row.get("sentiment_score", 0))) >= 0.25:
        return "情绪方向明显，可能推动乐观或恐惧指标。"
    return "综合风险、情绪幅度、不确定性和聚合权重后排名靠前。"


def add_driver_scores(df: pd.DataFrame) -> pd.DataFrame:
    """为新闻添加 Top Drivers 展示层分数，不改变六维聚合。"""
    if df.empty:
        return df.copy()

    scored = df.copy()
    risk = pd.to_numeric(scored.get("risk_intensity", 0), errors="coerce").fillna(0)
    sentiment_impact = pd.to_numeric(scored.get("sentiment_score", 0), errors="coerce").fillna(0).abs() * 100
    uncertainty = pd.to_numeric(scored.get("uncertainty", 0), errors="coerce").fillna(0)
    weight_score = normalized_weight_score(scored.get("agg_weight", pd.Series(0, index=scored.index)))
    scored["driver_score"] = (
        0.4 * risk
        + 0.25 * sentiment_impact
        + 0.2 * uncertainty
        + 0.15 * weight_score
    )
    scored["driver_reason"] = scored.apply(driver_reason, axis=1)
    return scored


def top_driver_articles(df: pd.DataFrame, limit: int = 5, macro_limit: int = 1) -> pd.DataFrame:
    """返回重点驱动新闻，并确保 Unmapped 宏观新闻可进入展示层。"""
    scored = add_driver_scores(df)
    if scored.empty:
        return scored

    top_regular = scored.sort_values("driver_score", ascending=False).head(limit)
    top_macro = macro_articles(scored).sort_values("driver_score", ascending=False).head(macro_limit)
    if top_macro.empty:
        return top_regular

    if "article_id" in scored:
        macro_ids = set(top_macro["article_id"].astype(str))
        regular_fill = top_regular[~top_regular["article_id"].astype(str).isin(macro_ids)]
    else:
        macro_keys = set(zip(top_macro["url"].astype(str), top_macro["title"].astype(str), strict=True))
        regular_fill = top_regular[
            ~top_regular.apply(lambda row: (str(row.get("url", "")), str(row.get("title", ""))) in macro_keys, axis=1)
        ]
    return pd.concat([top_macro, regular_fill], ignore_index=True).head(limit)
