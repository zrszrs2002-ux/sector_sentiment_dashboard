from __future__ import annotations

import pandas as pd

from src.config import DRIVER_MIN_EVENTS, DRIVER_WINDOW_HOURS, EVENT_COVERAGE_BOOST
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


# Driver reason copy is maintained here in one place (user-facing language, no internal detail).
def driver_reason(row: pd.Series) -> str:
    if str(row.get("sector", "")) == "Unmapped":
        return "Macro/market-level news: shapes overall market sentiment and isn't tied to a single sector."
    if float(row.get("risk_intensity", 0)) >= 70:
        return "Contains a clear high-intensity risk factor that may pressure sector sentiment."
    if abs(float(row.get("sentiment_score", 0))) >= 0.25:
        return "Sentiment direction is pronounced, which may drive the optimism or fear metrics."
    return "Ranked highly after combining risk, sentiment, and attention signals."


def coverage_reason(source_count: int) -> str:
    return f"Covered jointly by {int(source_count)} outlets, so its importance was boosted."


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
    for row in group.to_dict("records"):
        sources.update(split_sources(row.get("publisher", "") or row.get("source", "")))
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
    article_fields = [
        "article_id",
        "title",
        "source",
        "publisher",
        "published_at",
        "url",
        "agg_weight",
        "content_level",
        "evidence_sentence",
    ]
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
    boosted = events["coverage_boost_applied"]
    events.loc[boosted, "driver_reason"] = events.loc[boosted, "driver_reason"].astype(str) + " " + source_counts[
        boosted
    ].astype(int).map(coverage_reason)
    return events


def _utc_timestamp(value: object | None) -> pd.Timestamp:
    timestamp = pd.Timestamp.now(tz="UTC") if value is None else pd.Timestamp(value)
    if pd.isna(timestamp):
        raise ValueError("Invalid reference time for Top Drivers.")
    return timestamp.tz_localize("UTC") if timestamp.tzinfo is None else timestamp.tz_convert("UTC")


def _driver_window_options(initial_window_hours: int) -> tuple[int, ...]:
    initial = max(1, int(initial_window_hours))
    return tuple(dict.fromkeys(hours for hours in (initial, 72, 168) if hours >= initial))


def recent_event_driver_rows(
    df: pd.DataFrame,
    window_hours: int = DRIVER_WINDOW_HOURS,
    min_events: int = DRIVER_MIN_EVENTS,
    reference_time: object | None = None,
) -> tuple[pd.DataFrame, int]:
    """事件折叠前先按发布时间筛选，并在新闻荒时逐级扩窗。"""
    windows = _driver_window_options(window_hours)
    used_window = windows[-1]
    if df.empty or "published_at" not in df:
        return df.head(0).copy(), used_window

    reference = _utc_timestamp(reference_time)
    published = pd.to_datetime(df["published_at"], errors="coerce", utc=True)
    required_events = max(1, int(min_events))
    last_events = df.head(0).copy()
    for candidate_window in windows:
        threshold = reference - pd.Timedelta(hours=candidate_window)
        window_articles = df.loc[published.ge(threshold)].copy()
        events = event_driver_rows(window_articles)
        last_events = events
        used_window = candidate_window
        if len(events) >= required_events:
            break
    return last_events, used_window


def top_driver_articles(
    df: pd.DataFrame,
    limit: int = 5,
    macro_limit: int = 1,
    window_hours: int | None = None,
    min_events: int = DRIVER_MIN_EVENTS,
    reference_time: object | None = None,
) -> pd.DataFrame:
    """返回重点驱动事件；传入窗口时仅折叠和排序窗口内新闻。"""
    used_window: int | None = None
    if window_hours is None:
        events = event_driver_rows(df)
    else:
        events, used_window = recent_event_driver_rows(
            df,
            window_hours=window_hours,
            min_events=min_events,
            reference_time=reference_time,
        )
    if events.empty:
        if used_window is not None:
            events.attrs["driver_window_hours"] = used_window
        return events

    ranked_events = events.sort_values("driver_score", ascending=False, kind="stable")
    top_regular = ranked_events.head(limit)
    top_macro = macro_articles(ranked_events).head(macro_limit)
    guaranteed_macro_ids: set[str] = set()
    if top_macro.empty:
        result = top_regular
    else:
        natural_ids = set(top_regular["event_id"].astype(str))
        macro_ids = set(top_macro["event_id"].astype(str))
        guaranteed_macro_ids = macro_ids - natural_ids
        if guaranteed_macro_ids:
            non_macro = ranked_events[~ranked_events["event_id"].astype(str).isin(macro_ids)]
            regular_slots = max(0, limit - len(top_macro))
            result = pd.concat([non_macro.head(regular_slots), top_macro], ignore_index=True)
        else:
            result = top_regular
    result = result.sort_values("driver_score", ascending=False, kind="stable").head(limit).copy()
    result["macro_guaranteed"] = result["event_id"].astype(str).isin(guaranteed_macro_ids)
    if used_window is not None:
        result.attrs["driver_window_hours"] = used_window
    return result
