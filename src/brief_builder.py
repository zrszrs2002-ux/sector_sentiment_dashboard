from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from src.aggregation import market_metrics, sector_metrics
from src.config import BRIEF_WINDOW_HOURS, METRIC_COLUMNS, PIPELINE_REVISION, SECTORS
from src.daily_snapshots import load_market_snapshots, load_sector_snapshots
from src.driver_analysis import macro_articles, top_driver_articles
from src.rss_sources import distinct_value_count


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso_or_none(value: object) -> str | None:
    if pd.isna(value):
        return None
    try:
        return pd.Timestamp(value).tz_convert("UTC").isoformat()
    except (TypeError, ValueError):
        return None


def _round_metric(value: object) -> float:
    try:
        numeric = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    if pd.isna(numeric):
        return 0.0
    return round(numeric, 1)


def _window_articles(df: pd.DataFrame, generated_at: datetime) -> tuple[pd.DataFrame, pd.Timestamp, pd.Timestamp]:
    end_ts = pd.Timestamp(generated_at).tz_convert("UTC")
    start_ts = end_ts - pd.Timedelta(hours=BRIEF_WINDOW_HOURS)
    if df.empty or "published_at" not in df:
        return df.head(0).copy(), start_ts, end_ts
    working = df.copy()
    working["published_at"] = pd.to_datetime(working["published_at"], utc=True, errors="coerce")
    window = working[(working["published_at"] >= start_ts) & (working["published_at"] <= end_ts)].copy()
    return window, start_ts, end_ts


def _select_snapshot_rows(rows: pd.DataFrame, key_columns: list[str]) -> pd.DataFrame:
    """Select one row per key, preferring the active pipeline then the latest timestamp."""
    if rows.empty:
        return rows.copy()
    selected = rows.copy()
    pipeline_values = (
        selected["pipeline_revision"]
        if "pipeline_revision" in selected
        else pd.Series("", index=selected.index, dtype="object")
    )
    timestamp_values = (
        selected["snapshot_timestamp"]
        if "snapshot_timestamp" in selected
        else pd.Series("", index=selected.index, dtype="object")
    )
    selected["_preferred_pipeline"] = (
        pipeline_values.fillna("").astype(str).eq(PIPELINE_REVISION).astype(int)
    )
    selected["_snapshot_order"] = pd.to_datetime(
        timestamp_values, utc=True, errors="coerce"
    )
    selected = selected.sort_values(
        ["_preferred_pipeline", "_snapshot_order"],
        kind="stable",
        na_position="first",
    )
    if key_columns:
        selected = selected.drop_duplicates(key_columns, keep="last")
    else:
        selected = selected.tail(1)
    return selected.drop(columns=["_preferred_pipeline", "_snapshot_order"])


def _previous_market_snapshot(data_source: str, snapshot_date) -> dict[str, Any] | None:
    snapshots = load_market_snapshots(data_source)
    if snapshots.empty:
        return None
    previous = snapshots[snapshots["snapshot_date"] < snapshot_date]
    if previous.empty:
        return None
    latest_date = previous["snapshot_date"].max()
    selected = _select_snapshot_rows(previous[previous["snapshot_date"].eq(latest_date)], [])
    return selected.iloc[-1].to_dict()


def _previous_sector_snapshots(data_source: str, snapshot_date) -> pd.DataFrame:
    snapshots = load_sector_snapshots(data_source)
    if snapshots.empty:
        return snapshots
    previous_dates = sorted(date for date in snapshots["snapshot_date"].dropna().unique() if date < snapshot_date)
    if not previous_dates:
        return snapshots.head(0)
    previous = snapshots[snapshots["snapshot_date"].eq(previous_dates[-1])].copy()
    return _select_snapshot_rows(previous, ["sector"])


def _metric_deltas(current: dict[str, float], previous: dict[str, Any] | None) -> dict[str, float | None]:
    deltas: dict[str, float | None] = {}
    for metric in METRIC_COLUMNS:
        if previous is None:
            deltas[metric] = None
        else:
            deltas[metric] = _round_metric(
                float(current.get(metric, 0) or 0) - float(previous.get(metric, 0) or 0)
            )
    return deltas


