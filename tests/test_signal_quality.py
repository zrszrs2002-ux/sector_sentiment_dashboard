from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

import pandas as pd

from src.driver_analysis import collapse_articles_by_event, top_driver_articles
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



def driver_record(article_id: str, published: datetime, risk: float = 0.0) -> dict[str, object]:
    return {
        "article_id": article_id,
        "event_id": f"event-{article_id}",
        "title": article_id,
        "sector": "Technology",
        "published_at": published.isoformat(),
        "risk_intensity": risk,
        "sentiment_score": 0.0,
        "uncertainty": 0.0,
        "agg_weight": 1.0,
        "source": "Reuters",
        "publisher": "Reuters",
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

    def test_top_drivers_exclude_old_high_risk_news_in_48_hour_window(self) -> None:
        now = datetime(2026, 7, 13, 12, tzinfo=UTC)
        df = pd.DataFrame(
            [
                driver_record("old-high-risk", now - timedelta(days=5), risk=100),
                driver_record("fresh-ordinary", now - timedelta(hours=1)),
            ]
        )
        drivers = top_driver_articles(
            df,
            window_hours=48,
            min_events=1,
            reference_time=now,
        )
        self.assertEqual(drivers.attrs["driver_window_hours"], 48)
        self.assertEqual(drivers["article_id"].tolist(), ["fresh-ordinary"])

    def test_top_drivers_expand_window_when_48_hours_has_too_few_events(self) -> None:
        now = datetime(2026, 7, 13, 12, tzinfo=UTC)
        df = pd.DataFrame(
            [
                driver_record("fresh-1", now - timedelta(hours=1)),
                driver_record("fresh-2", now - timedelta(hours=2)),
                driver_record("expanded-1", now - timedelta(hours=60)),
                driver_record("expanded-2", now - timedelta(hours=65)),
                driver_record("expanded-3", now - timedelta(hours=70)),
                driver_record("too-old", now - timedelta(hours=180), risk=100),
            ]
        )
        drivers = top_driver_articles(
            df,
            window_hours=48,
            min_events=5,
            reference_time=now,
        )
        self.assertEqual(drivers.attrs["driver_window_hours"], 72)
        self.assertEqual(
            set(drivers["article_id"]),
            {"fresh-1", "fresh-2", "expanded-1", "expanded-2", "expanded-3"},
        )

    def test_top_drivers_30_day_window_does_not_expand(self) -> None:
        now = datetime(2026, 7, 13, 12, tzinfo=UTC)
        df = pd.DataFrame(
            [
                driver_record("within-30-days", now - timedelta(days=29)),
                driver_record("outside-30-days", now - timedelta(days=31), risk=100),
            ]
        )
        drivers = top_driver_articles(
            df,
            window_hours=30 * 24,
            min_events=5,
            reference_time=now,
        )
        self.assertEqual(drivers.attrs["driver_window_hours"], 30 * 24)
        self.assertEqual(drivers["article_id"].tolist(), ["within-30-days"])

    def test_macro_guarantee_is_included_but_keeps_score_order(self) -> None:
        now = datetime(2026, 7, 13, 12, tzinfo=UTC)
        regular = [
            driver_record("regular-1", now - timedelta(hours=1), risk=100),
            driver_record("regular-2", now - timedelta(hours=2), risk=75),
            driver_record("regular-3", now - timedelta(hours=3), risk=50),
            driver_record("regular-4", now - timedelta(hours=4), risk=25),
            driver_record("regular-5", now - timedelta(hours=5), risk=10),
        ]
        macro = driver_record("macro-low", now - timedelta(hours=6))
        macro["sector"] = "Unmapped"
        drivers = top_driver_articles(
            pd.DataFrame([*regular, macro]),
            window_hours=48,
            min_events=5,
            reference_time=now,
        )
        scores = drivers["driver_score"].tolist()
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(drivers.iloc[-1]["article_id"], "macro-low")
        self.assertTrue(bool(drivers.iloc[-1]["macro_guaranteed"]))
        self.assertIn("macro-low", set(drivers["article_id"]))


if __name__ == "__main__":
    unittest.main()
