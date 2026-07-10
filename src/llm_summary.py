from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from src.config import (
    DISCLAIMER,
    LLM_CANDIDATE_RATE_LIMIT_RETRY_SECONDS,
    LLM_ENABLED,
    LLM_MODEL_BRIEF_CANDIDATES,
    LLM_TIMEOUT_SECONDS,
    METRIC_LABELS,
)


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
    return """
你是一名资深市场舆情分析师，为同事撰写次日晨读的中文深度简报。

事实与推理边界：
- 只能使用所给数据包中的指标、排名、分布、新闻标题和证据句。每个判断都必须能回溯到其中的具体指标或新闻；不得补充外部事实。
- 不预测价格、涨跌或市场结果，不给出买卖、持仓或操作建议。
- 允许且鼓励三类基于数据包的分析：对指标水平作定性解读；解释新闻事件与对应板块指标之间的合理关联；跨多条新闻归纳共同主题。分析必须写成“基于数据可见”的解释，不能把推断冒充新事实。

数字与语言规范：
- 正文中的数字一律四舍五入为整数。每个数字必须伴随高低判断、排名、前日对比或近 7 日位置等相对语境，禁止裸数字罗列。
- 每个自然段最多出现 4 个阿拉伯数字。写完后必须逐段自检，任何超限段落都要拆分重写。禁止连续使用“X为A、Y为B、Z为C”式罗列句超过一次。
- 正文严禁出现数据包内部字段名或技术词，包括 null、movers、driver_score、snake_case 字段及 JSON。数据不足时使用自然中文，例如“今日暂无对比基准”。
- 指标在正文中只使用中文名称：乐观度、恐惧度、不确定性、关注度、分歧度、风险强度。
- 语言平实、克制、专业，使用完整句子和叙事段落，不使用夸张形容词。

输出为 Markdown，严格使用以下结构：
### ① 核心观点
用 2-3 句开门见山写出今天最值得知道的判断，不先做数据罗列。

### ② 市场全景
至少写成两个自然段，把市场指标、前日变化和近 7 日位置织入解释，每段聚焦一个情绪结构，不得逐项报数。

### ③ 板块与事件深读
本节是全文重心，篇幅应占正文约一半。只选择关注度、风险或情绪最突出的 3-5 个板块展开，每个板块写 2-4 句完整叙述：先判断指标处于什么水平，再引用具体新闻说明驱动，最后解释事件与指标如何相互印证。把正负面新闻和主题分布融入分析，不要把“指标”和“新闻”拆成互不相连的两节；不值得展开的板块一笔带过或不提，禁止为凑数量而罗列。引用关键新闻标题时使用书名号。

### ④ 风险与明日关注点
归纳风险类别、分歧或不确定性集中的原因，并说明下一次新闻更新应继续观察哪些已出现的主题；不得变成市场预测或投资建议。

### ⑤ 数据范围说明与免责声明
自然说明新闻条数、来源数、时间范围、数据源及历史对比是否充足，最后原文附上提供的免责声明。

正文篇幅为 900-1200 个中文字符（免责声明不计入），不得少于 900 字；信息密度优先于修辞。
""".strip()


def _models_list_reference(client: Any) -> str:
    """Return non-blocking account-list context for diagnostics only."""
    try:
        models = client.models.list()
        available_ids = {
            str(model.id)
            for model in getattr(models, "data", [])
            if getattr(model, "id", None)
        }
        states = [
            f"{candidate}={'在清单' if candidate in available_ids else '不在清单'}"
            for candidate in LLM_MODEL_BRIEF_CANDIDATES
        ]
        message = "models.list 参考（非门槛）：" + "，".join(states)
    except Exception as exc:  # noqa: BLE001 - listing must never block generation
        message = f"models.list 参考失败（不影响直接调用）：{_short_error(exc)}"
    print(message)
    return message


def _error_code(exc: Exception) -> str:
    values: list[Any] = [getattr(exc, "code", None), getattr(exc, "type", None)]
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error", body)
        if isinstance(error, dict):
            values.extend([error.get("code"), error.get("type")])
    return " ".join(str(value).lower() for value in values if value)


