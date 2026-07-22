from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from src.brief_builder import build_brief_payload
from src.config import BRIEF_ARCHIVE_DIR, BRIEF_GENERATION_HOUR_LOCAL, LATEST_BRIEF_PATH
from src.data_loader import DEMO_DATA_LABEL, REAL_DATA_LABEL, load_articles
from src.llm_summary import generate_llm_brief


def _local_now() -> datetime:
    return datetime.now().astimezone()


def _parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    raw_meta = text[4:end]
    content = text[end + 5 :].strip()
    metadata: dict[str, str] = {}
    for line in raw_meta.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    return metadata, content


def read_latest_brief() -> dict[str, object]:
    if not LATEST_BRIEF_PATH.exists() or LATEST_BRIEF_PATH.stat().st_size == 0:
        return {"metadata": {}, "content": ""}
    text = LATEST_BRIEF_PATH.read_text(encoding="utf-8-sig")
    metadata, content = _parse_front_matter(text)
    return {"metadata": metadata, "content": content}


def _latest_generated_for_date(brief_date: str) -> bool:
    metadata = read_latest_brief().get("metadata", {})
    if not isinstance(metadata, dict):
        return False
    return metadata.get("brief_date") == brief_date


def _write_brief(content: str, metadata: dict[str, str]) -> None:
    BRIEF_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_BRIEF_PATH.parent.mkdir(parents=True, exist_ok=True)
    meta_text = "\n".join(f"{key}: {value}" for key, value in metadata.items())
    full_text = f"---\n{meta_text}\n---\n\n{content.strip()}\n"
    _atomic_write_text(LATEST_BRIEF_PATH, full_text)
    archive_path = BRIEF_ARCHIVE_DIR / f"{metadata['brief_date']}.md"
    _atomic_write_text(archive_path, full_text)


def _atomic_write_text(path: Path, text: str) -> None:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    temp_path = path.with_name(f".{path.name}.{timestamp}.tmp")
    try:
        temp_path.write_text(text, encoding="utf-8-sig")
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _resolve_source(source_mode: str) -> tuple[str, object]:
    df = load_articles(source_mode=source_mode, load_all_history=True)
    if df.empty and source_mode == REAL_DATA_LABEL:
        print("Real news data is empty; brief generation fell back to Demo data.")
        return DEMO_DATA_LABEL, load_articles(source_mode=DEMO_DATA_LABEL, load_all_history=True)
    return source_mode, df


def generate_daily_brief(source_mode: str = REAL_DATA_LABEL, force: bool = False) -> dict[str, str]:
    now_local = _local_now()
    brief_date = now_local.date().isoformat()
    scheduled_time = now_local.replace(hour=BRIEF_GENERATION_HOUR_LOCAL, minute=0, second=0, microsecond=0)

    if not force and now_local < scheduled_time:
        message = f"It is not yet today's brief generation time ({BRIEF_GENERATION_HOUR_LOCAL}:00); skipping."
        print(message)
        return {"status": "skipped", "message": message}

    if not force and _latest_generated_for_date(brief_date):
        message = "Today's brief has already been generated; skipping. Fetching and brief generation stay decoupled."
        print(message)
        return {"status": "skipped", "message": message}

    resolved_source, df = _resolve_source(source_mode)
    if getattr(df, "empty", True):
        message = "No data available for the brief; generation skipped."
        print(message)
        return {"status": "skipped", "message": message}

    payload = build_brief_payload(df, resolved_source)
    result = generate_llm_brief(payload)
    metadata = {
        "brief_date": brief_date,
        "generated_at": payload["generated_at"],
        "generated_at_local": now_local.isoformat(timespec="seconds"),
        "data_window_start": payload["data_window"]["start"],
        "data_window_end": payload["data_window"]["end"],
        "data_snapshot_id": payload["snapshot_id"],
        "summary_source": result.get("source", "Rule template"),
        "data_source": resolved_source,
    }
    if result.get("model_id"):
        metadata["model_id"] = result["model_id"]
    if result.get("model_selection_log"):
        metadata["model_selection_log"] = result["model_selection_log"]
    if result.get("error"):
        metadata["fallback_reason"] = result["error"]

    _write_brief(result["content"], metadata)
    message = f"Daily market brief generated: {metadata['summary_source']}, date {brief_date}."
    print(message)
    return {
        "status": "generated",
        "message": message,
        "summary_source": metadata["summary_source"],
        "model_id": metadata.get("model_id", ""),
        "generated_at": metadata["generated_at"],
    }


def maybe_generate_daily_brief(source_mode: str = REAL_DATA_LABEL) -> dict[str, str]:
    return generate_daily_brief(source_mode=source_mode, force=False)
