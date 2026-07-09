from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from src.aggregation import market_metrics, sector_metrics
from src.config import BRIEF_WINDOW_HOURS, METRIC_COLUMNS
from src.daily_snapshots import load_market_snapshots, load_sector_snapshots
from src.driver_analysis import macro_articles, top_driver_articles


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso_or_none(value: object) -> str | None:
    if pd.isna(value):
        return None
    try:
        return pd.Timestamp(value).tz_convert("UTC").isoformat()
    except (TypeError, ValueError):
        return None


def _window_articles(df: pd.DataFrame, generated_at: datetime) -> tuple[pd.DataFrame, pd.Timestamp, pd.Timestamp]:
    end_ts = pd.Timestamp(generated_at).tz_convert("UTC")
    start_ts = end_ts - pd.Timedelta(hours=BRIEF_WINDOW_HOURS)
    if df.empty or "published_at" not in df:
        return df.head(0).copy(), start_ts, end_ts
    working = df.copy()
    working["published_at"] = pd.to_datetime(working["published_at"], utc=True, errors="coerce")
    window = working[(working["published_at"] >= start_ts) & (working["published_at"] <= end_ts)].copy()
    return window, start_ts, end_ts


def _previous_market_snapshot(data_source: str, snapshot_date) -> dict[str, Any] | None:
    snapshots = load_market_snapshots(data_source)
    if snapshots.empty:
        return None
    previous = snapshots[snapshots["snapshot_date"] < snapshot_date].sort_values("snapshot_date")
    if previous.empty:
        return None
    return previous.iloc[-1].to_dict()


def _previous_sector_snapshots(data_source: str, snapshot_date) -> pd.DataFrame:
    snapshots = load_sector_snapshots(data_source)
    if snapshots.empty:
        return snapshots
    previous_dates = sorted(date for date in snapshots["snapshot_date"].dropna().unique() if date < snapshot_date)
    if not previous_dates:
        return snapshots.head(0)
    return snapshots[snapshots["snapshot_date"].eq(previous_dates[-1])].copy()


def _metric_deltas(current: dict[str, float], previous: dict[str, Any] | None) -> dict[str, float | None]:
    deltas: dict[str, float | None] = {}
    for metric in METRIC_COLUMNS:
        if previous is None:
            deltas[metric] = None
        else:
            deltas[metric] = round(float(current.get(metric, 0) or 0) - float(previous.get(metric, 0) or 0), 3)
    return deltas


def _sector_rankings(sector_df: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    rankings: dict[str, list[dict[str, Any]]] = {}
    if sector_df.empty:
        return rankings
    for metric in METRIC_COLUMNS:
        rankings[metric] = [
            {
                "sector": str(row.get("sector", "")),
                "score": round(float(row.get(metric, 0) or 0), 2),
                "article_count": int(row.get("article_count", 0) or 0),
            }
            for row in sector_df.sort_values(metric, ascending=False).to_dict("records")
        ]
    return rankings


def _sector_movers(sector_df: pd.DataFrame, previous: pd.DataFrame) -> list[dict[str, Any]]:
    if sector_df.empty or previous.empty:
        return []
    previous_by_sector = previous.set_index("sector")
    movers: list[dict[str, Any]] = []
    for row in sector_df.to_dict("records"):
        sector = str(row.get("sector", ""))
        if sector not in previous_by_sector.index:
            continue
        prev_row = previous_by_sector.loc[sector]
        metric_changes = {
            metric: round(float(row.get(metric, 0) or 0) - float(prev_row.get(metric, 0) or 0), 3)
            for metric in METRIC_COLUMNS
        }
        movers.append(
            {
                "sector": sector,
                "total_abs_delta": round(sum(abs(value) for value in metric_changes.values()), 3),
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
        rows.append(
            {
                "title": str(row.get("title", "")),
                "sector": str(row.get("sector", "")),
                "driver_reason": str(row.get("driver_reason", "")),
                "evidence_sentence": str(row.get("evidence_sentence", "")),
                "url": str(row.get("url", "")),
            }
        )
    return rows


def build_brief_payload(df: pd.DataFrame, data_source: str, generated_at: datetime | None = None) -> dict[str, Any]:
    generated_at = generated_at or _utc_now()
    snapshot_date = generated_at.date()
    window_df, window_start, window_end = _window_articles(df, generated_at)

    market_scores = {metric: round(float(value), 3) for metric, value in market_metrics(window_df).items()}
    sector_df = sector_metrics(window_df)
    previous_market = _previous_market_snapshot(data_source, snapshot_date)
    previous_sector = _previous_sector_snapshots(data_source, snapshot_date)
    macro_df = macro_articles(window_df).sort_values("published_at", ascending=False)

    valid_times = window_df["published_at"].dropna() if "published_at" in window_df else pd.Series(dtype="datetime64[ns, UTC]")
    latest_collected = window_df["collected_at"].max() if "collected_at" in window_df and not window_df.empty else pd.NaT
    snapshot_id = f"{data_source}|{_iso_or_none(latest_collected) or 'no-collected-at'}|{len(window_df)}"

    return {
        "generated_at": generated_at.astimezone(UTC).isoformat(timespec="seconds"),
        "data_window": {
            "start": window_start.isoformat(),
            "end": window_end.isoformat(),
            "hours": BRIEF_WINDOW_HOURS,
        },
        "snapshot_id": snapshot_id,
        "data_source": data_source,
        "market": {
            "scores": market_scores,
            "delta_vs_previous_day": _metric_deltas(market_scores, previous_market),
        },
        "sectors": {
            "rankings": _sector_rankings(sector_df),
            "movers": _sector_movers(sector_df, previous_sector),
        },
        "top_drivers": _drivers(window_df),
        "risk_distribution_top5": window_df["risk_category"].value_counts().head(5).to_dict()
        if "risk_category" in window_df
        else {},
        "unmapped_macro_titles": macro_df["title"].dropna().astype(str).head(5).tolist()
        if "title" in macro_df
        else [],
        "coverage": {
            "article_count": int(len(window_df)),
            "source_count": int(window_df["source"].nunique()) if "source" in window_df else 0,
            "time_range": {
                "min_published_at": _iso_or_none(valid_times.min()) if not valid_times.empty else None,
                "max_published_at": _iso_or_none(valid_times.max()) if not valid_times.empty else None,
            },
            "data_source": data_source,
        },
    }