def _short_error(exc: Exception) -> str:
    status = getattr(exc, "status_code", None)
    code = _error_code(exc)
    message = re.sub(r"\s+", " ", str(exc)).strip()
    details = [f"HTTP {status}" if status else "", code, message]
    return " / ".join(part for part in details if part)[:240]


def _classify_candidate_error(exc: Exception) -> tuple[str, bool]:
    """Return a Chinese category and whether the next candidate should be tried."""
    status = getattr(exc, "status_code", None)
    code = _error_code(exc)
    message = str(exc).lower()
    combined = f"{code} {message}"

    if status == 429 or "rate_limit" in combined or "rate limit" in combined:
        return "429 限流", True
    if status == 403 or any(
        marker in combined
        for marker in ("permission_denied", "insufficient_permissions", "access denied", "not authorized")
    ):
        return "无权限", True
    if status == 404 or any(marker in combined for marker in ("model_not_found", "model not found", "does not exist")):
        return "模型不存在", True
    if status in {500, 502, 503, 504} or any(
        marker in combined
        for marker in ("overloaded", "capacity", "server_error", "temporarily unavailable")
    ):
        return "容量或服务暂不可用", True
    return "其他调用错误", False


def _selection_log(reference: str, events: list[str], final_reason: str) -> str:
    return "；".join([reference, *events, final_reason])


def _attempt_brief_models(client: Any, input_text: str) -> dict[str, Any]:
    reference = _models_list_reference(client)
    events: list[str] = []
    last_error: Exception | None = None

    for candidate_index, model_id in enumerate(LLM_MODEL_BRIEF_CANDIDATES):
        attempt = 1
        retried_first_rate_limit = False
        while True:
            try:
                response = client.responses.create(
                    model=model_id,
                    max_output_tokens=4600,
                    instructions=_system_prompt(),
                    input=input_text,
                )
                event = f"尝试 {model_id} 第 {attempt} 次：成功"
                events.append(event)
                print(event)
                if candidate_index == 0 and attempt == 1:
                    reason = f"最终使用 {model_id}：首选模型直接调用成功"
                elif candidate_index == 0:
                    reason = f"最终使用 {model_id}：首选模型限流等待后重试成功"
                else:
                    reason = f"最终使用 {model_id}：前序候选调用失败后切换成功"
                log = _selection_log(reference, events, reason)
                print(reason)
                return {"response": response, "model_id": model_id, "log": log, "error": ""}
            except Exception as exc:  # noqa: BLE001 - SDK errors vary by version
                last_error = exc
                category, can_switch = _classify_candidate_error(exc)
                event = f"尝试 {model_id} 第 {attempt} 次：失败（{category}，{_short_error(exc)}）"
                events.append(event)
                print(event)

                if candidate_index == 0 and attempt == 1 and category == "429 限流":
                    wait_event = f"等待 {LLM_CANDIDATE_RATE_LIMIT_RETRY_SECONDS} 秒后重试首选模型"
                    events.append(wait_event)
                    print(wait_event)
                    time.sleep(LLM_CANDIDATE_RATE_LIMIT_RETRY_SECONDS)
                    retried_first_rate_limit = True
                    attempt += 1
                    continue

                if can_switch or retried_first_rate_limit:
                    break

                reason = f"最终使用规则模板：{model_id} 发生不适合切换候选的错误"
                log = _selection_log(reference, events, reason)
                print(reason)
                return {"response": None, "model_id": "", "log": log, "error": _short_error(exc)}

    reason = "最终使用规则模板：所有候选模型均调用失败"
    log = _selection_log(reference, events, reason)
    print(reason)
    return {
        "response": None,
        "model_id": "",
        "log": log,
        "error": _short_error(last_error) if last_error else "no_model_candidates",
    }


def _number_count(text: str) -> int:
    return len(re.findall(r"\d+(?:\.\d+)?", text))


