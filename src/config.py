import os
from pathlib import Path


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def get_finbert_loading_mode() -> str:
    value = os.getenv("FINBERT_LOCAL_FILES_ONLY", "auto").strip().lower()
    return "offline" if value in {"1", "true", "yes", "on"} else "auto"


def get_finbert_batch_size() -> int:
    return _env_int("FINBERT_BATCH_SIZE", 32)


def get_demo_pin() -> str:
    return os.getenv("DEMO_PIN", "").strip()


def get_hf_token() -> str:
    return os.getenv("HF_TOKEN", "").strip()


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DICTIONARY_DIR = DATA_DIR / "dictionaries"
RSS_SOURCES_PATH = DATA_DIR / "rss_sources.json"
DEMO_PROCESSED_ARTICLES_PATH = DATA_DIR / "processed_articles.csv"
RAW_ARTICLES_PATH = DATA_DIR / "raw_articles.csv"
REAL_PROCESSED_ARTICLES_PATH = DATA_DIR / "real_processed_articles.csv"
ERROR_RECORDS_PATH = DATA_DIR / "error_records.csv"
ANNOTATION_DIR = DATA_DIR / "annotation"
ANNOTATION_BLIND_PATH = ANNOTATION_DIR / "annotation_blind.csv"
ANNOTATION_KEY_PATH = ANNOTATION_DIR / "annotation_key.csv"
ANNOTATION_ERRORS_PATH = ANNOTATION_DIR / "sentiment_errors.csv"
ANNOTATION_GUIDE_PATH = PROJECT_ROOT / "docs" / "annotation_guide.md"
SECTOR_DAILY_SCORES_PATH = DATA_DIR / "sector_daily_scores.csv"
MARKET_DAILY_SCORES_PATH = DATA_DIR / "market_daily_scores.csv"
LATEST_BRIEF_PATH = DATA_DIR / "latest_brief.md"
BRIEF_ARCHIVE_DIR = DATA_DIR / "briefs"
FULLTEXT_CACHE_PATH = DATA_DIR / "fulltext_cache.json"
CSV_EXPORT_ENCODING = "utf-8-sig"
BACKUP_RETENTION_COUNT = 10
WORKING_SET_DAYS = 30
RAW_SQLITE_WARNING_MB = 50
ANNOTATION_SAMPLE_SIZE = 300
# 固定种子使标注抽样可复现；需要新的样本时再显式更改此配置。
ANNOTATION_SAMPLE_SEED = 5720
# Backward-compatible alias for existing local callers.
ANNOTATION_RANDOM_SEED = ANNOTATION_SAMPLE_SEED
CALIBRATION_BIN_COUNT = 10

DISCLAIMER = "本系统基于公开财经新闻自动分析市场舆情，结果仅供研究参考，不构成投资建议。投资有风险，决策需独立判断。"

RSS_USER_AGENT = (
    "SectorSentimentDashboard/0.2 "
    "(practical research tool; contact: local-user; RSS title-summary-url only)"
)
RSS_REQUEST_TIMEOUT_SECONDS = 12
FULLTEXT_MAX_PER_RUN = 30
FULLTEXT_DRIVER_CANDIDATE_COUNT = 10
FULLTEXT_REQUEST_TIMEOUT_SECONDS = 10
FULLTEXT_RATE_LIMIT_SECONDS = 1.0
FULLTEXT_MIN_CHARS = 200
# TODO: RSS source_weight 当前为来源类型先验；待人工标注和误差分析后校准。
# content_level/rescored 将用于第二冲刺“摘要版 vs 正文版”信号对比评估。

# 全句平均对长文本存在中性稀释，正式分数统一用摘要口径保证可比性；
# 正文口径留档待第二阶段标注数据裁决。
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

FORMULA_VERSION_BASELINE = "baseline"
FORMULA_VERSION_ENHANCED = "enhanced"

# Baseline 权重组，一键回退时只需改为 ACTIVE_WEIGHTS = BASELINE_WEIGHTS。
# Optimism/Fear 仅使用 FinBERT 概率；Uncertainty 使用 0.6 neutral + 0.4 entropy；
# Attention 历史路径仅用新闻量 ECDF；Disagreement 仅用加权标准差；Risk 保持 0.7 mean + 0.3 P90。
BASELINE_WEIGHTS = {
    "optimism": {"p_positive": 1.0, "b_bull": 0.0, "g_growth": 0.0},
    "fear": {"p_negative": 1.0, "b_bear": 0.0, "s_shock": 0.0},
    "uncertainty": {"p_neutral": 0.6, "entropy_norm": 0.4, "k_unc": 0.0},
    "attention": {"volume_ecdf": 1.0, "growth_ecdf": 0.0},
    "disagreement": {"weighted_std": 1.0, "polarity_mix": 0.0},
    "risk_intensity": {"weighted_mean": 0.7, "p90": 0.3},
}

