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
from src.keyword_signals import keyword_signal_components, normalized_sentence_hit_score, signal_terms
from src.scoring import calculate_article_formula_values, normalized_entropy
from src.ui_helpers import _HEATMAP_COLOR_SCALES, heatmap_color_values


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

    def test_pairwise_disagreement_and_legacy_switch(self) -> None:
        baseline = sector_metrics(self.articles, BASELINE_WEIGHTS)
        enhanced = sector_metrics(self.articles, ENHANCED_WEIGHTS)
        baseline_row = baseline[baseline["sector"].eq("Technology")].iloc[0]
        enhanced_row = enhanced[enhanced["sector"].eq("Technology")].iloc[0]
        self.assertAlmostEqual(float(baseline_row["disagreement"]), 50.0)
        self.assertAlmostEqual(float(enhanced_row["disagreement"]), 50.0)
        with patch("src.aggregation.DISAGREEMENT_METHOD", "legacy_std_mix"):
            legacy = sector_metrics(self.articles, ENHANCED_WEIGHTS)
        legacy_row = legacy[legacy["sector"].eq("Technology")].iloc[0]
        self.assertAlmostEqual(float(legacy_row["disagreement"]), 75.0)
        self.assertAlmostEqual(
            float(baseline_row["risk_intensity"]),
            float(enhanced_row["risk_intensity"]),
        )

    def test_event_risk_representatives_and_weighted_p90(self) -> None:
        now = pd.Timestamp.now(tz="UTC")
        records = [
            {**self.articles.iloc[0].to_dict(), "article_id": "event-a-main", "event_id": "event-a", "risk_intensity": 100.0, "agg_weight": 1.0},
            {**self.articles.iloc[0].to_dict(), "article_id": "event-a-repeat", "event_id": "event-a", "risk_intensity": 0.0, "agg_weight": 0.1},
            {**self.articles.iloc[0].to_dict(), "article_id": "event-b", "event_id": "event-b", "risk_intensity": 50.0, "agg_weight": 1.0},
            {**self.articles.iloc[0].to_dict(), "article_id": "event-c", "event_id": "event-c", "risk_intensity": 0.0, "agg_weight": 1.0},
        ]
        for record in records:
            record["published_at"] = now
            record["collected_at"] = now
            record["publisher"] = record["article_id"]
        metrics = sector_metrics(pd.DataFrame(records), ENHANCED_WEIGHTS)
        row = metrics[metrics["sector"].eq("Technology")].iloc[0]
        self.assertEqual(int(row["article_count"]), 4)
        self.assertEqual(int(row["event_count"]), 3)
        self.assertEqual(int(row["publisher_count"]), 4)
        self.assertAlmostEqual(float(row["risk_intensity"]), 65.0)

    def test_direction_gate_panic_terms_and_relative_heatmap_scale(self) -> None:
        signal_terms.cache_clear()
        blocked_growth = keyword_signal_components("Revenue growth slows as demand turns weak.")
        blocked_bull = keyword_signal_components("The buy rating remains, but the outlook is cut.")
        panic = keyword_signal_components("Investor anxiety triggered a flight to safety and risk-off trading.")
        positive = keyword_signal_components("Strong demand and a buy rating support growth.")
        self.assertEqual(blocked_growth["g_growth"], 0.0)
        self.assertEqual(blocked_bull["b_bull"], 0.0)
        self.assertGreater(panic["s_shock"], 0.0)
        self.assertGreater(positive["g_growth"], 0.0)
        relative = heatmap_color_values(pd.Series([20.0, 21.0, 22.0]))
        absolute = heatmap_color_values(pd.Series([20.0, 21.0, 22.0]), "absolute")
        self.assertEqual(relative.tolist(), [0.0, 50.0, 100.0])
        self.assertEqual(absolute.tolist(), [20.0, 21.0, 22.0])

    def test_heatmap_color_scales_are_mode_specific(self) -> None:
        self.assertEqual(set(_HEATMAP_COLOR_SCALES), {"relative", "absolute"})
        expected_metrics = {
            "optimism",
            "fear",
            "uncertainty",
            "attention",
            "disagreement",
            "risk_intensity",
        }
        for mode in ("relative", "absolute"):
            self.assertEqual(set(_HEATMAP_COLOR_SCALES[mode]), expected_metrics)
            self.assertEqual(_HEATMAP_COLOR_SCALES[mode]["optimism"], "Greens")
        self.assertEqual(_HEATMAP_COLOR_SCALES["relative"]["fear"], "RdYlGn_r")
        self.assertEqual(_HEATMAP_COLOR_SCALES["absolute"]["fear"], "Reds")

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
            self.assertTrue(legacy["event_count"].isna().all())
            self.assertTrue(legacy["publisher_count"].isna().all())
            self.assertEqual(set(sector_today["pipeline_revision"]), {PIPELINE_REVISION})
            technology_today = sector_today[sector_today["sector"].astype(str).eq("Technology")]
            self.assertTrue((pd.to_numeric(technology_today["event_count"], errors="coerce") > 0).all())
            self.assertTrue((pd.to_numeric(technology_today["publisher_count"], errors="coerce") > 0).all())

            daily_snapshots._upsert_rows(
                sector_path,
                daily_snapshots.SECTOR_SNAPSHOT_FIELDS,
                [{**sector_today.iloc[0].to_dict(), "pipeline_revision": "r2"}],
                ["snapshot_date", "data_source", "formula_version", "pipeline_revision", "sector"],
            )
            preserved = pd.read_csv(sector_path)
            preserved_today = preserved[preserved["snapshot_date"].astype(str).eq(today)]
            self.assertIn("r2", set(preserved_today["pipeline_revision"]))
            self.assertIn(PIPELINE_REVISION, set(preserved_today["pipeline_revision"]))


if __name__ == "__main__":
    unittest.main()
