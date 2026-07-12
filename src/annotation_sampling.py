"""Reusable blind-sample generation for the human-annotation workflow."""

from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

from src.config import ANNOTATION_SAMPLE_SEED, ANNOTATION_SAMPLE_SIZE
from src.preprocessing import write_csv_atomic


BLIND_FIELDS = [
    "article_id",
    "title",
    "summary",
    "content",
    "url",
    "published_at",
    "label_sentiment",
    "label_sector_ok",
    "label_risk_categories",
    "label_evidence_ok",
    "notes",
]
KEY_FIELDS = [
    "article_id",
    "stratum_sector",
    "stratum_sentiment",
    "predicted_sentiment_finbert",
    "predicted_sector",
    "predicted_risk_categories",
    "predicted_evidence_sentence",
    "finbert_confidence",
    "p_positive",
    "p_neutral",
    "p_negative",
]
ANNOTATION_LABEL_COLUMNS = [
    "label_sentiment",
    "label_sector_ok",
    "label_risk_categories",
    "label_evidence_ok",
]
PROBABILITY_COLUMNS = {
    "positive": "p_positive",
    "neutral": "p_neutral",
    "negative": "p_negative",
}


def excel_hyperlink_formula(url: object) -> str:
    """Return an Excel hyperlink formula while preserving blank and invalid URLs."""
    value = str(url or "").strip()
    if not value or value.upper().startswith("=HYPERLINK("):
        return value
    if not value.lower().startswith(("https://", "http://")):
        return value
    escaped_url = value.replace('"', '""')
    return f'=HYPERLINK("{escaped_url}","打开原文")'

def read_required_csv(path: Path, required_columns: set[str]) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        raise FileNotFoundError(f"文件不存在或为空：{path}")
    frame = pd.read_csv(path, encoding="utf-8-sig")
    missing = sorted(required_columns - set(frame.columns))
    if missing:
        raise ValueError(f"{path.name} 缺少字段：{missing}")
    return frame


def finbert_label(row: pd.Series) -> str:
    probabilities: dict[str, float] = {}
    for label, column in PROBABILITY_COLUMNS.items():
        value = pd.to_numeric(row.get(column, 0), errors="coerce")
        probabilities[label] = 0.0 if pd.isna(value) else float(value)
    return max(probabilities, key=probabilities.get)


def balanced_stratified_sample(
    frame: pd.DataFrame,
    sample_size: int,
    seed: int,
) -> pd.DataFrame:
    """Round-robin through shuffled sector-by-sentiment strata."""
    if frame.empty or sample_size <= 0:
        return frame.head(0).copy()

    rng = random.Random(seed)
    groups: dict[tuple[str, str], list[int]] = {}
    for stratum, group in frame.groupby(["predicted_sector", "predicted_sentiment_finbert"]):
        indexes = group.index.tolist()
        rng.shuffle(indexes)
        groups[(str(stratum[0]), str(stratum[1]))] = indexes

    stratum_order = sorted(groups)
    rng.shuffle(stratum_order)
    cursors = {stratum: 0 for stratum in stratum_order}
    target = min(sample_size, len(frame))
    selected: list[int] = []

    while len(selected) < target:
        added = False
        for stratum in stratum_order:
            cursor = cursors[stratum]
            if cursor >= len(groups[stratum]):
                continue
            selected.append(groups[stratum][cursor])
            cursors[stratum] = cursor + 1
            added = True
            if len(selected) == target:
                break
        if not added:
            break
    return frame.loc[selected].copy()


def generate_annotation_samples(
    raw_path: Path,
    processed_path: Path,
    output_dir: Path,
    sample_size: int = ANNOTATION_SAMPLE_SIZE,
    seed: int = ANNOTATION_SAMPLE_SEED,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate blind and private-key CSVs from the same reproducible sample."""
    raw_fields = {"article_id", "title", "summary", "content", "url", "published_at"}
    prediction_fields = {
        "article_id",
        "sector",
        "risk_category",
        "evidence_sentence",
        "model_confidence",
        *PROBABILITY_COLUMNS.values(),
    }
    raw = read_required_csv(raw_path, raw_fields).drop_duplicates("article_id", keep="last")
    processed = read_required_csv(processed_path, prediction_fields).drop_duplicates(
        "article_id", keep="last"
    )

    raw_columns = ["article_id", "title", "summary", "content", "url", "published_at"]
    prediction_columns = [
        "article_id",
        "sector",
        "risk_category",
        "evidence_sentence",
        "model_confidence",
        *PROBABILITY_COLUMNS.values(),
    ]
    candidates = raw[raw_columns].merge(
        processed[prediction_columns],
        on="article_id",
        how="inner",
        validate="one_to_one",
    )
    if candidates.empty:
        raise ValueError("raw 与 processed 没有可按 article_id 对齐的新闻。")

    for column in PROBABILITY_COLUMNS.values():
        candidates[column] = pd.to_numeric(candidates[column], errors="coerce").fillna(0.0)
    candidates["predicted_sentiment_finbert"] = candidates.apply(finbert_label, axis=1)
    candidates["predicted_sector"] = (
        candidates["sector"].fillna("").astype(str).str.strip().replace("", "Unmapped")
    )
    candidates["predicted_risk_categories"] = candidates["risk_category"].fillna("").astype(str)
    candidates["predicted_evidence_sentence"] = candidates["evidence_sentence"].fillna("").astype(str)
    candidates["finbert_confidence"] = candidates[list(PROBABILITY_COLUMNS.values())].max(axis=1)

    sampled = balanced_stratified_sample(candidates, sample_size, seed)
    blind = sampled[raw_columns].fillna("").copy()
    blind["url"] = blind["url"].map(excel_hyperlink_formula)
    for column in BLIND_FIELDS[len(raw_columns) :]:
        blind[column] = ""
    blind = blind.reindex(columns=BLIND_FIELDS)
    if any("predict" in column.lower() for column in blind.columns):
        raise AssertionError("盲标文件意外包含模型预测列。")

    key = sampled.copy()
    key["stratum_sector"] = key["predicted_sector"]
    key["stratum_sentiment"] = key["predicted_sentiment_finbert"]
    key = key.reindex(columns=KEY_FIELDS).fillna("")

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv_atomic(output_dir / "annotation_blind.csv", BLIND_FIELDS, blind.to_dict("records"))
    write_csv_atomic(output_dir / "annotation_key.csv", KEY_FIELDS, key.to_dict("records"))
    return blind, key


def completed_annotation_cells(frame: pd.DataFrame) -> int:
    """Count only completed label cells; notes do not block a reproducible redraw."""
    return sum(
        int(frame.get(column, pd.Series(dtype=str)).fillna("").astype(str).str.strip().ne("").sum())
        for column in ANNOTATION_LABEL_COLUMNS
    )


# Preserve the original callable name for existing scripts and test consumers.
build_annotation_files = generate_annotation_samples