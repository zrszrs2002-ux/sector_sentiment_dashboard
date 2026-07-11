from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import src.daily_snapshots as daily_snapshots
from src.aggregation import sector_metrics
from src.config import (
    BASELINE_WEIGHTS,
    ENHANCED_WEIGHTS,
    FORMULA_VERSION_BASELINE,
    FORMULA_VERSION_ENHANCED,
    PIPELINE_REVISION,
)
from src.keyword_signals import normalized_sentence_hit_score, signal_terms
from src.scoring import calculate_article_formula_values, normalized_entropy


class EnhancedMetricTests(unittest.TestCase):
    def setUp(self) -> None:
        now = pd.Timestamp.now(tz="UTC")
        components = {
            "b_bull": 1.0,
            "b_bear": 0.0,
            "g_growth": 1.0,
            "s_shock": 1.0,
            "k_unc": 0.5,
            "entropy_norm": normalized_entropy([0.2, 0.5, 0.3]),
        }
        self.components = components
        self.articles = pd.DataFrame(
            [
                {
                    "article_id": "positive",
                    "source": "source-a",
                    "sector": "Technology",
                    "sentiment_score": 0.5,
                    "agg_weight": 1.0,
                    "risk_intensity": 20.0,
                    "published_at": now,
                    "collected_at": now,
                    "p_positive": 0.6,
                    "p_neutral": 0.3,
                    "p_negative": 0.1,
                    **components,
                },
                {
                    "article_id": "negative",
                    "source": "source-b",
                    "sector": "Technology",
                    "sentiment_score": -0.5,
                    "agg_weight": 1.0,
                    "risk_intensity": 40.0,
                    "published_at": now,
                    "collected_at": now,
                    "p_positive": 0.1,
                    "p_neutral": 0.3,
                    "p_negative": 0.6,
                    **components,
                },
            ]
        )

    def test_article_formula_groups_share_components(self) -> None:
        baseline = calculate_article_formula_values(
            0.2, 0.5, 0.3, self.components, BASELINE_WEIGHTS
        )
        enhanced = calculate_article_formula_values(
            0.2, 0.5, 0.3, self.components, ENHANCED_WEIGHTS
        )
        self.assertAlmostEqual(baseline["optimism"], 20.0)
        self.assertAlmostEqual(baseline["fear"], 30.0)
        self.assertAlmostEqual(enhanced["optimism"], 44.0)
        self.assertAlmostEqual(enhanced["fear"], 31.0)

    def test_sentence_hit_normalization_and_lm_merge(self) -> None:
        score = normalized_sentence_hit_score(
            ["beat expectations", "plain", "plain", "plain"],
            ["beat expectations"],
        )
        self.assertAlmostEqual(score, 0.75)
        self.assertGreaterEqual(len(signal_terms()["k_unc"]), 297)

    def test_disagreement_enhancement_and_risk_stability(self) -> None:
        baseline = sector_metrics(self.articles, BASELINE_WEIGHTS)
        enhanced = sector_metrics(self.articles, ENHANCED_WEIGHTS)
        baseline_row = baseline[baseline["sector"].eq("Technology")].iloc[0]
        enhanced_row = enhanced[enhanced["sector"].eq("Technology")].iloc[0]
        self.assertAlmostEqual(float(baseline_row["disagreement"]), 50.0)
        self.assertAlmostEqual(float(enhanced_row["disagreement"]), 75.0)
        self.assertAlmostEqual(
            float(baseline_row["risk_intensity"]),
            float(enhanced_row["risk_intensity"]),
        )

    def test_attention_switch_accepts_legacy_history(self) -> None:
        now = pd.Timestamp.now(tz="UTC")
        history = pd.DataFrame(
            [
                {
                    "snapshot_date": (now - pd.Timedelta(days=31 - index)).date(),
                    "sector": "Technology",
                    "article_count": index + 1,
                }
                for index in range(30)
            ]
        )
        baseline = sector_metrics(
            self.articles, BASELINE_WEIGHTS, attention_history=history
        )
        enhanced = sector_metrics(
            self.articles, ENHANCED_WEIGHTS, attention_history=history
        )
        baseline_attention = baseline.loc[
            baseline["sector"].eq("Technology"), "attention"
        ].iloc[0]
        enhanced_attention = enhanced.loc[
            enhanced["sector"].eq("Technology"), "attention"
        ].iloc[0]
        self.assertNotEqual(float(baseline_attention), float(enhanced_attention))

    def test_snapshot_dual_write_and_legacy_marking(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sector_path = root / "sector.csv"
            market_path = root / "market.csv"
            old_row = {
                "snapshot_date": "2026-01-01",
                "snapshot_timestamp": "2026-01-01T00:00:00+00:00",
                "data_source": "真实新闻",
                "article_count": 1,
                "optimism": 1,
            }
            pd.DataFrame([{**old_row, "sector": "Technology"}]).to_csv(
                sector_path, index=False
            )
            pd.DataFrame([old_row]).to_csv(market_path, index=False)

            records = self.articles.to_dict("records")
            with patch.object(daily_snapshots, "SECTOR_DAILY_SCORES_PATH", sector_path), patch.object(
                daily_snapshots, "MARKET_DAILY_SCORES_PATH", market_path
            ):
                result = daily_snapshots.write_daily_snapshots(records, "真实新闻")

            sectors = pd.read_csv(sector_path)
            markets = pd.read_csv(market_path)
            today = datetime.now(UTC).date().isoformat()
            sector_today = sectors[sectors["snapshot_date"].astype(str).eq(today)]
            market_today = markets[markets["snapshot_date"].astype(str).eq(today)]
            self.assertEqual(result["sector_rows"], 22)
            self.assertEqual(
                set(sector_today["formula_version"]),
                {FORMULA_VERSION_BASELINE, FORMULA_VERSION_ENHANCED},
            )
            self.assertEqual(
                set(market_today["formula_version"]),
                {FORMULA_VERSION_BASELINE, FORMULA_VERSION_ENHANCED},
            )
            legacy = sectors[sectors["snapshot_date"].astype(str).eq("2026-01-01")]
            self.assertEqual(set(legacy["formula_version"]), {FORMULA_VERSION_BASELINE})
            self.assertEqual(set(legacy["pipeline_revision"]), {"r1"})
            self.assertEqual(set(sector_today["pipeline_revision"]), {PIPELINE_REVISION})


if __name__ == "__main__":
    unittest.main()
