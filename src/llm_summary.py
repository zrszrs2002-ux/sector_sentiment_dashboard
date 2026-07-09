from __future__ import annotations

import json
import os
from typing import Any

from src.config import DISCLAIMER, LLM_ENABLED, LLM_MODEL_BRIEF, LLM_TIMEOUT_SECONDS, METRIC_LABELS


def generate_market_brief(
    market_scores: dict[str, float],
    top_sector: str,
    risk_sector: str,
    macro_count: int = 0,
    macro_title: str = "",
) -> str:
    """Rule fallback kept for older page code and quick smoke checks."""
    optimism = float(market_scores.get("optimism", 0) or 0)
    fear = float(market_scores.get("fear", 0) or 0)
    risk = float(market_scores.get("risk_intensity", 0) or 0)

    if risk >= 65 or fear >= 55:
        tone = "偏谨慎"
    elif optimism >= 55 and fear < 45:
        tone = "偏乐观"
    else:
        tone = "偏中性"

    macro_sentence = ""
    if macro_count:
        macro_sentence = f"另有 {macro_count} 条未映射宏观/市场级新闻进入观察。"
        if macro_title:
            macro_sentence += f"代表新闻：{macro_title}。"

    return (
        f"当前市场舆情整体{tone}。"
        f"乐观度较高的板块是 {top_sector}，风险强度较高的板块是 {risk_sector}。"
        f"市场级{METRIC_LABELS['optimism']}为 {optimism:.1f}，"
        f"{METRIC_LABELS['fear']}为 {fear:.1f}，"
        f"{METRIC_LABELS['risk_intensity']}为 {risk:.1f}。"
        f"{macro_sentence}"
        f"{DISCLAIMER}"
    )


def _top_sector(payload: dict[str, Any], metric: str) -> str:
    rows = payload.get("sectors", {}).get("rankings", {}).get(metric, [])
    return rows[0]["sector"] if rows else "暂无"


def _delta_sentence(deltas: dict[str, Any]) -> tuple[str, bool]:
    parts: list[str] = []
    for metric in ["optimism", "fear", "risk_intensity"]:
        value = deltas.get(metric)
        if value is None:
            continue
        parts.append(f"{METRIC_LABELS[metric]}较前一日{float(value):+.1f}")
    if not parts:
        return "", False
    return "；".join(parts) + "。", True


def _mover_sentence(payload: dict[str, Any]) -> str:
    movers = payload.get("sectors", {}).get("movers", [])
    if not movers:
        return ""
    names = [str(item.get("sector", "")) for item in movers[:3] if item.get("sector")]
    return f"异动幅度较大的板块包括 {'、'.join(names)}。" if names else ""


def generate_rule_brief_from_payload(payload: dict[str, Any]) -> str:
    scores = payload.get("market", {}).get("scores", {})
    deltas = payload.get("market", {}).get("delta_vs_previous_day", {})
    top_optimism = _top_sector(payload, "optimism")
    top_risk = _top_sector(payload, "risk_intensity")
    drivers = payload.get("top_drivers", [])
    risks = payload.get("risk_distribution_top5", {})
    coverage = payload.get("coverage", {})
    delta_text, has_delta = _delta_sentence(deltas)

    source_count = coverage.get("source_count", 0)
    coverage_note = f"数据覆盖：{coverage.get('article_count', 0)} 条新闻、{source_count} 个来源。"
    if not has_delta:
        coverage_note += "暂无前一日对比基准，异动对比将于明日起可用。"

    driver_lines = [
        f"- {item.get('title', '')}：{item.get('driver_reason', '')}"
        for item in drivers[:5]
        if item.get("title")
    ]
    risk_text = "、".join(f"{key} {value} 条" for key, value in risks.items()) or "暂无明显集中类别"
    mover_text = _mover_sentence(payload)

    return (
        "### 1) 今日市场概况\n"
        f"过去 24 小时市场乐观度 {float(scores.get('optimism', 0) or 0):.1f}，"
        f"恐惧度 {float(scores.get('fear', 0) or 0):.1f}，"
        f"风险强度 {float(scores.get('risk_intensity', 0) or 0):.1f}。"
        f"{delta_text}{coverage_note}\n\n"
        "### 2) 板块亮点与异动\n"
        f"乐观度排名靠前的是 {top_optimism}，风险强度排名靠前的是 {top_risk}。"
        f"{mover_text}\n\n"
        "### 3) 主要驱动事件解读\n"
        + ("\n".join(driver_lines) if driver_lines else "暂无足够新闻形成驱动事件。")
        + "\n\n### 4) 风险提示\n"
        f"风险类别分布 Top 5：{risk_text}。RSS 只覆盖近期新闻，短期趋势可能较稀疏。\n\n"
        "### 5) 免责声明\n"
        f"{DISCLAIMER}"
    )


