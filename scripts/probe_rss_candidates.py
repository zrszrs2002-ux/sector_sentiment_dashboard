"""Probe candidate RSS endpoints without modifying project data."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import feedparser
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import RSS_REQUEST_TIMEOUT_SECONDS, RSS_USER_AGENT  # noqa: E402


CANDIDATES = [
    ("Yahoo Finance ticker template", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=NVDA&region=US&lang=en-US"),
    ("CNBC Top News", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("CNBC Markets", "https://www.cnbc.com/id/10000664/device/rss/rss.html"),
    ("CNBC Technology", "https://www.cnbc.com/id/19854910/device/rss/rss.html"),
    ("CNBC Economy", "https://www.cnbc.com/id/20910258/device/rss/rss.html"),
    ("CNBC Earnings", "https://www.cnbc.com/id/15839135/device/rss/rss.html"),
    ("CNBC Business", "https://www.cnbc.com/id/10001147/device/rss/rss.html"),
    ("MarketWatch Top Stories", "https://feeds.marketwatch.com/marketwatch/topstories/"),
    ("MarketWatch Real-time Headlines", "https://feeds.marketwatch.com/marketwatch/realtimeheadlines/"),
    ("MarketWatch Market Pulse", "https://feeds.marketwatch.com/marketwatch/marketpulse/"),
    ("Google News Business", "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en"),
    ("Google News Markets", "https://news.google.com/rss/search?q=financial%20markets%20when%3A1d&hl=en-US&gl=US&ceid=US:en"),
    ("Nasdaq Markets", "https://www.nasdaq.com/feed/rssoutbound?category=Markets"),
    ("Nasdaq Earnings", "https://www.nasdaq.com/feed/rssoutbound?category=Earnings"),
    ("Nasdaq Technology", "https://www.nasdaq.com/feed/rssoutbound?category=Technology"),
    ("Benzinga", "https://www.benzinga.com/feed"),
    ("Benzinga Markets", "https://www.benzinga.com/markets/feed"),
    ("Motley Fool", "https://www.fool.com/feeds/index.aspx?id=foolwatch&format=rss2"),
    ("Motley Fool News", "https://www.fool.com/a/feeds/foolwatch"),
    ("Investing.com Stock Market News", "https://www.investing.com/rss/news_25.rss"),
    ("Fortune", "https://fortune.com/feed/"),
    ("Fortune Finance", "https://fortune.com/section/finance/feed/"),
    ("Business Insider", "https://www.businessinsider.com/rss"),
    ("Business Insider All", "https://feeds.businessinsider.com/custom/all"),
    ("WSJ Markets Headlines", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
    ("NYT Business", "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"),
]


def main() -> None:
    results = []
    headers = {
        "User-Agent": RSS_USER_AGENT,
        "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
    }
    for name, url in CANDIDATES:
        try:
            response = requests.get(url, headers=headers, timeout=RSS_REQUEST_TIMEOUT_SECONDS)
            parsed = feedparser.parse(response.content)
            results.append(
                {
                    "name": name,
                    "url": url,
                    "status": response.status_code,
                    "content_type": response.headers.get("content-type", ""),
                    "entries": len(parsed.entries),
                    "bozo": bool(parsed.bozo),
                    "first_title": str(parsed.entries[0].get("title", "")) if parsed.entries else "",
                }
            )
        except Exception as exc:  # noqa: BLE001 - probe should report every endpoint
            results.append({"name": name, "url": url, "error": f"{type(exc).__name__}: {exc}"})
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
