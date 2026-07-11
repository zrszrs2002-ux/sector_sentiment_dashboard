from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

import pandas as pd

from src.driver_analysis import collapse_articles_by_event
from src.event_clustering import cluster_articles, event_groups
from src.scoring import calculate_risk_intensity
from src.sentiment_model import ArticleSentiment
from src.topic_risk_tagger import tag_article


def sentiment(score: float = 0.0) -> ArticleSentiment:
    return ArticleSentiment(
        p_positive=0.2,
        p_neutral=0.6,
        p_negative=0.2,
        sentiment_score=score,
        model_confidence=0.6,
        evidence_sentence="",
        sentence_results=[],
    )


def event_record(article_id: str, hours: int, score: float = 0.0) -> dict[str, str]:
    published = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=hours)
    return {
        "article_id": article_id,
        "title": "Apple and Broadcom announce a custom chip supply partnership",
        "summary": "The companies signed a semiconductor supply agreement for new chips.",
        "tickers": "AAPL;AVGO",
        "sector": "Technology",
        "published_at": published.isoformat(),
        "sentiment_score": str(score),
        "agg_weight": "1.0",
        "source": "Yahoo Finance RSS",
    }


class SignalQualityTests(unittest.TestCase):
    def test_no_risk_and_single_weak_macro_hit_are_zero(self) -> None:
        no_risk = tag_article("The company opened a new office and named a director.")
        one_weak = tag_article("Inflation was mentioned in the quarterly update.")
        self.assertEqual(no_risk.risk_category, "")
        self.assertEqual(one_weak.risk_category, "")
        self.assertEqual(calculate_risk_intensity("", sentiment(), {}), 0.0)

    def test_two_distinct_weak_macro_terms_trigger(self) -> None:
        tagged = tag_article(
            "Inflation remained elevated. Consumer weakness added to the cautious outlook."
        )
        self.assertIn("macro risk", tagged.risk_category.split(";"))
        self.assertGreater(tagged.risk_strengths["macro risk"], 0)

    def test_multilabel_risk_formula_sums_density_weighted_severity(self) -> None:
        score = calculate_risk_intensity(
            "liquidity risk;regulatory risk",
            sentiment(),
            {"liquidity risk": 0.5, "regulatory risk": 0.25},
        )
        self.assertAlmostEqual(score, 70.0)

    def test_cluster_span_breaks_transitive_chain(self) -> None:
        records = [event_record("a", 0), event_record("b", 40), event_record("c", 80)]
        result = cluster_articles(records, engine="lexical")
        sizes = sorted(len(members) for members in event_groups(result.records).values())
        self.assertEqual(sizes, [1, 2])

    def test_polarity_guard_blocks_opposite_reports(self) -> None:
        records = [event_record("positive", 0, 0.8), event_record("negative", 1, -0.8)]
        result = cluster_articles(records, engine="lexical")
        self.assertEqual(len(event_groups(result.records)), 2)

    def test_source_count_splits_semicolon_and_ignores_stale_count(self) -> None:
        df = pd.DataFrame(
            [
                {
                    **event_record("a", 0),
                    "event_id": "event",
                    "source": "Yahoo Finance RSS;CNBC Top News RSS",
                    "source_count": 9,
                },
                {
                    **event_record("b", 1),
                    "event_id": "event",
                    "source": "Yahoo Finance RSS",
                    "source_count": 9,
                },
            ]
        )
        collapsed = collapse_articles_by_event(df)
        self.assertEqual(int(collapsed.iloc[0]["source_count"]), 2)


if __name__ == "__main__":
    unittest.main()
