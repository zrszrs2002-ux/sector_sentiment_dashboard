from pathlib import Path

import pandas as pd

from src.config import (
    DATA_DIR,
    DEMO_PROCESSED_ARTICLES_PATH,
    EXPECTED_ARTICLE_COLUMNS,
    REAL_PROCESSED_ARTICLES_PATH,
)


REAL_DATA_LABEL = "真实新闻"
DEMO_DATA_LABEL = "Demo 数据"


def empty_articles_df() -> pd.DataFrame:
    return pd.DataFrame(columns=EXPECTED_ARTICLE_COLUMNS)


def _read_articles(data_path: Path) -> pd.DataFrame:
    """读取文章数据，并统一处理时间、数值和布尔字段。"""
    df = pd.read_csv(data_path)

    missing_columns = [col for col in EXPECTED_ARTICLE_COLUMNS if col not in df.columns]
    if missing_columns:
        raise ValueError(f"{data_path.name} 缺少字段: {missing_columns}")

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

    df["is_duplicate"] = df["is_duplicate"].astype(str).str.lower().isin(["true", "1", "yes"])
    return df


def load_demo_articles() -> pd.DataFrame:
    """读取原始 demo 新闻数据。"""
    return _read_articles(DATA_DIR / "demo_articles.csv")


def load_processed_articles() -> pd.DataFrame:
    """读取经过 UTC 标准化和去重标记后的新闻数据。"""
    return _read_articles(DEMO_PROCESSED_ARTICLES_PATH)


def load_real_articles() -> pd.DataFrame:
    """读取 RSS 抓取并处理后的真实新闻数据。"""
    if not REAL_PROCESSED_ARTICLES_PATH.exists() or REAL_PROCESSED_ARTICLES_PATH.stat().st_size == 0:
        return empty_articles_df()
    real_df = _read_articles(REAL_PROCESSED_ARTICLES_PATH)
    return real_df


def load_articles(source_mode: str = DEMO_DATA_LABEL, prefer_processed: bool = True) -> pd.DataFrame:
    """页面统一读取入口：根据侧边栏选择加载 demo 或真实新闻。"""
    if source_mode == REAL_DATA_LABEL:
        return load_real_articles()

    if prefer_processed and DEMO_PROCESSED_ARTICLES_PATH.exists() and DEMO_PROCESSED_ARTICLES_PATH.stat().st_size > 0:
        processed_df = load_processed_articles()
        if not processed_df.empty:
            return processed_df
    return load_demo_articles()
