"""Validate r3 source weights, publishers, full-text cache, and snapshots."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (  # noqa: E402
    FULLTEXT_CACHE_PATH,
    MARKET_DAILY_SCORES_PATH,
    REAL_PROCESSED_ARTICLES_PATH,
    SECTOR_DAILY_SCORES_PATH,
)
from src.rss_sources import enabled_rss_sources, split_multi_value  # noqa: E402


def main() -> None:
    df = pd.read_csv(REAL_PROCESSED_ARTICLES_PATH)
    cache = json.loads(FULLTEXT_CACHE_PATH.read_text(encoding="utf-8"))
    publisher_counts: Counter[str] = Counter()
    for value in df["publisher"].fillna(""):
        publisher_counts.update(split_multi_value(value))

    for column in ["time_weight", "relevance_weight", "dedup_factor", "source_weight", "agg_weight"]:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)
    expected_weight = df["time_weight"] * df["relevance_weight"] * df["dedup_factor"] * df["source_weight"]

    successes = [item for item in cache.values() if item.get("status") == "success"]
    failures = [item for item in cache.values() if item.get("status") == "failed"]
    comparisons = []
    seen_titles: set[str] = set()
    for item in successes:
        if item.get("summary_sentiment_score") is None:
            continue
        title = str(item.get("title", ""))
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        summary_score = float(item["summary_sentiment_score"])
        fulltext_score = float(item["fulltext_sentiment_score"])
        comparisons.append(
            {
                "title": title,
                "summary_score": summary_score,
                "fulltext_score": fulltext_score,
                "absolute_change": abs(fulltext_score - summary_score),
                "evidence_sentence": str(item.get("fulltext_evidence_sentence", "")),
            }
        )
    comparisons.sort(key=lambda item: item["absolute_change"], reverse=True)

    sector_snapshots = pd.read_csv(SECTOR_DAILY_SCORES_PATH)
    market_snapshots = pd.read_csv(MARKET_DAILY_SCORES_PATH)
    payload = {
        "configured_sources": len(enabled_rss_sources()),
        "processed_articles": len(df),
        "publisher_top15": publisher_counts.most_common(15),
        "source_weight_values": sorted(df["source_weight"].dropna().unique().tolist()),
        "agg_weight_max_abs_error": float((df["agg_weight"] - expected_weight).abs().max()),
        "fulltext": {
            "cache_success": len(successes),
            "cache_failed": len(failures),
            "processed_fulltext": int(df["content_level"].fillna("").eq("fulltext").sum()),
            "processed_rescored": int(df["rescored"].fillna("").astype(str).str.lower().eq("true").sum()),
            "average_body_length": (
                sum(int(item.get("body_length", 0)) for item in successes) / len(successes)
                if successes
                else 0
            ),
            "top_three_changes": comparisons[:3],
        },
        "snapshot_revisions": {
            "sector": sector_snapshots["pipeline_revision"].fillna("").value_counts().to_dict(),
            "market": market_snapshots["pipeline_revision"].fillna("").value_counts().to_dict(),
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
