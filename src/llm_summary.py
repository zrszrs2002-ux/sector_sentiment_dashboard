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
        tone = "cautious"
    elif optimism >= 55 and fear < 45:
        tone = "optimistic"
    else:
        tone = "neutral"

    macro_sentence = ""
    if macro_count:
        macro_sentence = f" An additional {macro_count} unmapped macro/market-level news items are being tracked."
        if macro_title:
            macro_sentence += f" Representative headline: {macro_title}."

    return (
        f"Overall market sentiment is currently {tone}. "
        f"The sector with the highest optimism is {top_sector}; the sector with the highest "
        f"risk intensity is {risk_sector}. "
        f"Market-level {METRIC_LABELS['optimism']} is {optimism:.1f}, "
        f"{METRIC_LABELS['fear']} is {fear:.1f}, "
        f"{METRIC_LABELS['risk_intensity']} is {risk:.1f}."
        f"{macro_sentence} "
        f"{DISCLAIMER}"
    )


def _top_sector(payload: dict[str, Any], metric: str) -> str:
    rows = payload.get("sectors", {}).get("rankings", {}).get(metric, [])
    return rows[0]["sector"] if rows else "n/a"


def _delta_sentence(deltas: dict[str, Any]) -> tuple[str, bool]:
    parts: list[str] = []
    for metric in ["optimism", "fear", "risk_intensity"]:
        value = deltas.get(metric)
        if value is None:
            continue
        parts.append(f"{METRIC_LABELS[metric]} changed {float(value):+.1f} vs. the previous day")
    if not parts:
        return "", False
    return "; ".join(parts) + ". ", True


def _mover_sentence(payload: dict[str, Any]) -> str:
    movers = payload.get("sectors", {}).get("movers", [])
    if not movers:
        return ""
    names = [str(item.get("sector", "")) for item in movers[:3] if item.get("sector")]
    return f"Sectors with the biggest moves include {', '.join(names)}. " if names else ""


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
    coverage_note = f"Data coverage: {coverage.get('article_count', 0)} articles, {source_count} sources. "
    if not has_delta:
        coverage_note += "No prior-day baseline yet; day-over-day comparison becomes available tomorrow."

    driver_lines = [
        f"- {item.get('title', '')}: {item.get('driver_reason', '')}"
        for item in drivers[:5]
        if item.get("title")
    ]
    risk_text = ", ".join(f"{key} ({value})" for key, value in risks.items()) or "no clearly concentrated category"
    mover_text = _mover_sentence(payload)

    return (
        "### 1) Today's Market Snapshot\n"
        f"Over the past 24 hours, market optimism is {float(scores.get('optimism', 0) or 0):.1f}, "
        f"fear is {float(scores.get('fear', 0) or 0):.1f}, "
        f"and risk intensity is {float(scores.get('risk_intensity', 0) or 0):.1f}. "
        f"{delta_text}{coverage_note}\n\n"
        "### 2) Sector Highlights and Movers\n"
        f"{top_optimism} leads on optimism; {top_risk} leads on risk intensity. "
        f"{mover_text}\n\n"
        "### 3) Key Driver Events\n"
        + ("\n".join(driver_lines) if driver_lines else "Not enough news yet to form driver events.")
        + "\n\n### 4) Risk Notes\n"
        f"Top 5 risk category distribution: {risk_text}. RSS only covers recent news, so short-term "
        "trends may be sparse.\n\n"
        "### 5) Disclaimer\n"
        f"{DISCLAIMER}"
    )


