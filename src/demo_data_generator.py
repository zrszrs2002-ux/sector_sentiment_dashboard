"""可复现 demo 新闻数据生成器。

该模块不访问网络，使用固定模板生成 132 条过去 30 天内的财经新闻样本，
覆盖 11 个 GICS 风格板块。生成后会调用文章处理流水线，产出
`data/demo_articles.csv` 和带规则标签的 `data/processed_articles.csv`。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.article_pipeline import process_articles
from src.config import DATA_DIR, EXPECTED_ARTICLE_COLUMNS, RISK_SEVERITY_WEIGHTS
from src.preprocessing import write_article_csv


BASE_TIME = datetime(2026, 7, 7, 0, 0, tzinfo=UTC)

SECTOR_BLUEPRINTS = {
    "Technology": {
        "companies": [("Apple", "AAPL"), ("Microsoft", "MSFT"), ("Nvidia", "NVDA"), ("AMD", "AMD"), ("Broadcom", "AVGO")],
        "topics": ["AI demand", "semiconductors", "cloud growth", "earnings risk"],
        "risks": ["demand risk", "valuation risk", "earnings risk", "macro risk"],
        "signals": [
            ("AI server orders supported stronger guidance", 0.62),
            ("chip supply constraints kept investors cautious", -0.18),
            ("cloud spending trends remained resilient", 0.41),
            ("valuation questions grew after a sharp rally", -0.32),
        ],
    },
    "Communication Services": {
        "companies": [("Meta", "META"), ("Alphabet", "GOOGL"), ("Netflix", "NFLX"), ("AT&T", "T"), ("Verizon", "VZ")],
        "topics": ["advertising growth", "streaming margins", "regulatory risk", "subscriber trends"],
        "risks": ["regulatory risk", "demand risk", "valuation risk", "earnings risk"],
        "signals": [
            ("digital advertising demand improved across large platforms", 0.46),
            ("streaming competition raised questions about margins", -0.16),
            ("subscriber engagement remained stable", 0.28),
            ("policy scrutiny around platform rules increased", -0.34),
        ],
    },
    "Consumer Discretionary": {
        "companies": [("Amazon", "AMZN"), ("Tesla", "TSLA"), ("Nike", "NKE"), ("Home Depot", "HD"), ("McDonald's", "MCD")],
        "topics": ["consumer spending", "earnings risk", "demand risk", "valuation risk"],
        "risks": ["demand risk", "valuation risk", "earnings risk", "macro risk"],
        "signals": [
            ("online sales showed resilient consumer demand", 0.35),
            ("ticket sizes softened as shoppers became selective", -0.24),
            ("restaurant traffic held up better than expected", 0.22),
            ("auto demand concerns weighed on growth expectations", -0.38),
        ],
    },
    "Consumer Staples": {
        "companies": [("Walmart", "WMT"), ("Coca-Cola", "KO"), ("Procter & Gamble", "PG"), ("Costco", "COST")],
        "topics": ["defensive demand", "pricing power", "consumer spending", "margin pressure"],
        "risks": ["macro risk", "demand risk", "earnings risk", "commodity risk"],
        "signals": [
            ("essential goods demand remained steady", 0.31),
            ("input cost pressure limited margin expansion", -0.2),
            ("membership trends supported sales visibility", 0.26),
            ("pricing actions faced more consumer resistance", -0.21),
        ],
    },
    "Financials": {
        "companies": [("JPMorgan", "JPM"), ("Bank of America", "BAC"), ("Citigroup", "C"), ("Goldman Sachs", "GS")],
        "topics": ["credit risk", "interest rate uncertainty", "earnings risk", "liquidity risk"],
        "risks": ["credit risk", "liquidity risk", "interest rate risk", "earnings risk"],
        "signals": [
            ("loan loss reserves remained a central investor focus", -0.42),
            ("net interest income expectations stabilized", 0.19),
            ("capital market activity showed early improvement", 0.27),
            ("credit quality concerns persisted in consumer lending", -0.48),
        ],
    },
    "Healthcare": {
        "companies": [("Pfizer", "PFE"), ("Johnson & Johnson", "JNJ"), ("Merck", "MRK"), ("UnitedHealth", "UNH")],
        "topics": ["healthcare regulation", "drug pipeline", "earnings risk", "policy uncertainty"],
        "risks": ["regulatory risk", "earnings risk", "demand risk", "macro risk"],
        "signals": [
            ("pipeline updates improved confidence in future revenue", 0.33),
            ("drug pricing rules created uncertainty for margins", -0.35),
            ("managed care utilization trends were mixed", -0.14),
            ("clinical trial progress supported sentiment", 0.39),
        ],
    },
    "Industrials": {
        "companies": [("Boeing", "BA"), ("Caterpillar", "CAT"), ("GE", "GE"), ("3M", "MMM")],
        "topics": ["supply chain", "earnings risk", "capital spending", "infrastructure demand"],
        "risks": ["earnings risk", "demand risk", "macro risk", "geopolitical risk"],
        "signals": [
            ("order backlogs remained healthy across machinery names", 0.34),
            ("delivery delays continued to pressure execution", -0.29),
            ("infrastructure demand supported medium-term guidance", 0.31),
            ("export uncertainty weighed on industrial sentiment", -0.26),
        ],
    },
    "Energy": {
        "companies": [("ExxonMobil", "XOM"), ("Chevron", "CVX"), ("ConocoPhillips", "COP")],
        "topics": ["oil price movement", "commodity shock", "cash flow", "geopolitical risk"],
        "risks": ["commodity risk", "geopolitical risk", "earnings risk", "demand risk"],
        "signals": [
            ("higher crude prices improved cash flow expectations", 0.37),
            ("oil price volatility increased uncertainty for margins", -0.27),
            ("capital discipline remained supportive for shareholders", 0.3),
            ("geopolitical supply concerns lifted risk premiums", -0.31),
        ],
    },
    "Utilities": {
        "companies": [("NextEra Energy", "NEE"), ("Duke Energy", "DUK"), ("Southern Company", "SO")],
        "topics": ["interest rate uncertainty", "defensive demand", "renewable investment", "dividend yield"],
        "risks": ["interest rate risk", "regulatory risk", "liquidity risk", "macro risk"],
        "signals": [
            ("lower yield expectations supported dividend sectors", 0.32),
            ("rate case uncertainty remained a regulatory overhang", -0.24),
            ("renewable investment plans supported long-term growth", 0.25),
            ("financing costs remained a watch point", -0.28),
        ],
    },
    "Real Estate": {
        "companies": [("Prologis", "PLD"), ("Simon Property", "SPG"), ("Realty Income", "O")],
        "topics": ["housing market", "refinancing risk", "tenant demand", "interest rate uncertainty"],
        "risks": ["liquidity risk", "interest rate risk", "demand risk", "valuation risk"],
        "signals": [
            ("warehouse demand remained healthier than retail traffic", 0.18),
            ("refinancing costs pressured REIT valuations", -0.43),
            ("leasing activity showed signs of stabilization", 0.16),
            ("higher cap rates weighed on property values", -0.37),
        ],
    },
    "Materials": {
        "companies": [("BHP", "BHP"), ("Freeport-McMoRan", "FCX"), ("Dow", "DOW")],
        "topics": ["commodity shock", "industrial demand", "copper prices", "earnings risk"],
        "risks": ["commodity risk", "demand risk", "macro risk", "earnings risk"],
        "signals": [
            ("copper demand expectations improved with grid investment", 0.29),
            ("chemical margins faced pressure from weak demand", -0.33),
            ("iron ore pricing supported mining cash flows", 0.24),
            ("commodity swings increased earnings uncertainty", -0.3),
        ],
    },
}

SOURCES = [
    "Demo Market Wire",
    "Demo Finance Daily",
    "Demo Sector Brief",
    "Demo Analyst Note",
    "Demo Macro Watch",
]


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def metric_bundle(sentiment: float, risk_category: str, recency_index: int) -> dict[str, str]:
    """根据示例情绪和风险类别生成 demo 六维指标。"""
    severity = RISK_SEVERITY_WEIGHTS.get(risk_category, 3)
    optimism = clamp(50 + sentiment * 45 + (recency_index % 5 - 2) * 1.4)
    fear = clamp(42 - sentiment * 38 + severity * 4 + (recency_index % 4 - 1.5) * 1.2)
    uncertainty = clamp(44 + severity * 5 + abs(sentiment) * 12 + (recency_index % 6))
    attention = clamp(35 + (30 - recency_index) * 1.6 + (recency_index % 7) * 2.2)
    disagreement = clamp(abs(sentiment) * 70 + severity * 5 + (recency_index % 5) * 3)
    risk_intensity = clamp(severity * 17 + max(-sentiment, 0) * 28 + (recency_index % 6) * 2)

    return {
        "sentiment_score": f"{sentiment:.2f}",
        "optimism": f"{optimism:.1f}",
        "fear": f"{fear:.1f}",
        "uncertainty": f"{uncertainty:.1f}",
        "attention_weight": f"{attention:.1f}",
        "disagreement_input": f"{disagreement:.1f}",
        "risk_intensity": f"{risk_intensity:.1f}",
        "model_confidence": f"{clamp(0.62 + abs(sentiment) * 0.3, 0, 0.92):.2f}",
    }


def build_article(sector: str, sector_index: int, item_index: int) -> dict[str, str]:
    blueprint = SECTOR_BLUEPRINTS[sector]
    company, ticker = blueprint["companies"][item_index % len(blueprint["companies"])]
    partner_company, partner_ticker = blueprint["companies"][(item_index + 1) % len(blueprint["companies"])]
    topic = blueprint["topics"][item_index % len(blueprint["topics"])]
    risk_category = blueprint["risks"][item_index % len(blueprint["risks"])]
    signal_text, base_sentiment = blueprint["signals"][item_index % len(blueprint["signals"])]

    duplicate_slot = item_index == 10
    similar_slot = item_index == 11
    day_offset = (sector_index * 3 + item_index * 2) % 30
    hour_offset = (sector_index * 2 + item_index * 3) % 24
    published_at = BASE_TIME - timedelta(days=day_offset, hours=hour_offset)

    article_id = f"demo-{sector_index + 1:02d}-{item_index + 1:02d}"
    source = SOURCES[(sector_index + item_index) % len(SOURCES)]
    title = f"{company} {topic} update {item_index + 1} shapes {sector} sentiment"
    url = f"https://example.com/{article_id}"

    if duplicate_slot:
        title = f"{company} {topic} update {item_index + 1} shapes {sector} sentiment"
        url = f"https://example.com/demo-{sector_index + 1:02d}-01"
    elif similar_slot:
        reference_company, _ = blueprint["companies"][0]
        reference_topic = blueprint["topics"][0]
        title = f"{reference_company} {reference_topic} update 1 reshapes {sector} sentiment"

    sentiment_adjustment = ((item_index % 5) - 2) * 0.04
    sentiment = max(-0.75, min(0.75, base_sentiment + sentiment_adjustment))
    metrics = metric_bundle(sentiment, risk_category, day_offset)

    summary = f"{signal_text}. Investors linked the move to {topic}."
    content = (
        f"{company} and {partner_company} were mentioned in demo coverage of {sector}. "
        f"{signal_text}. Analysts said {risk_category} should be monitored over the next few weeks."
    )

    record = {
        "article_id": article_id,
        "source": source,
        "title": title,
        "summary": summary,
        "content": content,
        "url": url,
        "published_at": published_at.isoformat(timespec="seconds"),
        "collected_at": BASE_TIME.isoformat(timespec="seconds"),
        "language": "en",
        "tickers": f"{ticker};{partner_ticker}",
        "companies": f"{company};{partner_company}",
        "sector": sector,
        "topic": topic,
        "risk_category": risk_category,
        "evidence_sentence": signal_text,
        "is_duplicate": "False",
        "dedup_factor": "1.0",
    }
    record.update(metrics)
    return {column: record.get(column, "") for column in EXPECTED_ARTICLE_COLUMNS}


def generate_demo_records() -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for sector_index, sector in enumerate(SECTOR_BLUEPRINTS):
        for item_index in range(12):
            records.append(build_article(sector, sector_index, item_index))
    return records


def write_raw_demo(path: Path, records: list[dict[str, str]]) -> None:
    write_article_csv(path, records)


def main() -> None:
    demo_path = DATA_DIR / "demo_articles.csv"
    processed_path = DATA_DIR / "processed_articles.csv"
    records = generate_demo_records()
    write_raw_demo(demo_path, records)
    processed = process_articles(demo_path, processed_path)
    print(f"Generated demo data: {len(records)} records")
    print(f"Generated processed data: {len(processed)} records")


if __name__ == "__main__":
    main()
