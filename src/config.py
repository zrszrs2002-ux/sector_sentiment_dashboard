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
EVALUATION_DIR = DATA_DIR / "evaluation"
ANNOTATION_BLIND_PATH = ANNOTATION_DIR / "annotation_blind.csv"
ANNOTATION_KEY_PATH = ANNOTATION_DIR / "annotation_key.csv"
ANNOTATION_META_PATH = ANNOTATION_DIR / "annotation_meta.json"
ANNOTATION_ERRORS_PATH = ANNOTATION_DIR / "sentiment_errors.csv"
SENSITIVITY_ANALYSIS_PATH = EVALUATION_DIR / "sensitivity_analysis.csv"
ANNOTATION_GUIDE_PATH = PROJECT_ROOT / "docs" / "annotation_guide.md"
SECTOR_DAILY_SCORES_PATH = DATA_DIR / "sector_daily_scores.csv"
MARKET_DAILY_SCORES_PATH = DATA_DIR / "market_daily_scores.csv"
LATEST_BRIEF_PATH = DATA_DIR / "latest_brief.md"
BRIEF_ARCHIVE_DIR = DATA_DIR / "briefs"
FULLTEXT_CACHE_PATH = DATA_DIR / "fulltext_cache.json"
CSV_EXPORT_ENCODING = "utf-8-sig"
BACKUP_RETENTION_COUNT = 10
WORKING_SET_DAYS = 30
# Market Overview Top Drivers start with the past 48 hours and expand to 72/168 hours if too few events are found.
DRIVER_WINDOW_HOURS = 48
DRIVER_MIN_EVENTS = 5
RAW_SQLITE_WARNING_MB = 50
ANNOTATION_SAMPLE_SIZE = 300
# A fixed seed makes annotation sampling reproducible; change it explicitly only when a new sample is required.
ANNOTATION_SAMPLE_SEED = 5720
# Backward-compatible alias for existing local callers.
ANNOTATION_RANDOM_SEED = ANNOTATION_SAMPLE_SEED
CALIBRATION_BIN_COUNT = 10

DISCLAIMER = (
    "This system automatically analyzes market sentiment based on public financial news. "
    "Results are for research reference only and do not constitute investment advice. "
    "Investing involves risk; please make independent decisions."
)

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
# TODO: RSS source_weight is currently a source-type prior; calibrate it after human annotation and error analysis.
# content_level/rescored will support the Sprint 2 comparison of summary-based and full-text signals.

# Averaging all sentences can dilute long texts toward neutral. Formal scores therefore use summaries for comparability.
# Full-text scores are retained for a later decision based on Phase 2 annotation data.
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
    "optimism": "Optimism",
    "fear": "Fear",
    "uncertainty": "Uncertainty",
    "attention": "Attention",
    "disagreement": "Disagreement",
    "risk_intensity": "Risk Intensity",
}

FORMULA_VERSION_BASELINE = "baseline"
FORMULA_VERSION_ENHANCED = "enhanced"

# Baseline weight group. A one-step rollback requires only ACTIVE_WEIGHTS = BASELINE_WEIGHTS.
# Optimism/Fear use only FinBERT probabilities; Uncertainty uses 0.6 neutral + 0.4 entropy;
# the historical Attention path uses only volume ECDF; Disagreement uses only weighted standard deviation;
# and Risk retains 0.7 mean + 0.3 P90.
BASELINE_WEIGHTS = {
    "optimism": {"p_positive": 1.0, "b_bull": 0.0, "g_growth": 0.0},
    "fear": {"p_negative": 1.0, "b_bear": 0.0, "s_shock": 0.0},
    "uncertainty": {"p_neutral": 0.6, "entropy_norm": 0.4, "k_unc": 0.0},
    "attention": {"volume_ecdf": 1.0, "growth_ecdf": 0.0},
    "disagreement": {"weighted_std": 1.0, "polarity_mix": 0.0},
    "risk_intensity": {"weighted_mean": 0.7, "p90": 0.3},
}

# Initial Enhanced weights are expert priors. src/sensitivity_analysis.py performs weight sensitivity analysis;
# calibration against human annotations is conducted separately.
ENHANCED_WEIGHTS = {
    "optimism": {"p_positive": 0.7, "b_bull": 0.2, "g_growth": 0.1},
    "fear": {"p_negative": 0.7, "b_bear": 0.2, "s_shock": 0.1},
    "uncertainty": {"p_neutral": 0.4, "entropy_norm": 0.3, "k_unc": 0.3},
    "attention": {"volume_ecdf": 0.7, "growth_ecdf": 0.3},
    "disagreement": {"weighted_std": 0.5, "polarity_mix": 0.5},
    "risk_intensity": {"weighted_mean": 0.7, "p90": 0.3},
}