def _system_prompt() -> str:
    return """
You are a senior market sentiment analyst writing an in-depth English morning brief for
colleagues to read the next day.

Fact and reasoning boundaries:
- Use only the metrics, rankings, distributions, headlines, and evidence sentences in the
  supplied data package. Every judgment must trace back to a specific metric or article in
  it; do not add outside facts.
- Do not predict prices, price moves, or market outcomes, and do not give buy/sell,
  position, or trading advice.
- Three kinds of data-grounded analysis are encouraged: qualitative interpretation of metric
  levels; explaining the plausible link between a news event and the corresponding sector
  metric; and summarizing common themes across multiple articles. Frame analysis as
  "visible from the data" explanation, never present inference as new fact.

Numbers and language conventions:
- Round all numbers in the body to whole numbers. Every number must be paired with relative
  context (high/low judgment, ranking, prior-day comparison, or 7-day position); no bare
  number listing.
- Use at most 4 Arabic numerals per paragraph. Self-check every paragraph after writing and
  split any paragraph that exceeds this. Do not use "X is A, Y is B, Z is C" style listing
  sentences more than once in a row.
- Never use internal field names or technical terms from the data package in the body
  (null, movers, driver_score, snake_case fields, JSON, etc.). When data is missing, use
  plain English, e.g. "no comparison baseline is available today."
- In the body, refer to metrics only by these English names: Optimism, Fear, Uncertainty,
  Attention, Disagreement, Risk Intensity.
- Keep the language plain, restrained, and professional; use complete sentences and
  narrative paragraphs, and avoid exaggerated adjectives.

Output Markdown using exactly this structure:
### 1) Key Takeaway
Open with 2-3 sentences stating today's single most important judgment; do not start with a
list of numbers.

### 2) Market Overview
At least two paragraphs weaving together market metrics, the prior-day change, and the
7-day position; each paragraph should focus on one sentiment dimension rather than reciting
figures item by item.

### 3) Sector and Event Deep Dive
This is the core section and should be roughly half the brief. Cover only the 3-5 sectors
with the most notable attention, risk, or sentiment; write 2-4 full sentences per sector:
first state the level of the metric, then cite specific news to explain the driver, then
explain how the event and the metric corroborate each other. Weave positive and negative
news and topic distribution into the analysis rather than splitting "metrics" and "news"
into two disconnected sections; sectors not worth covering can be mentioned briefly or
skipped -- do not pad the section just to list more sectors. Put quoted headlines in
quotation marks.

### 4) Risks and Tomorrow's Watch Items
Summarize why risk categories, disagreement, or uncertainty are concentrated, and note which
already-emerging themes the next news update should keep watching; this must not turn into a
market forecast or investment advice.

### 5) Data Scope and Disclaimer
Naturally state the article count, source count, time range, data source, and whether
historical comparison data is sufficient, then append the provided disclaimer verbatim at
the end.

Body length should be 900-1200 words (the disclaimer does not count toward this), and must
not be under 900 words; prioritize information density over rhetorical flourish.
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
            f"{candidate}={'listed' if candidate in available_ids else 'not listed'}"
            for candidate in LLM_MODEL_BRIEF_CANDIDATES
        ]
        message = "models.list reference (non-gating): " + ", ".join(states)
    except Exception as exc:  # noqa: BLE001 - listing must never block generation
        message = f"models.list reference failed (does not affect direct calls): {_short_error(exc)}"
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
    """Return an error category and whether the next candidate should be tried."""
    status = getattr(exc, "status_code", None)
    code = _error_code(exc)
    message = str(exc).lower()
    combined = f"{code} {message}"

    if status == 429 or "rate_limit" in combined or "rate limit" in combined:
        return "429 rate limited", True
    if status == 403 or any(
        marker in combined
        for marker in ("permission_denied", "insufficient_permissions", "access denied", "not authorized")
    ):
        return "no permission", True
    if status == 404 or any(marker in combined for marker in ("model_not_found", "model not found", "does not exist")):
        return "model not found", True
    if status in {500, 502, 503, 504} or any(
        marker in combined
        for marker in ("overloaded", "capacity", "server_error", "temporarily unavailable")
    ):
        return "capacity or service unavailable", True
    return "other call error", False


def _selection_log(reference: str, events: list[str], final_reason: str) -> str:
    return "; ".join([reference, *events, final_reason])


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
                event = f"Attempt {model_id} #{attempt}: success"
                events.append(event)
                print(event)
                if candidate_index == 0 and attempt == 1:
                    reason = f"Final choice: {model_id} -- primary model succeeded on first call"
                elif candidate_index == 0:
                    reason = f"Final choice: {model_id} -- primary model succeeded after rate-limit retry"
                else:
                    reason = f"Final choice: {model_id} -- switched after earlier candidate(s) failed"
                log = _selection_log(reference, events, reason)
                print(reason)
                return {"response": response, "model_id": model_id, "log": log, "error": ""}
            except Exception as exc:  # noqa: BLE001 - SDK errors vary by version
                last_error = exc
                category, can_switch = _classify_candidate_error(exc)
                event = f"Attempt {model_id} #{attempt}: failed ({category}, {_short_error(exc)})"
                events.append(event)
                print(event)

                if candidate_index == 0 and attempt == 1 and category == "429 rate limited":
                    wait_event = f"Waiting {LLM_CANDIDATE_RATE_LIMIT_RETRY_SECONDS}s before retrying the primary model"
                    events.append(wait_event)
                    print(wait_event)
                    time.sleep(LLM_CANDIDATE_RATE_LIMIT_RETRY_SECONDS)
                    retried_first_rate_limit = True
                    attempt += 1
                    continue

                if can_switch or retried_first_rate_limit:
                    break

                reason = f"Final choice: rule template -- {model_id} raised an error unsuitable for switching candidates"
                log = _selection_log(reference, events, reason)
                print(reason)
                return {"response": None, "model_id": "", "log": log, "error": _short_error(exc)}

    reason = "Final choice: rule template -- all candidate models failed"
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
    clauses = [part.strip() for part in re.split(r"(?<=[.!?;])\s+", paragraph) if part.strip()]
    if len(clauses) < 2:
        return paragraph

    groups: list[str] = []
    current: list[str] = []
    current_count = 0
    for clause in clauses:
        clause_count = _number_count(clause)
        if current and current_count + clause_count > max_numbers:
            groups.append(" ".join(current))
            current = [clause]
            current_count = clause_count
        else:
            current.append(clause)
            current_count += clause_count
    if current:
        groups.append(" ".join(current))
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
        log = "No model request made; final choice: rule template -- LLM_ENABLED=False"
        print(log)
        return {
            "source": "Rule template",
            "content": generate_rule_brief_from_payload(payload),
            "error": "LLM_ENABLED=False",
            "model_id": "",
            "model_selection_log": log,
        }

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        log = "No model request made; final choice: rule template -- OPENAI_API_KEY not detected"
        print(log)
        return {
            "source": "Rule template",
            "content": generate_rule_brief_from_payload(payload),
            "error": "missing_api_key",
            "model_id": "",
            "model_selection_log": log,
        }

    try:
        from openai import OpenAI
    except ImportError as exc:
        log = f"No model request made; final choice: rule template -- OpenAI SDK unavailable ({_short_error(exc)})"
        print(log)
        return {
            "source": "Rule template",
            "content": generate_rule_brief_from_payload(payload),
            "error": _short_error(exc),
            "model_id": "",
            "model_selection_log": log,
        }

    try:
        client = OpenAI(api_key=api_key, timeout=LLM_TIMEOUT_SECONDS)
        attempt_result = _attempt_brief_models(
            client,
            "Generate the daily market brief using only the following JSON data. "
            f"The disclaimer must be appended verbatim at the end: {DISCLAIMER}\n\n"
            f"{json.dumps(payload, ensure_ascii=False, default=str)}",
        )
        response = attempt_result["response"]
        model_id = str(attempt_result["model_id"])
        selection_log = str(attempt_result["log"])
        if response is None:
            return {
                "source": "Rule template",
                "content": generate_rule_brief_from_payload(payload),
                "error": str(attempt_result["error"]),
                "model_id": "",
                "model_selection_log": selection_log,
            }
        content = str(getattr(response, "output_text", "") or "").strip()
        if not content:
            raise RuntimeError("LLM returned empty content")
        content = _enforce_llm_paragraph_density(content)
        if DISCLAIMER not in content:
            content = f"{content}\n\n### 5) Disclaimer\n{DISCLAIMER}"
        return {
            "source": "AI generated",
            "content": content,
            "error": "",
            "model_id": model_id,
            "model_selection_log": selection_log,
        }
    except Exception as exc:  # noqa: BLE001 - external API must never break the pipeline
        log = locals().get("selection_log", "")
        if log:
            log = f"{log}; final choice: rule template -- failed to process model output ({_short_error(exc)})"
        else:
            log = f"Candidate request chain incomplete; final choice: rule template -- {_short_error(exc)}"
        print(f"LLM brief call failed, fell back to rule template: {_short_error(exc)}")
        return {
            "source": "Rule template",
            "content": generate_rule_brief_from_payload(payload),
            "error": _short_error(exc),
            "model_id": "",
            "model_selection_log": log,
        }