def _seven_day_positions(
    data_source: str,
    snapshot_date,
    current: dict[str, float],
) -> dict[str, str]:
    snapshots = load_market_snapshots(data_source)
    if snapshots.empty:
        return {}
    history = snapshots[snapshots["snapshot_date"].notna() & (snapshots["snapshot_date"] <= snapshot_date)].copy()
    history = history.sort_values("snapshot_date").drop_duplicates("snapshot_date", keep="last").tail(7)
    if history["snapshot_date"].nunique() < 7:
        return {}

    labels: dict[str, str] = {}
    for metric in METRIC_COLUMNS:
        values = pd.to_numeric(history[metric], errors="coerce").dropna()
        if len(values) < 7:
            return {}
        current_value = float(current.get(metric, 0) or 0)
        lower_days = int((values < current_value).sum())
        higher_days = int((values > current_value).sum())
        if lower_days == 0 and higher_days == 0:
            labels[metric] = "与近 7 日水平基本持平"
        elif lower_days == 0:
            labels[metric] = "未高于近 7 日中的任何一天"
        elif lower_days == 7:
            labels[metric] = "高于近 7 日全部 7 天"
        else:
            labels[metric] = f"高于近 7 日中 {lower_days} 天"
    return labels


def _sector_rankings(sector_df: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    rankings: dict[str, list[dict[str, Any]]] = {}
    if sector_df.empty:
        return rankings
    for metric in METRIC_COLUMNS:
        rankings[metric] = [
            {
                "sector": str(row.get("sector", "")),
                "score": _round_metric(row.get(metric, 0)),
                "article_count": int(row.get("article_count", 0) or 0),
            }
            for row in sector_df.sort_values(metric, ascending=False).to_dict("records")
        ]
    return rankings


def _sector_movers(sector_df: pd.DataFrame, previous: pd.DataFrame) -> list[dict[str, Any]]:
    if sector_df.empty or previous.empty:
        return []
    previous_by_sector = _select_snapshot_rows(previous, ["sector"]).set_index("sector")
    movers: list[dict[str, Any]] = []
    for row in sector_df.to_dict("records"):
        sector = str(row.get("sector", ""))
        if sector not in previous_by_sector.index:
            continue
        prev_row = previous_by_sector.loc[sector]
        metric_changes = {
            metric: _round_metric(float(row.get(metric, 0) or 0) - float(prev_row.get(metric, 0) or 0))
            for metric in METRIC_COLUMNS
        }
        movers.append(
            {
                "sector": sector,
                "total_abs_delta": _round_metric(sum(abs(value) for value in metric_changes.values())),
                "metric_changes": metric_changes,
            }
        )
    return sorted(movers, key=lambda item: item["total_abs_delta"], reverse=True)[:5]


def _drivers(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    drivers = top_driver_articles(df, limit=5)
    rows: list[dict[str, Any]] = []
    for row in drivers.to_dict("records"):
        evidence_sentence = str(row.get("evidence_sentence", ""))
        event_id = str(row.get("event_id", ""))
        if event_id and "content_level" in df and "event_id" in df:
            fulltext_members = df[
                df["event_id"].fillna("").astype(str).eq(event_id)
                & df["content_level"].fillna("").astype(str).eq("fulltext")
            ].copy()
            if not fulltext_members.empty:
                fulltext_members["_weight"] = pd.to_numeric(
                    fulltext_members.get("agg_weight", 0), errors="coerce"
                ).fillna(0)
                evidence_sentence = str(
                    fulltext_members.sort_values("_weight", ascending=False).iloc[0].get(
                        "evidence_sentence", evidence_sentence
                    )
                )
        rows.append(
            {
                "title": str(row.get("title", "")),
                "sector": str(row.get("sector", "")),
                "driver_reason": str(row.get("driver_reason", "")),
                "evidence_sentence": evidence_sentence,
                "url": str(row.get("url", "")),
                "source_count": int(row.get("source_count", 0) or 0),
                "related_article_count": int(row.get("event_article_count", 1) or 1),
            }
        )
    return rows


def _topic_distribution(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty or "topic" not in df:
        return []
    topics = df["topic"].fillna("").astype(str).str.strip()
    counts = topics[topics.ne("")].value_counts().head(5)
    return [{"topic": str(topic), "article_count": int(count)} for topic, count in counts.items()]


def _risk_distribution(df: pd.DataFrame) -> dict[str, int]:
    if df.empty or "risk_category" not in df:
        return {}
    risks = df["risk_category"].fillna("").astype(str).str.strip()
    counts = risks[risks.ne("")].value_counts().head(5)
    return {str(risk): int(count) for risk, count in counts.items()}


def _sector_sentiment_counts(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty or "sector" not in df or "sentiment_score" not in df:
        return [
            {"sector": sector, "positive_article_count": 0, "negative_article_count": 0}
            for sector in SECTORS
        ]
    scores = pd.to_numeric(df["sentiment_score"], errors="coerce").fillna(0)
    rows: list[dict[str, Any]] = []
    for sector in SECTORS:
        sector_scores = scores[df["sector"].astype(str).eq(sector)]
        rows.append(
            {
                "sector": sector,
                "positive_article_count": int((sector_scores > 0).sum()),
                "negative_article_count": int((sector_scores < 0).sum()),
            }
        )
    return rows


def _display_sector(value: object) -> str:
    sector = str(value or "").strip()
    return "宏观/市场" if sector in {"", "Unmapped"} else sector


def _sentiment_news_rows(df: pd.DataFrame, positive: bool) -> list[dict[str, str]]:
    if df.empty or "sentiment_score" not in df or "title" not in df:
        return []
    working = df.copy()
    working["_sentiment_score"] = pd.to_numeric(working["sentiment_score"], errors="coerce").fillna(0)
    working = working[working["_sentiment_score"].gt(0)] if positive else working[working["_sentiment_score"].lt(0)]
    working = working.sort_values("_sentiment_score", ascending=not positive)
    working = working.drop_duplicates(subset=["title"], keep="first").head(3)
    return [
        {
            "title": str(row.get("title", "")),
            "sector": _display_sector(row.get("sector", "")),
            "evidence_sentence": str(row.get("evidence_sentence", "")),
        }
        for row in working.to_dict("records")
        if str(row.get("title", "")).strip()
    ]


def _sentiment_extremes(df: pd.DataFrame) -> dict[str, list[dict[str, str]]]:
    return {
        "most_positive_top3": _sentiment_news_rows(df, positive=True),
        "most_negative_top3": _sentiment_news_rows(df, positive=False),
    }


def build_brief_payload(df: pd.DataFrame, data_source: str, generated_at: datetime | None = None) -> dict[str, Any]:
    generated_at = generated_at or _utc_now()
    snapshot_date = generated_at.date()
    window_df, window_start, window_end = _window_articles(df, generated_at)

    market_scores = {
        metric: _round_metric(value)
        for metric, value in market_metrics(window_df, data_source=data_source).items()
    }
    sector_df = sector_metrics(window_df, data_source=data_source)
    previous_market = _previous_market_snapshot(data_source, snapshot_date)
    previous_sector = _previous_sector_snapshots(data_source, snapshot_date)
    macro_df = macro_articles(window_df).sort_values("published_at", ascending=False)

    valid_times = window_df["published_at"].dropna() if "published_at" in window_df else pd.Series(dtype="datetime64[ns, UTC]")
    latest_collected = window_df["collected_at"].max() if "collected_at" in window_df and not window_df.empty else pd.NaT
    snapshot_id = f"{data_source}|{_iso_or_none(latest_collected) or 'no-collected-at'}|{len(window_df)}"

    market_payload: dict[str, Any] = {
        "scores": market_scores,
        "delta_vs_previous_day": _metric_deltas(market_scores, previous_market),
    }
    seven_day_positions = _seven_day_positions(data_source, snapshot_date, market_scores)
    if seven_day_positions:
        market_payload["seven_day_position"] = seven_day_positions

    return {
        "generated_at": generated_at.astimezone(UTC).isoformat(timespec="seconds"),
        "data_window": {
            "start": window_start.isoformat(),
            "end": window_end.isoformat(),
            "hours": BRIEF_WINDOW_HOURS,
        },
        "snapshot_id": snapshot_id,
        "data_source": data_source,
        "market": market_payload,
        "sectors": {
            "rankings": _sector_rankings(sector_df),
            "movers": _sector_movers(sector_df, previous_sector),
        },
        "top_drivers": _drivers(window_df),
        "topic_distribution_top5": _topic_distribution(window_df),
        "sector_sentiment_counts": _sector_sentiment_counts(window_df),
        "sentiment_extremes": _sentiment_extremes(window_df),
        "risk_distribution_top5": _risk_distribution(window_df),
        "unmapped_macro_titles": macro_df["title"].dropna().astype(str).head(5).tolist()
        if "title" in macro_df
        else [],
        "coverage": {
            "article_count": int(len(window_df)),
            "source_count": distinct_value_count(
                window_df["publisher"] if "publisher" in window_df else window_df.get("source", []),
                window_df.get("source", []),
            ),
            "time_range": {
                "min_published_at": _iso_or_none(valid_times.min()) if not valid_times.empty else None,
                "max_published_at": _iso_or_none(valid_times.max()) if not valid_times.empty else None,
            },
            "data_source": data_source,
        },
    }
