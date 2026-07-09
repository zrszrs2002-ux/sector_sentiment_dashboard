from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError, ParserError

from src.aggregation import market_metrics, sector_metrics
from src.config import (
    EXPECTED_ARTICLE_COLUMNS,
    MARKET_DAILY_SCORES_PATH,
    METRIC_COLUMNS,
    SECTOR_DAILY_SCORES_PATH,
)
from src.preprocessing import write_csv_atomic


SECTOR_SNAPSHOT_FIELDS = [
    "snapshot_date",
    "snapshot_timestamp",
    "data_source",
    "sector",
    "article_count",
    *METRIC_COLUMNS,
]
MARKET_SNAPSHOT_FIELDS = [
    "snapshot_date",
    "snapshot_timestamp",
    "data_source",
    "article_count",
    *METRIC_COLUMNS,
]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (OSError, EmptyDataError, ParserError, UnicodeDecodeError):
        return pd.DataFrame()


def articles_to_dataframe(records: list[dict[str, str]]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame(columns=EXPECTED_ARTICLE_COLUMNS)

    for column in EXPECTED_ARTICLE_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    df = df.reindex(columns=EXPECTED_ARTICLE_COLUMNS)

    for column in ["published_at", "collected_at"]:
        df[column] = pd.to_datetime(df[column], utc=True, errors="coerce")

    numeric_columns = [
        "p_positive",
        "p_neutral",
        "p_negative",
        "sentiment_score",
        "optimism",
        "fear",
        "uncertainty",
        "attention",
        "attention_weight",
        "disagreement",
        "disagreement_input",
        "risk_intensity",
        "model_confidence",
        "relevance_weight",
        "time_weight",
        "agg_weight",
        "dedup_factor",
    ]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)
    return df


def _upsert_rows(path: Path, fieldnames: list[str], rows: list[dict[str, object]], key_fields: list[str]) -> None:
    existing = _read_csv(path)
    if existing.empty:
        write_csv_atomic(path, fieldnames, rows)
        return

    for column in fieldnames:
        if column not in existing.columns:
            existing[column] = ""
    existing = existing.reindex(columns=fieldnames)

    incoming_keys = {tuple(str(row.get(key, "")) for key in key_fields) for row in rows}
    keep_mask = existing.apply(
        lambda row: tuple(str(row.get(key, "")) for key in key_fields) not in incoming_keys,
        axis=1,
    )
    merged = pd.concat([existing[keep_mask], pd.DataFrame(rows)], ignore_index=True)
    merged = merged.sort_values(key_fields).reset_index(drop=True)
    write_csv_atomic(path, fieldnames, merged.to_dict("records"))


def write_daily_snapshots(records: list[dict[str, str]], data_source: str) -> dict[str, int | str]:
    """Persist today's UTC sector and market scores without truncating history."""
    snapshot_time = datetime.now(UTC).isoformat(timespec="seconds")
    snapshot_date = snapshot_time[:10]
    df = articles_to_dataframe(records)

    sector_df = sector_metrics(df)
    sector_rows = []
    for row in sector_df.to_dict("records"):
        sector_rows.append(
            {
                "snapshot_date": snapshot_date,
                "snapshot_timestamp": snapshot_time,
                "data_source": data_source,
                "sector": row.get("sector", ""),
                "article_count": int(row.get("article_count", 0) or 0),
                **{metric: round(float(row.get(metric, 0) or 0), 6) for metric in METRIC_COLUMNS},
            }
        )

    market = market_metrics(df)
    market_rows = [
        {
            "snapshot_date": snapshot_date,
            "snapshot_timestamp": snapshot_time,
            "data_source": data_source,
            "article_count": int(len(df)),
            **{metric: round(float(market.get(metric, 0) or 0), 6) for metric in METRIC_COLUMNS},
        }
    ]

    _upsert_rows(
        SECTOR_DAILY_SCORES_PATH,
        SECTOR_SNAPSHOT_FIELDS,
        sector_rows,
        ["snapshot_date", "data_source", "sector"],
    )
    _upsert_rows(
        MARKET_DAILY_SCORES_PATH,
        MARKET_SNAPSHOT_FIELDS,
        market_rows,
        ["snapshot_date", "data_source"],
    )
    return {
        "snapshot_date": snapshot_date,
        "sector_rows": len(sector_rows),
        "market_rows": len(market_rows),
    }


def load_sector_snapshots(data_source: str | None = None) -> pd.DataFrame:
    df = _read_csv(SECTOR_DAILY_SCORES_PATH)
    if df.empty:
        return pd.DataFrame(columns=SECTOR_SNAPSHOT_FIELDS)
    for column in SECTOR_SNAPSHOT_FIELDS:
        if column not in df.columns:
            df[column] = ""
    df = df.reindex(columns=SECTOR_SNAPSHOT_FIELDS)
    if data_source:
        df = df[df["data_source"].astype(str).eq(str(data_source))]
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"], errors="coerce").dt.date
    for column in ["article_count", *METRIC_COLUMNS]:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)
    return df


def load_market_snapshots(data_source: str | None = None) -> pd.DataFrame:
    df = _read_csv(MARKET_DAILY_SCORES_PATH)
    if df.empty:
        return pd.DataFrame(columns=MARKET_SNAPSHOT_FIELDS)
    for column in MARKET_SNAPSHOT_FIELDS:
        if column not in df.columns:
            df[column] = ""
    df = df.reindex(columns=MARKET_SNAPSHOT_FIELDS)
    if data_source:
        df = df[df["data_source"].astype(str).eq(str(data_source))]
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"], errors="coerce").dt.date
    for column in ["article_count", *METRIC_COLUMNS]:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)
    return df
