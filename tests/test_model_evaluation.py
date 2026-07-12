from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scripts.sample_for_annotation import BLIND_FIELDS, build_annotation_files
from src.evaluation import SENTIMENT_LABELS, evaluate_annotation_files


def fake_annotation_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    true_labels = ["negative"] * 10 + ["neutral"] * 10 + ["positive"] * 10
    predictions = (
        ["negative"] * 8
        + ["neutral"] * 2
        + ["neutral"] * 8
        + ["positive"] * 2
        + ["positive"] * 8
        + ["negative"] * 2
    )
    risk_labels = ["macro risk", "interest rate risk", "regulatory risk"]
    texts = {
        "negative": "Loss and decline remained weak.",
        "neutral": "Results may appear different and could change.",
        "positive": "Growth improved and demand became stronger.",
    }

    annotation_rows: list[dict[str, object]] = []
    key_rows: list[dict[str, object]] = []
    for index, (truth, prediction) in enumerate(zip(true_labels, predictions, strict=True)):
        article_id = f"fake-{index:02d}"
        true_risk = risk_labels[index // 10]
        predicted_risk = risk_labels[(index // 10 + (1 if index % 10 >= 8 else 0)) % 3]
        probabilities = {label: 0.1 for label in SENTIMENT_LABELS}
        probabilities[prediction] = 0.8
        annotation_rows.append(
            {
                "article_id": article_id,
                "title": f"Fake article {index}",
                "summary": texts[truth],
                "content": texts[truth],
                "url": f"https://example.com/{index}",
                "published_at": "2026-07-01T00:00:00+00:00",
                "label_sentiment": truth,
                "label_sector_ok": "1" if index < 27 else "0",
                "label_risk_categories": true_risk,
                "label_evidence_ok": "1" if index < 24 else "0",
                "notes": "",
            }
        )
        key_rows.append(
            {
                "article_id": article_id,
                "stratum_sector": "Technology",
                "stratum_sentiment": prediction,
                "predicted_sentiment_finbert": prediction,
                "predicted_sector": "Technology",
                "predicted_risk_categories": predicted_risk,
                "predicted_evidence_sentence": texts[truth],
                "finbert_confidence": 0.8,
                "p_positive": probabilities["positive"],
                "p_neutral": probabilities["neutral"],
                "p_negative": probabilities["negative"],
            }
        )
    return pd.DataFrame(annotation_rows), pd.DataFrame(key_rows)


class ModelEvaluationTests(unittest.TestCase):
    def test_thirty_row_end_to_end_metrics(self) -> None:
        annotations, key = fake_annotation_frames()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            annotation_path = root / "annotation_blind.csv"
            key_path = root / "annotation_key.csv"
            error_path = root / "sentiment_errors.csv"
            annotations.to_csv(annotation_path, index=False, encoding="utf-8-sig")
            key.sample(frac=1, random_state=7).to_csv(
                key_path, index=False, encoding="utf-8-sig"
            )
            result = evaluate_annotation_files(annotation_path, key_path, error_path)
            errors_on_disk = pd.read_csv(error_path, encoding="utf-8-sig")
            repeated = evaluate_annotation_files(annotation_path, key_path, error_path)
            self.assertEqual(len(repeated["sentiment_errors"]), 6)
            self.assertFalse((root / "backups").exists())

        finbert = result["sentiment_reports"]["FinBERT"]
        neutral = result["sentiment_reports"]["全中性基线"]
        lexicon = result["sentiment_reports"]["词典引擎"]
        self.assertAlmostEqual(finbert["accuracy"], 0.8)
        self.assertAlmostEqual(finbert["macro_f1"], 0.8)
        self.assertEqual(finbert["confusion_matrix"].loc["negative", "neutral"], 2)
        self.assertAlmostEqual(neutral["accuracy"], 1 / 3)
        self.assertAlmostEqual(neutral["macro_f1"], 1 / 6)
        self.assertAlmostEqual(lexicon["accuracy"], 1.0)
        self.assertAlmostEqual(result["calibration"]["brier_score"], 0.34)
        self.assertEqual(len(result["sentiment_errors"]), 6)
        self.assertEqual(len(errors_on_disk), 6)
        self.assertAlmostEqual(result["sector_mapping"]["accuracy"], 0.9)
        self.assertAlmostEqual(result["evidence"]["precision"], 0.8)

        risk = result["risk"]["per_class"].set_index("risk_category")
        self.assertAlmostEqual(risk.loc["macro risk", "precision"], 0.8)
        self.assertAlmostEqual(risk.loc["macro risk", "recall"], 0.8)
        self.assertAlmostEqual(result["risk"]["macro_f1"], 0.24)

    def test_manual_brier_examples(self) -> None:
        correct_brier = (0.8 - 1) ** 2 + 0.1**2 + 0.1**2
        wrong_brier = 0.8**2 + (0.1 - 1) ** 2 + 0.1**2
        overall = (24 * correct_brier + 6 * wrong_brier) / 30
        self.assertAlmostEqual(correct_brier, 0.06)
        self.assertAlmostEqual(wrong_brier, 1.46)
        self.assertAlmostEqual(overall, 0.34)

    def test_blind_sampling_contract(self) -> None:
        annotations, key = fake_annotation_frames()
        raw = annotations[["article_id", "title", "summary", "content", "url", "published_at"]]
        processed = key.rename(
            columns={
                "predicted_sector": "sector",
                "predicted_risk_categories": "risk_category",
                "predicted_evidence_sentence": "evidence_sentence",
                "finbert_confidence": "model_confidence",
            }
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_path = root / "raw.csv"
            processed_path = root / "processed.csv"
            output_dir = root / "annotation"
            raw.to_csv(raw_path, index=False, encoding="utf-8-sig")
            processed.to_csv(processed_path, index=False, encoding="utf-8-sig")
            blind, private_key = build_annotation_files(
                raw_path,
                processed_path,
                output_dir,
                sample_size=24,
                seed=5720,
            )

            self.assertEqual(list(blind.columns), BLIND_FIELDS)
            self.assertFalse(any("predict" in column.lower() for column in blind.columns))
            self.assertTrue(blind["url"].str.startswith('=HYPERLINK("https://example.com/').all())
            self.assertEqual(len(blind), 24)
            self.assertEqual(len(private_key), 24)
            self.assertTrue((output_dir / "annotation_blind.csv").exists())
            self.assertTrue((output_dir / "annotation_key.csv").exists())


if __name__ == "__main__":
    unittest.main()
