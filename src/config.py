from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DICTIONARY_DIR = DATA_DIR / "dictionaries"
DEMO_PROCESSED_ARTICLES_PATH = DATA_DIR / "processed_articles.csv"
RAW_ARTICLES_PATH = DATA_DIR / "raw_articles.csv"
REAL_PROCESSED_ARTICLES_PATH = DATA_DIR / "real_processed_articles.csv"

DISCLAIMER = "本系统仅用于教育和研究演示，不构成投资建议。"

SECTORS = [
    "Technology",
    "Communication Services",
    "Consumer Discretionary",
    "Consumer Staples",
    "Financials",
    "Healthcare",
    "Industrials",
    "Energy",
    "Utilities",
    "Real Estate",
    "Materials",
]

METRIC_COLUMNS = [
    "optimism",
    "fear",
    "uncertainty",
    "attention",
    "disagreement",
    "risk_intensity",
]

METRIC_LABELS = {
    "optimism": "乐观度",
    "fear": "恐惧度",
    "uncertainty": "不确定性",
    "attention": "关注度",
    "disagreement": "分歧度",
    "risk_intensity": "风险强度",
}

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
    "p_positive",
    "p_neutral",
    "p_negative",
    "optimism",
    "fear",
    "uncertainty",
    "attention",
    "attention_weight",
    "disagreement",
    "disagreement_input",
    "risk_intensity",
    "risk_category",
    "evidence_sentence",
    "model_confidence",
    "relevance_weight",
    "time_weight",
    "agg_weight",
    "is_duplicate",
    "dedup_factor",
]

# TODO: 第二阶段计划用人工标注数据对这些权重做校准和敏感性分析，当前为专家先验设定的 baseline 值
TIME_DECAY_TAU_HOURS = 72
# TODO: 当前 Attention 使用跨板块横截面近似：在近 7 天窗口内按板块加权新闻量排名分位数计算。
# TODO: 等真实新闻积累出 30 天以上历史后，应切换为每个板块新闻量相对自身历史分布的 ECDF 分位数。
# TODO: 这样可避免跨板块直接比较新闻量时低估 Utilities、Materials 等天然新闻较少的板块。
ATTENTION_WINDOW_DAYS = 7
UNCERTAINTY_NEUTRAL_WEIGHT = 0.6
UNCERTAINTY_ENTROPY_WEIGHT = 0.4
RISK_AVG_WEIGHT = 0.7
RISK_P90_WEIGHT = 0.3

RELEVANCE_WEIGHTS = {
    "company_or_ticker": 1.0,
    "topic_only": 0.7,
}

DEFAULT_DEDUP_FACTORS = {
    "unique": 1.0,
    "similar_reprint": 0.7,
    "duplicate": 0.3,
}

RISK_SEVERITY_WEIGHTS = {
    "liquidity risk": 5,
    "credit risk": 5,
    "macro risk": 4,
    "regulatory risk": 4,
    "geopolitical risk": 4,
    "interest rate risk": 3,
    "earnings risk": 3,
    "commodity risk": 3,
    "demand risk": 3,
    "valuation risk": 2,
}
