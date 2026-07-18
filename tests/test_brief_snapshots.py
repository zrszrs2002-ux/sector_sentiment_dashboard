from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

import pandas as pd

from src.brief_builder import (
    _previous_market_snapshot,
    _previous_sector_snapshots,
    _sector_movers,
)
from src.config import METRIC_COLUMNS, PIPELINE_REVISION


def _metric_values(value: float) -> dict[str, float]:
    return {metric: value for metric in METRIC_COLUMNS}


class BriefSnapshotSelectionTests(unittest.TestCase):
    snapshot_date = date(2026, 7, 18)
    previous_date = date(2026, 7, 12)

    def test_sector_snapshots_prefer_active_pipeline_and_latest_fallback(self) -> None:
        rows = pd.DataFrame(
            [
                {
                    "snapshot_date": self.previous_date,
                    "snapshot_timestamp": "2026-07-12T20:20:15+00:00",
                    "pipeline_revision": "r3",
                    "sector": "Technology",
                    **_metric_values(10.0),
                },
                {
                    "snapshot_date": self.previous_date,
                    "snapshot_timestamp": "2026-07-12T21:36:52+00:00",
                    "pipeline_revision": PIPELINE_REVISION,
                    "sector": "Technology",
                    **_metric_values(20.0),
                },
                {
                    "snapshot_date": self.previous_date,
                    "snapshot_timestamp": "2026-07-12T19:00:00+00:00",
                    "pipeline_revision": "r2",
                    "sector": "Energy",
                    **_metric_values(3.0),
                },
                {
                    "snapshot_date": self.previous_date,
                    "snapshot_timestamp": "2026-07-12T22:00:00+00:00",
                    "pipeline_revision": "r3",
                    "sector": "Energy",
                    **_metric_values(5.0),
                },
            ]
        )
        with patch("src.brief_builder.load_sector_snapshots", return_value=rows):
            selected = _previous_sector_snapshots("真实新闻", self.snapshot_date)

        self.assertFalse(selected["sector"].duplicated().any())
        selected_by_sector = selected.set_index("sector")
        self.assertEqual(
            selected_by_sector.loc["Technology", "pipeline_revision"],
            PIPELINE_REVISION,
        )
        self.assertEqual(selected_by_sector.loc["Energy", "pipeline_revision"], "r3")

        current = pd.DataFrame(
            [
                {"sector": "Technology", **_metric_values(30.0)},
                {"sector": "Energy", **_metric_values(8.0)},
            ]
        )
        movers = {item["sector"]: item for item in _sector_movers(current, rows)}
        self.assertEqual(movers["Technology"]["metric_changes"]["optimism"], 10.0)
        self.assertEqual(movers["Energy"]["metric_changes"]["optimism"], 3.0)

    def test_market_snapshot_prefers_active_pipeline_on_latest_date(self) -> None:
        rows = pd.DataFrame(
            [
                {
                    "snapshot_date": date(2026, 7, 11),
                    "snapshot_timestamp": "2026-07-11T23:00:00+00:00",
                    "pipeline_revision": PIPELINE_REVISION,
                    **_metric_values(99.0),
                },
                {
                    "snapshot_date": self.previous_date,
                    "snapshot_timestamp": "2026-07-12T20:20:15+00:00",
                    "pipeline_revision": "r3",
                    **_metric_values(10.0),
                },
                {
                    "snapshot_date": self.previous_date,
                    "snapshot_timestamp": "2026-07-12T21:36:52+00:00",
                    "pipeline_revision": PIPELINE_REVISION,
                    **_metric_values(20.0),
                },
            ]
        )
        with patch("src.brief_builder.load_market_snapshots", return_value=rows):
            selected = _previous_market_snapshot("真实新闻", self.snapshot_date)

        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected["snapshot_date"], self.previous_date)
        self.assertEqual(selected["pipeline_revision"], PIPELINE_REVISION)
        self.assertEqual(selected["optimism"], 20.0)


if __name__ == "__main__":
    unittest.main()
