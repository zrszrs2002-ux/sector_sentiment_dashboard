"""Create a blind, cross-stratum annotation sample and a private prediction key."""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (  # noqa: E402
    ANNOTATION_DIR,
    ANNOTATION_RANDOM_SEED,
    ANNOTATION_SAMPLE_SIZE,
    RAW_ARTICLES_PATH,
    REAL_PROCESSED_ARTICLES_PATH,
)
from src.preprocessing import write_csv_atomic  # noqa: E402


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
PROBABILITY_COLUMNS = {
    "positive": "p_positive",
    "neutral": "p_neutral",
    "negative": "p_negative",
}


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
    """Round-robin over shuffled strata, redistributing quota from small strata."""
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


def build_annotation_files(
    raw_path: Path,
    processed_path: Path,
    output_dir: Path,
    sample_size: int = ANNOTATION_SAMPLE_SIZE,
    seed: int = ANNOTATION_RANDOM_SEED,
) -> tuple[pd.DataFrame, pd.DataFrame]:
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

    distribution = key.groupby(["stratum_sector", "stratum_sentiment"]).size()
    unmatched = len(raw) - len(candidates)
    print(
        f"盲标抽样完成：候选 {len(candidates)} 条，抽取 {len(blind)} 条，"
        f"覆盖 {len(distribution)} 个 sector×sentiment 层；未匹配 processed {unmatched} 条。"
    )
    print(
        f"层内样本范围：{int(distribution.min())}-{int(distribution.max())}；"
        f"随机种子：{seed}。"
    )
    print(f"盲标文件：{output_dir / 'annotation_blind.csv'}")
    print(f"对账 key：{output_dir / 'annotation_key.csv'}（请勿提供给标注者）")
    return blind, key


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按 sector×FinBERT 情绪分层生成盲标样本。")
    parser.add_argument("--raw-path", type=Path, default=RAW_ARTICLES_PATH)
    parser.add_argument("--processed-path", type=Path, default=REAL_PROCESSED_ARTICLES_PATH)
    parser.add_argument("--output-dir", type=Path, default=ANNOTATION_DIR)
    parser.add_argument("--sample-size", type=int, default=ANNOTATION_SAMPLE_SIZE)
    parser.add_argument("--seed", type=int, default=ANNOTATION_RANDOM_SEED)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.sample_size <= 0:
        raise ValueError("sample-size 必须大于 0。")
    build_annotation_files(
        args.raw_path,
        args.processed_path,
        args.output_dir,
        args.sample_size,
        args.seed,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