SENSITIVITY_PERTURBATION_FACTORS = (0.0, 0.5, 0.8, 1.2, 1.5)
SENSITIVITY_TOP_K = 3

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

# TODO: Phase 2 will use human annotations to calibrate and analyze these expert-prior baseline values.
TIME_DECAY_TAU_HOURS = 72
# TODO: Attention currently uses a cross-sector approximation: rank percentiles of weighted sector news volume
# over the latest seven-day window.
# TODO: After at least 30 days of real-news history accumulate, switch to each sector's news-volume ECDF
# percentile relative to its own history.
# TODO: This avoids understating naturally low-coverage sectors such as Utilities and Materials.
ATTENTION_WINDOW_DAYS = 7
ATTENTION_MIN_HISTORY_DAYS = 30
ATTENTION_GROWTH_LOOKBACK_DAYS = 7
KEYWORD_SENTENCE_SCORE_MULTIPLIER = 3.0
# Fear is technically limited to downside/risk-off pressure: S_shock uses panic-reaction terms and no longer
# double-counts event risks such as defaults, investigations, or recessions.
# Risk Intensity independently captures event-risk severity.
# TODO: The pairwise-distance normalization coefficient is a first-version prior requiring annotation calibration.
DISAGREEMENT_METHOD = "pairwise_distance"  # Use "legacy_std_mix" for ablation.
DISAGREEMENT_PAIRWISE_NORMALIZATION = 2.0
# Used only by legacy_std_mix; the default formula has no sentiment-polarity threshold.
DISAGREEMENT_POLARITY_THRESHOLD = 0.15

# TODO: Risk-density and severity coefficients are expert priors requiring human-annotation calibration in Sprint 2.
# Per-category risk intensity: r_k = min(matched sentences / total sentences * 3, 1).
RISK_KEYWORD_SENTENCE_SCORE_MULTIPLIER = 3.0
RISK_SEVERITY_SCALE_MAX = 5.0
# Bounded risk combination: noisy_or avoids premature saturation from linear multi-label addition;
# sum remains available for legacy ablation.
RISK_COMBINE = "noisy_or"  # "sum"

# Sentiment/uncertainty pressure is disabled by default to avoid coupling Risk Intensity with Fear/Uncertainty.
# Enabling it restores the early baseline: risk-label severity + negative-sentiment pressure + uncertainty pressure.
RISK_USE_SENTIMENT_PRESSURE = False
RISK_SENTIMENT_SEVERITY_WEIGHT = 0.75
RISK_NEGATIVE_PRESSURE_WEIGHT = 35
RISK_UNCERTAINTY_PRESSURE_WEIGHT = 10

# By default, FinBERT first checks the local cache for the pinned revision and downloads only on a cache miss;
# explicit offline mode reads the cache only.
SENTIMENT_ENGINE = "finbert"
SENTIMENT_DEVICE = "auto"
FINBERT_MODEL_NAME = "ProsusAI/finbert"
FINBERT_REVISION = "4556d13015211d73dccd3fdd39d39232506f3e43"
FINBERT_MAX_LENGTH = 128

# Event clustering affects collapsed display only; it does not change dedup_factor, agg_weight,
# or six-dimensional aggregation.
# Independent reports continue contributing to Attention and sentiment. Whether to downweight articles within
# a cluster will be evaluated with annotation data in Sprint 2.
EVENT_TIME_WINDOW_HOURS = 48
EVENT_MAX_SPAN_HOURS = 72
# TODO: The polarity-guard threshold is a first-version prior requiring event-pair annotation for split/merge errors.
EVENT_POLARITY_GUARD_THRESHOLD = 0.30
EVENT_SIMILARITY_ENGINE = "embedding"
EVENT_EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
# TODO: The following event-similarity thresholds are first-version priors to be calibrated with annotated
# event pairs in Sprint 2.
EVENT_EMBED_THRESHOLD = 0.72
EVENT_LEXICAL_THRESHOLD = 0.40
# Unmapped news without a ticker lacks entity constraints and therefore uses stricter text thresholds.
EVENT_UNMAPPED_EMBED_THRESHOLD = 0.82
EVENT_UNMAPPED_LEXICAL_THRESHOLD = 0.55
# TODO: The coverage boost also requires calibration with Top Drivers annotation data; 15% is a conservative prior.
EVENT_COVERAGE_BOOST = 1.15
EVENT_EMBED_BATCH_SIZE = 64

# Semantic revision of the data pipeline, used to explain formula/label discontinuities in daily snapshot trends.
PIPELINE_REVISION = "r4"

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