def _split_dense_paragraph(paragraph: str, max_numbers: int = 4) -> str:
    paragraph = paragraph.strip()
    if not paragraph or _number_count(paragraph) <= max_numbers:
        return paragraph
    clauses = [part.strip() for part in re.split(r"(?<=[。！？；])", paragraph) if part.strip()]
    if len(clauses) < 2:
        return paragraph

    groups: list[str] = []
    current: list[str] = []
    current_count = 0
    for clause in clauses:
        clause_count = _number_count(clause)
        if current and current_count + clause_count > max_numbers:
            groups.append("".join(current))
            current = [clause]
            current_count = clause_count
        else:
            current.append(clause)
            current_count += clause_count
    if current:
        groups.append("".join(current))
    return "\n\n".join(groups)


def _enforce_llm_paragraph_density(content: str) -> str:
    blocks: list[str] = []
    for raw_block in content.split("\n\n"):
        lines = raw_block.strip().splitlines()
        if not lines:
            continue
        if lines[0].startswith("###"):
            heading = lines[0]
            body = "\n".join(lines[1:]).strip()
            blocks.append(f"{heading}\n{_split_dense_paragraph(body)}" if body else heading)
        else:
            blocks.append(_split_dense_paragraph("\n".join(lines)))
    return "\n\n".join(blocks)


def generate_llm_brief(payload: dict[str, Any]) -> dict[str, str]:
    if not LLM_ENABLED:
        log = "未发起模型请求；最终使用规则模板：LLM_ENABLED=False"
        print(log)
        return {
            "source": "规则模板",
            "content": generate_rule_brief_from_payload(payload),
            "error": "LLM_ENABLED=False",
            "model_id": "",
            "model_selection_log": log,
        }

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        log = "未发起模型请求；最终使用规则模板：未检测到 OPENAI_API_KEY"
        print(log)
        return {
            "source": "规则模板",
            "content": generate_rule_brief_from_payload(payload),
            "error": "missing_api_key",
            "model_id": "",
            "model_selection_log": log,
        }

    try:
        from openai import OpenAI
    except ImportError as exc:
        log = f"未发起模型请求；最终使用规则模板：OpenAI SDK 不可用（{_short_error(exc)}）"
        print(log)
        return {
            "source": "规则模板",
            "content": generate_rule_brief_from_payload(payload),
            "error": _short_error(exc),
            "model_id": "",
            "model_selection_log": log,
        }

    try:
        client = OpenAI(api_key=api_key, timeout=LLM_TIMEOUT_SECONDS)
        attempt_result = _attempt_brief_models(
            client,
            "请只基于以下 JSON 数据生成每日市场简报。"
            f"免责声明必须原文附在结尾：{DISCLAIMER}\n\n"
            f"{json.dumps(payload, ensure_ascii=False, default=str)}",
        )
        response = attempt_result["response"]
        model_id = str(attempt_result["model_id"])
        selection_log = str(attempt_result["log"])
        if response is None:
            return {
                "source": "规则模板",
                "content": generate_rule_brief_from_payload(payload),
                "error": str(attempt_result["error"]),
                "model_id": "",
                "model_selection_log": selection_log,
            }
        content = str(getattr(response, "output_text", "") or "").strip()
        if not content:
            raise RuntimeError("LLM 返回内容为空")
        content = _enforce_llm_paragraph_density(content)
        if DISCLAIMER not in content:
            content = f"{content}\n\n### 5) 免责声明\n{DISCLAIMER}"
        return {
            "source": "AI 生成",
            "content": content,
            "error": "",
            "model_id": model_id,
            "model_selection_log": selection_log,
        }
    except Exception as exc:  # noqa: BLE001 - 外部 API 不应中断管线
        log = locals().get("selection_log", "")
        if log:
            log = f"{log}；最终使用规则模板：模型返回内容处理失败（{_short_error(exc)}）"
        else:
            log = f"未完成候选请求链；最终使用规则模板：{_short_error(exc)}"
        print(f"LLM 简报调用失败，已回退到规则模板：{_short_error(exc)}")
        return {
            "source": "规则模板",
            "content": generate_rule_brief_from_payload(payload),
            "error": _short_error(exc),
            "model_id": "",
            "model_selection_log": log,
        }
