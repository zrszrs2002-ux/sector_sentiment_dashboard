"""CLI wrapper for reproducible blind annotation sample generation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.annotation_sampling import BLIND_FIELDS, build_annotation_files  # noqa: E402
from src.config import (  # noqa: E402
    ANNOTATION_DIR,
    ANNOTATION_SAMPLE_SEED,
    ANNOTATION_SAMPLE_SIZE,
    RAW_ARTICLES_PATH,
    REAL_PROCESSED_ARTICLES_PATH,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按 sector×FinBERT 情绪分层生成盲标样本。")
    parser.add_argument("--raw-path", type=Path, default=RAW_ARTICLES_PATH)
    parser.add_argument("--processed-path", type=Path, default=REAL_PROCESSED_ARTICLES_PATH)
    parser.add_argument("--output-dir", type=Path, default=ANNOTATION_DIR)
    parser.add_argument("--sample-size", type=int, default=ANNOTATION_SAMPLE_SIZE)
    parser.add_argument("--seed", type=int, default=ANNOTATION_SAMPLE_SEED)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.sample_size <= 0:
        raise ValueError("sample-size 必须大于 0。")
    blind, key = build_annotation_files(
        args.raw_path,
        args.processed_path,
        args.output_dir,
        args.sample_size,
        args.seed,
    )
    print(f"盲标抽样完成：抽取 {len(blind)} 条，随机种子：{args.seed}。")
    print(f"盲标文件：{args.output_dir / 'annotation_blind.csv'}")
    print(f"对账 key：{args.output_dir / 'annotation_key.csv'}（请勿提供给标注者，共 {len(key)} 条）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())