from src.config import DISCLAIMER, METRIC_LABELS


def generate_market_brief(market_scores: dict[str, float], top_sector: str, risk_sector: str) -> str:
    """没有 LLM API 时使用规则模板生成中文市场摘要。"""
    optimism = market_scores.get("optimism", 0)
    fear = market_scores.get("fear", 0)
    risk = market_scores.get("risk_intensity", 0)

    if risk >= 65 or fear >= 55:
        tone = "偏紧张"
    elif optimism >= 55 and fear < 45:
        tone = "偏乐观"
    else:
        tone = "偏谨慎"

    return (
        f"当前 demo 市场舆情整体{tone}。"
        f"乐观度较高的板块是 {top_sector}，风险强度较高的板块是 {risk_sector}。"
        f"市场级{METRIC_LABELS['optimism']}为 {optimism:.1f}，"
        f"{METRIC_LABELS['fear']}为 {fear:.1f}，"
        f"{METRIC_LABELS['risk_intensity']}为 {risk:.1f}。"
        f"{DISCLAIMER}"
    )
