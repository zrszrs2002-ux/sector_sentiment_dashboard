from __future__ import annotations

import unittest
from datetime import UTC, datetime
from unittest.mock import patch

import pandas as pd

from src.article_pipeline import article_text, enrich_record, merge_tag_results, sentiment_content
from src.brief_builder import _drivers
from src.driver_analysis import collapse_articles_by_event
from src.fulltext_fetcher import select_fulltext_candidates
from src.news_collector import FeedConfig, entry_publisher
from src.rss_sources import distinct_value_count, enabled_rss_sources, source_weight_for_names
from src.scoring import score_article
from src.sentiment_model import ArticleSentiment, SentenceSentiment
from src.topic_risk_tagger import TagResult


class DataSourceAndFulltextTests(unittest.TestCase):
    def test_external_source_config_contract(self) -> None:
        sources = enabled_rss_sources()
        self.assertEqual(len(sources), 20)
        self.assertTrue(any(source.kind == "ticker_template" for source in sources))
        self.assertTrue(all(0 < source.source_weight <= 1 for source in sources))
        self.assertTrue(all(source.max_entries > 0 for source in sources))

    def test_entry_publisher_and_fallback(self) -> None:
        config = FeedConfig("Google News Business RSS", "https://example.com", 0.8, 30, False)
        self.assertEqual(entry_publisher({"source": {"title": "Reuters"}}, config.source), "Reuters")
        self.assertEqual(entry_publisher({}, config.source), config.source)

    def test_source_weight_enters_aggregation_weight(self) -> None:
        timestamp = "2026-01-01T00:00:00+00:00"
        sentiment = ArticleSentiment(0.2, 0.6, 0.2, 0.0, 0.6, "", [])
        scores = score_article(
            sentiment=sentiment,
            risk_category="",
            published_at=timestamp,
            collected_at=timestamp,
            relevance_weight=1.0,
            dedup_factor=1.0,
            source_weight=0.8,
        )
        self.assertEqual(scores["source_weight"], "0.800")
        self.assertEqual(scores["agg_weight"], "0.800000")
        self.assertEqual(source_weight_for_names("Google News Business RSS"), 0.8)

    def test_event_source_count_uses_publishers(self) -> None:
        df = pd.DataFrame(
            [
                {"article_id": "a", "event_id": "e", "source": "Google", "publisher": "Reuters", "agg_weight": 1, "published_at": "2026-01-01", "url": ""},
                {"article_id": "b", "event_id": "e", "source": "Google", "publisher": "AP", "agg_weight": 0.9, "published_at": "2026-01-01", "url": ""},
            ]
        )
        collapsed = collapse_articles_by_event(df)
        self.assertEqual(int(collapsed.iloc[0]["source_count"]), 2)
        self.assertEqual(distinct_value_count(["", "Reuters"], ["Yahoo", "Google"]), 2)

    def test_brief_prefers_fulltext_evidence(self) -> None:
        source_df = pd.DataFrame(
            [
                {
                    "article_id": "summary",
                    "event_id": "event",
                    "content_level": "summary",
                    "evidence_sentence": "summary evidence",
                    "agg_weight": 1.0,
                },
                {
                    "article_id": "fulltext",
                    "event_id": "event",
                    "content_level": "fulltext",
                    "evidence_sentence": "fulltext evidence",
                    "agg_weight": 0.9,
                },
            ]
        )
        driver = pd.DataFrame(
            [
                {
                    "article_id": "summary",
                    "event_id": "event",
                    "title": "Driver",
                    "sector": "Technology",
                    "driver_reason": "reason",
                    "evidence_sentence": "summary evidence",
                    "url": "https://example.com",
                    "source_count": 2,
                    "event_article_count": 2,
                }
            ]
        )
        with patch("src.brief_builder.top_driver_articles", return_value=driver):
            rows = _drivers(source_df)
        self.assertEqual(rows[0]["evidence_sentence"], "fulltext evidence")

    def test_candidate_selection_respects_cache_and_paywall(self) -> None:
        published = datetime.now(UTC).isoformat(timespec="seconds")
        base = {
            "event_id": "",
            "published_at": published,
            "sector": "Technology",
            "topic": "AI demand",
            "risk_intensity": "70",
            "sentiment_score": "0.7",
            "agg_weight": "1",
            "uncertainty": "20",
            "content_level": "summary",
            "evidence_sentence": "evidence",
        }
        records = [
            {**base, "article_id": "allowed", "title": "Allowed", "url": "https://cnbc.com/a", "source": "CNBC Top News RSS"},
            {**base, "article_id": "paywall", "title": "Paywall", "url": "https://nytimes.com/b", "source": "NYT Business RSS"},
            {**base, "article_id": "cached", "title": "Cached", "url": "https://cnbc.com/c", "source": "CNBC Top News RSS"},
        ]
        selected = select_fulltext_candidates(records, {"cached": {"status": "failed"}})
        self.assertEqual([record["article_id"] for record in selected], ["allowed"])

        duplicate = {**records[0], "article_id": "duplicate", "url": "https://cnbc.com/other"}
        selected = select_fulltext_candidates([records[0], duplicate], {})
        self.assertEqual(len(selected), 1)

    def test_article_text_prefers_body_without_exposing_content_field(self) -> None:
        record = {"title": "Title", "summary": "Summary", "content": "Summary", "body_text": "Full body."}
        text = article_text(record)
        self.assertIn("Full body", text)
        self.assertEqual(record["content"], "Summary")
        self.assertEqual(sentiment_content(record), "Summary")

        timestamp = "2026-01-01T00:00:00+00:00"
        record.update(
            {
                "article_id": "fulltext",
                "source": "CNBC Top News RSS",
                "publisher": "CNBC",
                "url": "https://example.com/fulltext",
                "published_at": timestamp,
                "collected_at": timestamp,
                "sector": "Technology",
                "dedup_factor": "1.0",
                "content_level": "fulltext",
                "rescored": "True",
            }
        )
        summary_sentiment = ArticleSentiment(
            0.8,
            0.1,
            0.1,
            0.7,
            0.8,
            "Summary",
            [],
        )
        body_sentence = "Full body."
        fulltext_sentiment = ArticleSentiment(
            0.1,
            0.1,
            0.8,
            -0.7,
            0.8,
            body_sentence,
            [SentenceSentiment(body_sentence, 0.1, 0.1, 0.8, -0.7, 0.8)],
        )
        enriched = enrich_record(record, summary_sentiment, fulltext_sentiment)
        self.assertEqual(enriched["sentiment_score"], "0.700")
        self.assertEqual(enriched["p_positive"], "0.800")
        self.assertEqual(enriched["optimism"], "56.0")
        self.assertEqual(enriched["fear"], "7.0")
        self.assertEqual(enriched["uncertainty"], "21.5")
        self.assertEqual(enriched["sentiment_score_fulltext"], "-0.700")
        self.assertEqual(enriched["p_negative_fulltext"], "0.800")
        self.assertEqual(enriched["evidence_sentence"], body_sentence)

        summary_tag = TagResult(
            "general market sentiment", "", "valuation", "summary risk", 3, {"valuation": 0.4}
        )
        fulltext_tag = TagResult(
            "cloud growth", "Technology", "macro risk", "body risk", 4, {"macro risk": 0.6}
        )
        merged_tag = merge_tag_results(summary_tag, fulltext_tag)
        self.assertEqual(merged_tag.topic, "cloud growth")
        self.assertEqual(merged_tag.risk_category, "valuation;macro risk")
        self.assertEqual(merged_tag.risk_strengths, {"valuation": 0.4, "macro risk": 0.6})


if __name__ == "__main__":
    unittest.main()
