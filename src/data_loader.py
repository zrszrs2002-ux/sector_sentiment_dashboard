from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError, ParserError

from src.config import (
    DATA_DIR,
    DEMO_PROCESSED_ARTICLES_PATH,
    EXPECTED_ARTICLE_COLUMNS,
    FORMULA_COMPONENT_COLUMNS,
    REAL_PROCESSED_ARTICLES_PATH,
    WORKING_SET_DAYS,
)


REAL_DATA_LABEL = "Real news"
DEMO_DATA_LABEL = "Demo data"


def empty_articles_df() -> pd.DataFrame:
    return pd.DataFrame(columns=EXPECTED_ARTICLE_COLUMNS)


def _read_articles(data_path: Path) -> pd.DataFrame:
    """Load article data and normalize timestamp, numeric, and Boolean fields."""
    try:
        df = pd.read_csv(data_path)
    except (FileNotFoundError, OSError, EmptyDataError, ParserError, UnicodeDecodeError):
        return empty_articles_df()

    missing_columns = [col for col in EXPECTED_ARTICLE_COLUMNS if col not in df.columns]
    if missing_columns:
        for column in missing_columns:
            df[column] = ""
    df = df.reindex(columns=EXPECTED_ARTICLE_COLUMNS)

    for column in ["published_at", "collected_at"]:
        df[column] = pd.to_datetime(df[column], utc=True, errors="coerce")

    numeric_columns = [
        "p_positive",
        "p_neutral",
        "p_negative",
        *FORMULA_COMPONENT_COLUMNS,
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
        "source_weight",
        "agg_weight",
        "dedup_factor",
        "source_count",
    ]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)

    df["is_duplicate"] = df["is_duplicate"].astype(str).str.lower().isin(["true", "1", "yes"])
    df["rescored"] = df["rescored"].astype(str).str.lower().isin(["true", "1", "yes"])
    return df


def filter_working_set(df: pd.DataFrame, load_all_history: bool = False) -> pd.DataFrame:
    if load_all_history or df.empty or "published_at" not in df:
        return df
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=WORKING_SET_DAYS)
    return df[df["published_at"].isna() | (df["published_at"] >= cutoff)].copy()


def load_demo_articles(load_all_history: bool = False) -> pd.DataFrame:
    """Load raw demo-news data."""
    return filter_working_set(_read_articles(DATA_DIR / "demo_articles.csv"), load_all_history)


def load_processed_articles(load_all_history: bool = False) -> pd.DataFrame:
    """Load news data after UTC normalization and duplicate marking."""
    return filter_working_set(_read_articles(DEMO_PROCESSED_ARTICLES_PATH), load_all_history)


def load_real_articles(load_all_history: bool = False) -> pd.DataFrame:
    """Load real-news data collected and processed from RSS."""
    if not REAL_PROCESSED_ARTICLES_PATH.exists() or REAL_PROCESSED_ARTICLES_PATH.stat().st_size == 0:
        return empty_articles_df()
    real_df = _read_articles(REAL_PROCESSED_ARTICLES_PATH)
    return filter_working_set(real_df, load_all_history)


def has_real_articles() -> bool:
    """Return whether processed real-news output exists and contains at least one row."""
    if not REAL_PROCESSED_ARTICLES_PATH.exists() or REAL_PROCESSED_ARTICLES_PATH.stat().st_size == 0:
        return False
    try:
        preview = pd.read_csv(REAL_PROCESSED_ARTICLES_PATH, nrows=1)
    except (OSError, EmptyDataError, ParserError, UnicodeDecodeError):
        return False
    return not preview.empty


def load_articles(
    source_mode: str = REAL_DATA_LABEL,
    prefer_processed: bool = True,
    load_all_history: bool = False,
) -> pd.DataFrame:
    """Shared page loader: select demo or real-news data from the sidebar mode."""
    if source_mode == REAL_DATA_LABEL:
        return load_real_articles(load_all_history=load_all_history)

    if prefer_processed and DEMO_PROCESSED_ARTICLES_PATH.exists() and DEMO_PROCESSED_ARTICLES_PATH.stat().st_size > 0:
        processed_df = load_processed_articles(load_all_history=load_all_history)
        if not processed_df.empty:
            return processed_df
    return load_demo_articles(load_all_history=load_all_history)
