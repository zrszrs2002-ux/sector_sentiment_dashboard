"""Selective, cached full-text retrieval for high-value current-day articles."""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd

try:
    import requests
    import trafilatura
except ImportError:  # pragma: no cover - optional dependency degrades cleanly
    requests = None
    trafilatura = None

from src.config import (
    FULLTEXT_CACHE_PATH,
    FULLTEXT_DRIVER_CANDIDATE_COUNT,
    FULLTEXT_MAX_PER_RUN,
    FULLTEXT_MIN_CHARS,
    FULLTEXT_RATE_LIMIT_SECONDS,
    FULLTEXT_REQUEST_TIMEOUT_SECONDS,
    RSS_USER_AGENT,
)
from src.driver_analysis import top_driver_articles
from src.rss_sources import fulltext_allowed_for_names


def load_fulltext_cache(path: Path = FULLTEXT_CACHE_PATH) -> dict[str, dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    for item in payload.values():
        if isinstance(item, dict) and item.get("body_text"):
            item["body_text"] = _clean_body(item["body_text"])
    return payload


def write_fulltext_cache(cache: dict[str, dict[str, Any]], path: Path = FULLTEXT_CACHE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def _numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    prepared = df.copy()
    for column in ["sentiment_score", "risk_intensity", "agg_weight", "source_weight"]:
        values = prepared[column] if column in prepared else pd.Series(0, index=prepared.index)
        prepared[column] = pd.to_numeric(values, errors="coerce").fillna(0)
    return prepared


def select_fulltext_candidates(
    records: list[dict[str, str]],
    cache: dict[str, dict[str, Any]],
    now: datetime | None = None,
) -> list[dict[str, str]]:
    if not records:
        return []
    now = (now or datetime.now(UTC)).astimezone(UTC)
    df = _numeric_columns(pd.DataFrame(records))
    for column in ["article_id", "event_id", "source", "url", "content_level", "published_at"]:
        if column not in df:
            df[column] = ""
    df["_published"] = pd.to_datetime(df["published_at"], utc=True, errors="coerce")
    df["_event"] = df["event_id"].fillna("").astype(str)
    empty_event = df["_event"].eq("")
    df.loc[empty_event, "_event"] = df.loc[empty_event, "article_id"].astype(str)
    today = df["_published"].dt.date.eq(now.date())
    today_df = df[today].copy()
    if today_df.empty:
        return []

    driver_ids: set[str] = set()
    drivers = top_driver_articles(today_df, limit=FULLTEXT_DRIVER_CANDIDATE_COUNT)
    if not drivers.empty and "article_id" in drivers:
        driver_ids = set(drivers["article_id"].fillna("").astype(str))

    multi_representative_ids: set[str] = set()
    for _event_id, group in df.groupby("_event", sort=False):
        if len(group) < 2:
            continue
        representative = group.sort_values(["agg_weight", "article_id"], ascending=[False, True]).iloc[0]
        if pd.notna(representative["_published"]) and representative["_published"].date() == now.date():
            multi_representative_ids.add(str(representative["article_id"]))

    today_df["_is_driver"] = today_df["article_id"].astype(str).isin(driver_ids)
    today_df["_is_multi_rep"] = today_df["article_id"].astype(str).isin(multi_representative_ids)
    today_df["_high_sentiment"] = today_df["sentiment_score"].abs().ge(0.5)
    today_df["_high_risk"] = today_df["risk_intensity"].ge(60)
    eligible = today_df[
        today_df[["_is_driver", "_is_multi_rep", "_high_sentiment", "_high_risk"]].any(axis=1)
    ].copy()
    if eligible.empty:
        return []

    cached_urls = {str(item.get("url", "")).strip() for item in cache.values() if item.get("url")}
    cached_title_keys = {
        re.sub(r"[^a-z0-9]+", " ", str(item.get("title", "")).lower()).strip()
        for item in cache.values()
        if item.get("title")
    }
    eligible["_title_key"] = eligible["title"].fillna("").astype(str).map(
        lambda value: re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    )
    eligible = eligible[
        eligible["url"].fillna("").astype(str).str.startswith(("http://", "https://"))
        & eligible["source"].map(fulltext_allowed_for_names)
        & ~eligible["article_id"].astype(str).isin(cache)
        & ~eligible["url"].fillna("").astype(str).isin(cached_urls)
        & ~eligible["_title_key"].isin(cached_title_keys)
        & ~eligible["content_level"].fillna("").astype(str).eq("fulltext")
    ]
    eligible["_priority"] = (
        8 * eligible["_is_driver"].astype(int)
        + 4 * eligible["_is_multi_rep"].astype(int)
        + 2 * eligible["_high_risk"].astype(int)
        + eligible["_high_sentiment"].astype(int)
    )
    eligible["_abs_sentiment"] = eligible["sentiment_score"].abs()
    eligible = eligible.sort_values(
        ["_priority", "risk_intensity", "_abs_sentiment", "agg_weight", "article_id"],
        ascending=[False, False, False, False, True],
    ).drop_duplicates("_title_key", keep="first").head(FULLTEXT_MAX_PER_RUN)
    return [records[int(index)] for index in eligible.index]


def _extract_body(url: str) -> str:
    if requests is None or trafilatura is None:
        raise RuntimeError("缺少 trafilatura 或 requests")
    response = requests.get(
        url,
        headers={"User-Agent": RSS_USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        timeout=FULLTEXT_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    body = trafilatura.extract(
        response.text,
        url=str(response.url),
        include_comments=False,
        include_tables=False,
        favor_precision=True,
        output_format="txt",
    )
    cleaned = _clean_body(body)
    if len(cleaned) < FULLTEXT_MIN_CHARS:
        raise ValueError(f"正文提取结果不足 {FULLTEXT_MIN_CHARS} 字符")
    return cleaned


def _clean_body(value: object) -> str:
    return "\n".join(line.rstrip() for line in str(value or "").splitlines()).strip()


def fetch_and_rescore_fulltext(
    records: list[dict[str, str]],
    *,
    fetch_new: bool = True,
    force_existing: bool = False,
) -> dict[str, Any]:
    started = perf_counter()
    cache = load_fulltext_cache()
    working = [dict(record) for record in records]
    by_id = {str(record.get("article_id", "")): record for record in working}
    existing_analysis_records = [
        record
        for record in working
        if record.get("body_text")
        and (
            force_existing
            or not all(
                str(record.get(column, "")).strip()
                for column in ["sentiment_score_fulltext", "p_positive_fulltext", "p_neutral_fulltext", "p_negative_fulltext"]
            )
        )
    ]
    restore_records: list[dict[str, str]] = []
    for article_id, cached in cache.items():
        record = by_id.get(article_id)
        if not record or cached.get("status") != "success" or record.get("body_text"):
            continue
        body_text = str(cached.get("body_text", ""))
        if body_text:
            record.update({"body_text": body_text, "content_level": "fulltext", "rescored": "True"})
            restore_records.append(record)

    candidates = select_fulltext_candidates(working, cache) if fetch_new else []
    fetched_records: list[dict[str, str]] = []
    prior_scores: dict[str, dict[str, Any]] = {}
    last_request_started: float | None = None
    failed_count = 0
    for record in candidates:
        if last_request_started is not None:
            remaining = FULLTEXT_RATE_LIMIT_SECONDS - (perf_counter() - last_request_started)
            if remaining > 0:
                time.sleep(remaining)
        article_id = str(record.get("article_id", ""))
        attempted_at = datetime.now(UTC).isoformat(timespec="seconds")
        last_request_started = perf_counter()
        try:
            body_text = _extract_body(str(record.get("url", "")))
        except Exception as exc:  # noqa: BLE001 - per-article failures are cached and silent
            failed_count += 1
            cache[article_id] = {
                "status": "failed",
                "attempted_at": attempted_at,
                "url": str(record.get("url", "")),
                "title": str(record.get("title", "")),
                "reason": f"{type(exc).__name__}: {exc}"[:300],
            }
            continue
        prior_scores[article_id] = {
            "title": str(record.get("title", "")),
            "summary_sentiment_score": float(record.get("sentiment_score", 0) or 0),
            "summary_evidence_sentence": str(record.get("evidence_sentence", "")),
        }
        record.update({"body_text": body_text, "content_level": "fulltext", "rescored": "True"})
        fetched_records.append(record)

    rescore_inputs = existing_analysis_records + restore_records + fetched_records
    comparisons: list[dict[str, Any]] = []
    rescored_count = 0
    if rescore_inputs:
        from src.article_pipeline import enrich_records_batch

        rescored_records, _errors = enrich_records_batch(rescore_inputs)
        for original, rescored in zip(rescore_inputs, rescored_records, strict=True):
            article_id = str(original.get("article_id", ""))
            if rescored.get("processing_error"):
                original["rescored"] = "False"
                continue
            by_id[article_id] = rescored
            rescored_count += 1
            body_text = str(rescored.get("body_text", ""))
            prior = prior_scores.get(article_id, {})
            cache[article_id] = {
                "status": "success",
                "attempted_at": cache.get(article_id, {}).get(
                    "attempted_at", datetime.now(UTC).isoformat(timespec="seconds")
                ),
                "url": str(rescored.get("url", "")),
                "title": str(rescored.get("title", "")),
                "body_text": body_text,
                "body_length": len(body_text),
                "summary_sentiment_score": float(rescored.get("sentiment_score", 0) or 0),
                "fulltext_sentiment_score": float(rescored.get("sentiment_score_fulltext", 0) or 0),
                "fulltext_evidence_sentence": str(rescored.get("evidence_sentence", "")),
            }
            if prior:
                comparisons.append(
                    {
                        **prior,
                        "fulltext_sentiment_score": float(rescored.get("sentiment_score_fulltext", 0) or 0),
                        "fulltext_evidence_sentence": str(rescored.get("evidence_sentence", "")),
                        "body_length": len(body_text),
                    }
                )

    write_fulltext_cache(cache)
    final_records = [by_id.get(str(record.get("article_id", "")), record) for record in working]
    result = {
        "records": final_records,
        "selected_count": len(candidates),
        "attempted_count": len(candidates),
        "success_count": len(fetched_records),
        "failed_count": failed_count,
        "restored_from_cache_count": len(restore_records),
        "rescored_count": rescored_count,
        "elapsed_seconds": round(perf_counter() - started, 3),
        "comparisons": comparisons,
    }
    print(
        "选择性正文抓取完成："
        f"候选 {result['selected_count']}，成功 {result['success_count']}，失败 {result['failed_count']}，"
        f"缓存恢复 {result['restored_from_cache_count']}，重评分 {result['rescored_count']}，"
        f"耗时 {result['elapsed_seconds']:.1f} 秒。"
    )
    return result


def sync_fulltext_to_raw(
    raw_records: list[dict[str, str]], processed_records: list[dict[str, str]]
) -> int:
    processed_by_id = {
        str(record.get("article_id", "")): record
        for record in processed_records
        if record.get("body_text")
    }
    updated = 0
    for raw in raw_records:
        processed = processed_by_id.get(str(raw.get("article_id", "")))
        if not processed:
            continue
        before = (raw.get("body_text", ""), raw.get("content_level", ""), raw.get("rescored", ""))
        raw.update(
            {
                "body_text": processed.get("body_text", ""),
                "content_level": "fulltext",
                "rescored": processed.get("rescored", "True"),
            }
        )
        after = (raw.get("body_text", ""), raw.get("content_level", ""), raw.get("rescored", ""))
        updated += before != after
    return updated
