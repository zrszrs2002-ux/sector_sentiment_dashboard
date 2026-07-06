from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

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
    "attention_weight",
    "disagreement_input",
    "risk_intensity",
]

METRIC_LABELS = {
    "optimism": "乐观度",
    "fear": "恐惧度",
    "uncertainty": "不确定性",
    "attention_weight": "关注度",
    "disagreement_input": "分歧度",
    "risk_intensity": "风险强度",
}

# TODO: 第二阶段计划用人工标注数据对这些权重做校准和敏感性分析，当前为专家先验设定的 baseline 值
TIME_DECAY_TAU_HOURS = 72
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
