from __future__ import annotations

import unittest
import warnings

import pandas as pd
from pandas.testing import assert_frame_equal, assert_series_equal

from src.config import (
    ENHANCED_WEIGHTS,
    METRIC_COLUMNS,
    SENSITIVITY_PERTURBATION_FACTORS,
)
from src.sensitivity_analysis import (
    _daily_spearman,
    compute_sensitivity_analysis,
    perturb_dimension_weights,
    recompute_sector_day_scores,
)


class SensitivityAnalysisTests(unittest.TestCase):
    def test_daily_spearman_handles_constant_ranking_without_warning(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            correlation = _daily_spearman(
                pd.Series([1.0, 1.0, 1.0]),
                pd.Series([3.0, 2.0, 1.0]),
            )

        self.assertEqual(correlation, 0.0)

    def setUp(self) -> None:
        rows: list[dict[str, object]] = []
        sectors = [
            ("Technology", 0.70, 0.10, 0.20, 0.10, 0.20),
            ("Financials", 0.30, 0.50, 0.90, 0.40, 0.20),
            ("Health Care", 0.50, 0.20, 0.10, 0.80, 0.70),
        ]
        for day_index, day in enumerate(
            pd.date_range("2026-01-01", periods=3, tz="UTC")
        ):
            for sector_index, (
                sector,
                p_positive,
                p_negative,
                b_bull,
                g_growth,
                k_unc,
            ) in enumerate(sectors):
                for article_index in range(3):
                    article_id = (
                        f"d{day_index}-s{sector_index}-a{article_index}"
                    )
                    positive = p_positive + article_index * 0.01
                    negative = p_negative + article_index * 0.01
                    neutral = 1.0 - positive - negative
                    rows.append(
                        {
                            "article_id": article_id,
                            "event_id": article_id,
                            "source": f"source-{article_index}",
                            "publisher": f"publisher-{article_index}",
                            "sector": sector,
                            "published_at": day
                            + pd.Timedelta(hours=article_index),
                            "collected_at": day + pd.Timedelta(hours=4),
                            "p_positive": positive,
                            "p_neutral": neutral,
                            "p_negative": negative,
                            "b_bull": b_bull,
                            "b_bear": 1.0 - b_bull,
                            "g_growth": g_growth,
                            "s_shock": 0.1 + 0.2 * article_index,
                            "k_unc": k_unc,
                            "entropy_norm": 0.4 + 0.1 * article_index,
                            "sentiment_score": positive - negative,
                            "risk_intensity": 10.0 + 35.0 * article_index,
                            "agg_weight": 1.0 - 0.2 * article_index,
                        }
                    )
        self.articles = pd.DataFrame(rows)

    def test_factor_one_matches_default_scores_exactly(self) -> None:
        expected = recompute_sector_day_scores(
            self.articles,
            ENHANCED_WEIGHTS,
        )
        for dimension, components in ENHANCED_WEIGHTS.items():
            for component in components:
                weights = perturb_dimension_weights(
                    dimension,
                    component,
                    1.0,
                )
                actual = recompute_sector_day_scores(
                    self.articles,
                    weights,
                )
                assert_frame_equal(expected, actual, check_exact=True)

    def test_perturbed_dimension_weights_are_renormalized(self) -> None:
        factors = (*SENSITIVITY_PERTURBATION_FACTORS, 1.0)
        for dimension, components in ENHANCED_WEIGHTS.items():
            for component in components:
                for factor in factors:
                    weights = perturb_dimension_weights(
                        dimension,
                        component,
                        factor,
                    )
                    self.assertAlmostEqual(
                        sum(weights[dimension].values()),
                        1.0,
                        places=12,
                    )
                    for other_dimension in ENHANCED_WEIGHTS:
                        if other_dimension != dimension:
                            self.assertEqual(
                                weights[other_dimension],
                                ENHANCED_WEIGHTS[other_dimension],
                            )

    def test_perturbation_leaves_other_five_dimensions_unchanged(self) -> None:
        default_scores = recompute_sector_day_scores(
            self.articles,
            ENHANCED_WEIGHTS,
        )
        for dimension, components in ENHANCED_WEIGHTS.items():
            component = next(iter(components))
            weights = perturb_dimension_weights(
                dimension,
                component,
                0.5,
            )
            perturbed_scores = recompute_sector_day_scores(
                self.articles,
                weights,
            )
            for metric in METRIC_COLUMNS:
                if metric != dimension:
                    assert_series_equal(
                        default_scores[metric],
                        perturbed_scores[metric],
                        check_exact=True,
                    )

        optimism_weights = perturb_dimension_weights(
            "optimism",
            "p_positive",
            0.0,
        )
        optimism_scores = recompute_sector_day_scores(
            self.articles,
            optimism_weights,
        )
        self.assertFalse(
            default_scores["optimism"].equals(
                optimism_scores["optimism"]
            )
        )

    def test_compute_rejects_demo_data_source(self) -> None:
        with self.assertRaisesRegex(ValueError, "严禁使用 Demo 数据"):
            compute_sensitivity_analysis(
                self.articles,
                data_source="processed_articles.csv",
                factors=(1.0,),
            )


if __name__ == "__main__":
    unittest.main()
