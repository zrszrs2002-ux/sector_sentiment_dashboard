from __future__ import annotations

import pandas as pd

from src.config import EVENT_COVERAGE_BOOST
from src.event_clustering import split_sources


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


def _with_event_keys(df: pd.DataFrame) -> pd.DataFrame:
    working = df.copy()
    if "article_id" in working:
        fallback = working["article_id"].fillna("").astype(str)
    else:
        fallback = pd.Series([f"row-{index}" for index in working.index], index=working.index)
    if "event_id" not in working:
        working["event_id"] = fallback
    else:
        event_ids = working["event_id"].fillna("").astype(str).str.strip()
        working["event_id"] = event_ids.where(event_ids.ne(""), fallback)
    return working


def _representative(group: pd.DataFrame) -> pd.Series:
    ranked = group.copy()
    weights = ranked["agg_weight"] if "agg_weight" in ranked else pd.Series(0, index=ranked.index)
    ranked["_agg_weight"] = pd.to_numeric(weights, errors="coerce").fillna(0)
    if "article_id" not in ranked:
        ranked["article_id"] = ranked.index.astype(str)
    ranked["_article_id"] = ranked["article_id"].fillna("").astype(str)
    return ranked.sort_values(["_agg_weight", "_article_id"], ascending=[False, True]).iloc[0].copy()


def _distinct_source_count(group: pd.DataFrame) -> int:
    sources: set[str] = set()
    if "source" in group:
        for value in group["source"]:
            sources.update(split_sources(value))
    stored_count = 0
    if "source_count" in group:
        values = pd.to_numeric(group["source_count"], errors="coerce").fillna(0)
        stored_count = int(values.max()) if not values.empty else 0
    return len(sources) if sources else stored_count


def collapse_articles_by_event(df: pd.DataFrame) -> pd.DataFrame:
    """Return one highest-agg-weight representative per persisted event ID."""
    if df.empty:
        return df.copy()

    working = _with_event_keys(df)
    rows: list[dict[str, object]] = []
    article_fields = ["article_id", "title", "source", "published_at", "url", "agg_weight"]
    if "driver_score" in working:
        article_fields.append("driver_score")

    for event_id, group in working.groupby("event_id", sort=False, dropna=False):
        representative = _representative(group)
        row = representative.drop(labels=["_agg_weight", "_article_id"], errors="ignore").to_dict()
        row["event_id"] = str(event_id)
        row["event_article_count"] = int(len(group))
        row["source_count"] = _distinct_source_count(group)
        row["event_articles"] = group.sort_values("published_at", ascending=False, na_position="last").reindex(
            columns=article_fields
        ).to_dict("records")
        if "driver_score" in group:
            article_scores = pd.to_numeric(group["driver_score"], errors="coerce").fillna(0)
            row["representative_driver_score"] = float(representative.get("driver_score", 0) or 0)
            row["driver_score"] = float(article_scores.max())
        rows.append(row)
    return pd.DataFrame(rows)


def event_driver_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Build event-level driver rows without mutating article aggregation fields."""
    events = collapse_articles_by_event(add_driver_scores(df))
    if events.empty:
        return events

    source_counts = pd.to_numeric(events["source_count"], errors="coerce").fillna(0)
    events["coverage_boost_applied"] = source_counts.ge(3)
    events["driver_score"] = pd.to_numeric(events["driver_score"], errors="coerce").fillna(0)
    events.loc[events["coverage_boost_applied"], "driver_score"] *= EVENT_COVERAGE_BOOST
    events["driver_score"] = events["driver_score"].clip(upper=100 * EVENT_COVERAGE_BOOST)
    events.loc[events["coverage_boost_applied"], "driver_reason"] = events.loc[
        events["coverage_boost_applied"], "driver_reason"
    ].astype(str) + f" 覆盖至少 3 家媒体，事件分数乘以 {EVENT_COVERAGE_BOOST:.2f}。"
    return events


def top_driver_articles(df: pd.DataFrame, limit: int = 5, macro_limit: int = 1) -> pd.DataFrame:
    """返回重点驱动事件，并确保 Unmapped 宏观事件可进入展示层。"""
    events = event_driver_rows(df)
    if events.empty:
        return events

    top_regular = events.sort_values("driver_score", ascending=False).head(limit)
    top_macro = macro_articles(events).sort_values("driver_score", ascending=False).head(macro_limit)
    if top_macro.empty:
        return top_regular

    macro_ids = set(top_macro["event_id"].astype(str))
    regular_fill = top_regular[~top_regular["event_id"].astype(str).isin(macro_ids)]
    return pd.concat([top_macro, regular_fill], ignore_index=True).head(limit)
