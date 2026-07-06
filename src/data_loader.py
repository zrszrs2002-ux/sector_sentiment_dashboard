import pandas as pd

from src.config import DATA_DIR, METRIC_COLUMNS


EXPECTED_ARTICLE_COLUMNS = [
    "article_id",
    "source",
    "title",
    "summary",
    "content",
    "url",
    "published_at",
    "collected_at",
    "language",
    "tickers",
    "companies",
    "sector",
    "topic",
    "sentiment_score",
    "optimism",
    "fear",
    "uncertainty",
    "attention_weight",
    "disagreement_input",
    "risk_intensity",
    "risk_category",
    "evidence_sentence",
    "model_confidence",
    "is_duplicate",
    "dedup_factor",
]


def load_demo_articles() -> pd.DataFrame:
    """读取第一阶段 demo 新闻数据，并统一处理时间与数值字段。"""
    data_path = DATA_DIR / "demo_articles.csv"
    df = pd.read_csv(data_path)

    missing_columns = [col for col in EXPECTED_ARTICLE_COLUMNS if col not in df.columns]
    if missing_columns:
        raise ValueError(f"demo_articles.csv 缺少字段: {missing_columns}")

    for column in ["published_at", "collected_at"]:
        df[column] = pd.to_datetime(df[column], utc=True, errors="coerce")

    numeric_columns = [
        "sentiment_score",
        "model_confidence",
        "dedup_factor",
        *METRIC_COLUMNS,
    ]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)

    df["is_duplicate"] = df["is_duplicate"].astype(str).str.lower().isin(["true", "1", "yes"])
    return df