# Enhanced 初始权重均为专家先验；TODO: 第二冲刺用标注数据做消融与敏感性校准。
ENHANCED_WEIGHTS = {
    "optimism": {"p_positive": 0.7, "b_bull": 0.2, "g_growth": 0.1},
    "fear": {"p_negative": 0.7, "b_bear": 0.2, "s_shock": 0.1},
    "uncertainty": {"p_neutral": 0.4, "entropy_norm": 0.3, "k_unc": 0.3},
    "attention": {"volume_ecdf": 0.7, "growth_ecdf": 0.3},
    "disagreement": {"weighted_std": 0.5, "polarity_mix": 0.5},
    "risk_intensity": {"weighted_mean": 0.7, "p90": 0.3},
}

ACTIVE_WEIGHTS = ENHANCED_WEIGHTS
ACTIVE_FORMULA_VERSION = (
    FORMULA_VERSION_BASELINE
    if ACTIVE_WEIGHTS is BASELINE_WEIGHTS
    else FORMULA_VERSION_ENHANCED
)

FORMULA_COMPONENT_COLUMNS = [
    "b_bull",
    "b_bear",
    "g_growth",
    "s_shock",
    "k_unc",
    "entropy_norm",
]

FULLTEXT_SENTIMENT_COLUMNS = [
    "sentiment_score_fulltext",
    "p_positive_fulltext",
    "p_neutral_fulltext",
    "p_negative_fulltext",
]

EXPECTED_ARTICLE_COLUMNS = [
    "article_id",

    "event_id",
    "source",
    "publisher",
    "source_count",
    "title",
    "summary",
    "content",
    "body_text",
    "content_level",
    "rescored",
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
    *FULLTEXT_SENTIMENT_COLUMNS,
    *FORMULA_COMPONENT_COLUMNS,
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
    "source_weight",
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
ATTENTION_MIN_HISTORY_DAYS = 30
ATTENTION_GROWTH_LOOKBACK_DAYS = 7
KEYWORD_SENTENCE_SCORE_MULTIPLIER = 3.0
DISAGREEMENT_POLARITY_THRESHOLD = 0.15

# TODO: 风险密度与严重度系数均为专家先验，第二冲刺需用人工标注校准。
# 每类风险强度 r_k = min(命中句子数 / 总句子数 * 3, 1)。
RISK_KEYWORD_SENTENCE_SCORE_MULTIPLIER = 3.0
RISK_SEVERITY_SCALE_MAX = 5.0

# 默认关闭情绪/不确定性压力项，避免 Risk Intensity 与 Fear/Uncertainty 维度耦合。
# 打开后会回到早期 baseline：风险标签严重度 + 负向情绪压力 + 不确定性压力。
RISK_USE_SENTIMENT_PRESSURE = False
RISK_SENTIMENT_SEVERITY_WEIGHT = 0.75
RISK_NEGATIVE_PRESSURE_WEIGHT = 35
RISK_UNCERTAINTY_PRESSURE_WEIGHT = 10

# FinBERT 默认先读固定 revision 的本地缓存，未命中时自动下载；显式离线时只读缓存。
SENTIMENT_ENGINE = "finbert"
SENTIMENT_DEVICE = "auto"
FINBERT_MODEL_NAME = "ProsusAI/finbert"
FINBERT_REVISION = "4556d13015211d73dccd3fdd39d39232506f3e43"
FINBERT_MAX_LENGTH = 128

# 事件聚类只折叠展示，不修改 dedup_factor、agg_weight 或六维指标聚合。
# 独立报道继续贡献 Attention/情绪；是否对簇内文章降权留到第二冲刺用标注数据评估。
EVENT_TIME_WINDOW_HOURS = 48
EVENT_MAX_SPAN_HOURS = 72
# TODO: 极性护栏阈值为首版先验，需结合事件对标注检查误拆与误合并。
EVENT_POLARITY_GUARD_THRESHOLD = 0.30
EVENT_SIMILARITY_ENGINE = "embedding"
EVENT_EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
# TODO: 以下事件相似度阈值是首版先验值，待第二冲刺用人工标注事件对校准。
EVENT_EMBED_THRESHOLD = 0.72
EVENT_LEXICAL_THRESHOLD = 0.40
# 无 ticker 的 Unmapped 新闻缺少实体约束，因此采用更严格的文本阈值。
EVENT_UNMAPPED_EMBED_THRESHOLD = 0.82
EVENT_UNMAPPED_LEXICAL_THRESHOLD = 0.55
# TODO: 媒体覆盖加成同样需要用 Top Drivers 标注数据校准，当前取保守的 15%。
EVENT_COVERAGE_BOOST = 1.15
EVENT_EMBED_BATCH_SIZE = 64

# 数据管线语义修订号；用于解释每日快照趋势中的公式/标签断点。
PIPELINE_REVISION = "r3"

LLM_ENABLED = True
# The runtime attempts candidates in order; models.list is logging context only.
LLM_MODEL_BRIEF_CANDIDATES = ["gpt-5.6-terra", "gpt-5.5"]
LLM_CANDIDATE_RATE_LIMIT_RETRY_SECONDS = 5
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