def _system_prompt() -> str:
    return (
        "你是金融舆情分析助手，为板块舆情监测系统撰写每日中文简报。"
        "你必须严格基于用户提供的数据 JSON 写作；每个论断都要对应数据中的具体新闻标题或指标数值。"
        "数据中没有的信息一律不得提及；不要预测价格，不要给出买卖或持仓建议。"
        "输出 Markdown，结构必须为：1) 今日市场概况（2-3句，含与昨日变化；若 JSON 中前一日差值为 null，则说明暂无对比基准）"
        "2) 板块亮点与异动 3) 主要驱动事件解读（叙事化，引用新闻标题）"
        "4) 风险提示 5) 结尾附 config 中的免责声明。"
        "篇幅 300-500 字，语言平实专业，不使用夸张形容词。"
    )


def _resolve_brief_model(client: Any) -> str:
    """Return only a model ID confirmed by the authenticated OpenAI account."""
    models = client.models.list()
    available_ids = {
        str(model.id)
        for model in getattr(models, "data", [])
        if getattr(model, "id", None)
    }
    if LLM_MODEL_BRIEF in available_ids:
        return LLM_MODEL_BRIEF

    model_family = LLM_MODEL_BRIEF.rsplit("-", 1)[0]
    family_ids = sorted(model_id for model_id in available_ids if model_id.startswith(model_family))
    preview = ", ".join(family_ids) if family_ids else f"无可用 {model_family} 模型"
    raise RuntimeError(
        f"简报模型 {LLM_MODEL_BRIEF!r} 不在当前 OpenAI 账户的模型列表中（{preview}）。"
        "请根据 API 返回的实际模型 ID 更新 LLM_MODEL_BRIEF。"
    )


def generate_llm_brief(payload: dict[str, Any]) -> dict[str, str]:
    if not LLM_ENABLED:
        return {"source": "规则模板", "content": generate_rule_brief_from_payload(payload), "error": "LLM_ENABLED=False"}

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("未检测到 OPENAI_API_KEY，已回退到规则模板简报。")
        return {"source": "规则模板", "content": generate_rule_brief_from_payload(payload), "error": "missing_api_key"}

    try:
        from openai import OpenAI
    except ImportError as exc:
        print(f"OpenAI SDK 不可用，已回退到规则模板简报：{exc}")
        return {"source": "规则模板", "content": generate_rule_brief_from_payload(payload), "error": str(exc)}

    try:
        client = OpenAI(api_key=api_key, timeout=LLM_TIMEOUT_SECONDS)
        model_id = _resolve_brief_model(client)
        response = client.responses.create(
            model=model_id,
            max_output_tokens=1200,
            instructions=_system_prompt(),
            input=(
                "请只基于以下 JSON 数据生成每日市场简报。"
                f"免责声明必须原文附在结尾：{DISCLAIMER}\n\n"
                f"{json.dumps(payload, ensure_ascii=False, default=str)}"
            ),
        )
        content = str(getattr(response, "output_text", "") or "").strip()
        if not content:
            raise RuntimeError("LLM 返回内容为空")
        if DISCLAIMER not in content:
            content = f"{content}\n\n### 5) 免责声明\n{DISCLAIMER}"
        return {"source": "AI 生成", "content": content, "error": ""}
    except Exception as exc:  # noqa: BLE001 - 外部 API 不应中断管线
        print(f"LLM 简报调用失败，已回退到规则模板：{exc}")
        return {"source": "规则模板", "content": generate_rule_brief_from_payload(payload), "error": str(exc)}
