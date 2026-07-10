import os
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DICTIONARY_DIR = DATA_DIR / "dictionaries"
DEMO_PROCESSED_ARTICLES_PATH = DATA_DIR / "processed_articles.csv"
RAW_ARTICLES_PATH = DATA_DIR / "raw_articles.csv"
REAL_PROCESSED_ARTICLES_PATH = DATA_DIR / "real_processed_articles.csv"
ERROR_RECORDS_PATH = DATA_DIR / "error_records.csv"
SECTOR_DAILY_SCORES_PATH = DATA_DIR / "sector_daily_scores.csv"
MARKET_DAILY_SCORES_PATH = DATA_DIR / "market_daily_scores.csv"
LATEST_BRIEF_PATH = DATA_DIR / "latest_brief.md"
BRIEF_ARCHIVE_DIR = DATA_DIR / "briefs"
CSV_EXPORT_ENCODING = "utf-8-sig"
BACKUP_RETENTION_COUNT = 10
WORKING_SET_DAYS = 30
RAW_SQLITE_WARNING_MB = 50

DISCLAIMER = "本系统基于公开财经新闻自动分析市场舆情，结果仅供研究参考，不构成投资建议。投资有风险，决策需独立判断。"

RSS_USER_AGENT = (
    "SectorSentimentDashboard/0.2 "
    "(practical research tool; contact: local-user; RSS title-summary-url only)"
)
RSS_REQUEST_TIMEOUT_SECONDS = 12
RSS_MAX_ENTRIES_PER_FEED = 20
CNBC_TOP_NEWS_RSS = "https://www.cnbc.com/id/100003114/device/rss/rss.html"
MARKETWATCH_TOP_STORIES_RSS = "https://feeds.marketwatch.com/marketwatch/topstories"
YAHOO_FINANCE_RSS_TEMPLATE = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"

SIMILAR_TITLE_THRESHOLD = 0.9
SIMILAR_PREFIX_TOKEN_COUNT = 5

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
    "time_parse_error",
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
    "processing_error",
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

# 默认关闭情绪/不确定性压力项，避免 Risk Intensity 与 Fear/Uncertainty 维度耦合。
# 打开后会回到早期 baseline：风险标签严重度 + 负向情绪压力 + 不确定性压力。
RISK_USE_SENTIMENT_PRESSURE = False
RISK_SENTIMENT_SEVERITY_WEIGHT = 0.75
RISK_NEGATIVE_PRESSURE_WEIGHT = 35
RISK_UNCERTAINTY_PRESSURE_WEIGHT = 10

# FinBERT 默认只读取本地缓存；模型或依赖不可用时会回退词典模型并给中文提示。
SENTIMENT_ENGINE = "finbert"
SENTIMENT_DEVICE = "auto"
FINBERT_MODEL_NAME = "ProsusAI/finbert"
FINBERT_LOCAL_FILES_ONLY = _env_bool("FINBERT_LOCAL_FILES_ONLY", True)
FINBERT_MAX_LENGTH = 128
FINBERT_BATCH_SIZE = _env_int("FINBERT_BATCH_SIZE", 32)

LLM_ENABLED = True
DEMO_PIN = os.getenv("DEMO_PIN", "").strip()
# The runtime verifies this exact ID through OpenAI's models.list() before
# generation. Switch back to gpt-5.6-terra after the account receives access.
LLM_MODEL_BRIEF = "gpt-5.5"
# Backward-compatible alias for integrations that still import LLM_MODEL.
LLM_MODEL = LLM_MODEL_BRIEF
# Reserved task-specific defaults for the upcoming sector-summary and chat features.
LLM_MODEL_SECTOR_SUMMARY = "gpt-5.6-luna"
LLM_MODEL_CHAT = "gpt-5.6-luna"
LLM_TIMEOUT_SECONDS = 45
BRIEF_GENERATION_HOUR_LOCAL = 8
BRIEF_WINDOW_HOURS = 24

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
