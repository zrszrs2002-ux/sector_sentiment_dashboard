"""Compare the current r2 signal outputs with the Git HEAD r1 dataset."""

from __future__ import annotations

import io
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import REAL_PROCESSED_ARTICLES_PATH
from src.driver_analysis import top_driver_articles


def head_dataframe() -> pd.DataFrame:
    relative = REAL_PROCESSED_ARTICLES_PATH.relative_to(REAL_PROCESSED_ARTICLES_PATH.parents[1])
    result = subprocess.run(
        ["git", "show", f"HEAD:{relative.as_posix()}"],
        cwd=REAL_PROCESSED_ARTICLES_PATH.parents[1],
        check=True,
        capture_output=True,
    )
    return pd.read_csv(io.BytesIO(result.stdout))


def exploded_counts(series: pd.Series) -> Counter[str]:
    counts: Counter[str] = Counter()
    for value in series.fillna("").astype(str):
        counts.update(item.strip() for item in value.split(";") if item.strip())
    return counts


def cluster_groups(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    event_ids = df["event_id"].fillna(df["article_id"]).astype(str)
    return {str(key): group.copy() for key, group in df.groupby(event_ids, sort=False)}


def cluster_stats(df: pd.DataFrame) -> dict[str, object]:
    groups = cluster_groups(df)
    sizes = Counter(len(group) for group in groups.values())
    spans = []
    for group in groups.values():
        dates = pd.to_datetime(group["published_at"], utc=True, errors="coerce").dropna()
        spans.append((dates.max() - dates.min()).total_seconds() / 3600 if len(dates) else 0)
    return {
        "cluster_count": len(groups),
        "multi_cluster_count": sum(size > 1 for size in sizes.elements()),
        "size_distribution": dict(sorted(sizes.items())),
        "max_size": max(sizes, default=0),
        "max_span_hours": round(max(spans, default=0), 3),
        "over_72_hours": sum(span > 72 for span in spans),
    }


def rows_for_old_event(old: pd.DataFrame, predicate) -> pd.DataFrame:
    candidates = old[predicate(old)]
    if candidates.empty:
        return candidates
    event_id = candidates["event_id"].value_counts().index[0]
    return old[old["event_id"].astype(str).eq(str(event_id))]


def compact_event(group: pd.DataFrame) -> dict[str, object]:
    dates = pd.to_datetime(group["published_at"], utc=True, errors="coerce").dropna()
    sources = {
        item.strip()
        for value in group["source"].fillna("").astype(str)
        for item in re.split(r"[;|]+", value)
        if item.strip()
    }
    return {
        "event_id": str(group.iloc[0]["event_id"]),
        "size": len(group),
        "span_hours": round((dates.max() - dates.min()).total_seconds() / 3600, 3),
        "sentiment_range": [
            round(float(pd.to_numeric(group["sentiment_score"], errors="coerce").min()), 3),
            round(float(pd.to_numeric(group["sentiment_score"], errors="coerce").max()), 3),
        ],
        "source_count": len(sources),
        "sources": sorted(sources),
        "titles": group["title"].fillna("").astype(str).tolist(),
    }


def main() -> None:
    old = head_dataframe()
    current = pd.read_csv(REAL_PROCESSED_ARTICLES_PATH)
    risk = pd.to_numeric(current["risk_intensity"], errors="coerce").fillna(0)
    histogram = pd.cut(
        risk,
        bins=list(range(0, 111, 10)),
        right=False,
        include_lowest=True,
    ).value_counts(sort=False)

    old_text = (old["title"].fillna("") + " " + old["summary"].fillna("")).str.lower()
    old_apple = rows_for_old_event(
        old,
        lambda frame: old_text.str.contains("apple") & old_text.str.contains("broadcom"),
    )
    apple_ids = set(old_apple["article_id"].astype(str))
    current_apple = current[current["article_id"].astype(str).isin(apple_ids)]

    old_meta = rows_for_old_event(
        old,
        lambda frame: (
            old["tickers"].fillna("").astype(str).str.contains(r"(?:^|;)META(?:;|$)", regex=True)
            & old["title"].fillna("").astype(str).str.contains("Meta", case=False)
        ),
    )
    meta_ids = set(old_meta["article_id"].astype(str))
    current_meta = current[current["article_id"].astype(str).isin(meta_ids)]

    random_groups = [group for group in cluster_groups(current).values() if len(group) > 1]
    sampled_indices = pd.Series(range(len(random_groups))).sample(
        n=min(5, len(random_groups)), random_state=5720
    )

    driver_df = current.copy()
    for column in ["agg_weight", "risk_intensity", "sentiment_score", "source_count"]:
        driver_df[column] = pd.to_numeric(driver_df[column], errors="coerce").fillna(0)
    top_drivers = top_driver_articles(driver_df)
    meta_drivers = top_drivers[
        top_drivers["title"].fillna("").astype(str).str.contains("Meta", case=False)
    ]

    payload = {
        "article_count": len(current),
        "risk_stats": {
            "mean": round(float(risk.mean()), 4),
            "std": round(float(risk.std()), 4),
            "quantiles": {
                str(key): round(float(value), 4)
                for key, value in risk.quantile([0, 0.1, 0.25, 0.5, 0.75, 0.9, 1]).items()
            },
            "zero_count": int(risk.eq(0).sum()),
            "unique_count": int(risk.nunique()),
            "histogram": {str(key): int(value) for key, value in histogram.items()},
        },
        "risk_before": dict(exploded_counts(old["risk_category"]).most_common()),
        "risk_after": dict(exploded_counts(current["risk_category"]).most_common()),
        "topic_before_top10": {
            str(key): int(value) for key, value in old["topic"].value_counts().head(10).items()
        },
        "topic_after_top10": {
            str(key): int(value)
            for key, value in current["topic"].value_counts().head(10).items()
        },
        "technology_general_before": int(
            ((old["sector"] == "Technology") & (old["topic"] == "general market sentiment")).sum()
        ),
        "technology_general_after": int(
            ((current["sector"] == "Technology") & (current["topic"] == "general market sentiment")).sum()
        ),
        "clusters_before": cluster_stats(old),
        "clusters_after": cluster_stats(current),
        "apple_broadcom_old_cluster_size": len(old_apple),
        "apple_broadcom_r2_events": [
            compact_event(group) for group in cluster_groups(current_apple).values()
        ],
        "meta_old_cluster_size": len(old_meta),
        "meta_r2_events": [compact_event(group) for group in cluster_groups(current_meta).values()],
        "meta_top_drivers": meta_drivers[
            ["title", "event_id", "source_count", "driver_score"]
        ].to_dict("records"),
        "random_multi_clusters": [compact_event(random_groups[index]) for index in sampled_indices],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
