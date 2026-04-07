from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime

import feedparser
import httpx

from config import settings


RSS_SOURCES = [
    ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
    ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
    ("Bloomberg Markets", "https://feeds.bloomberg.com/markets/news.rss"),
]


@dataclass
class RSSArticle:
    ticker: str
    title: str
    content: str
    source_url: str
    source_name: str
    published_at: datetime | None
    content_hash: str


class RSSParser:
    def __init__(self) -> None:
        self.client = httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": "AlphaSignal/1.0"},
            follow_redirects=True,
        )

    async def fetch_articles(self) -> list[RSSArticle]:
        articles: list[RSSArticle] = []
        for source_name, url in RSS_SOURCES:
            try:
                response = await self.client.get(url)
                response.raise_for_status()
                feed = feedparser.parse(response.text)
                for entry in feed.entries[:10]:
                    title = entry.get("title", "").strip()
                    summary = entry.get("summary", "").strip()
                    link = entry.get("link", "").strip()
                    if not title or not link:
                        continue

                    content = f"{title}\n\n{summary}".strip()
                    ticker = self._extract_ticker(content)
                    articles.append(
                        RSSArticle(
                            ticker=ticker,
                            title=title,
                            content=content[:8000],
                            source_url=link,
                            source_name=source_name,
                            published_at=self._parse_date(entry.get("published")),
                            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                        )
                    )
            except Exception:
                continue
        return articles

    async def close(self) -> None:
        await self.client.aclose()

    def _extract_ticker(self, text: str) -> str:
        for ticker in settings.supported_tickers:
            if re.search(rf"\b{re.escape(ticker.replace('-USD', ''))}\b", text.upper()):
                return ticker
        return "MARKET"

    @staticmethod
    def _parse_date(value: str | None) -> datetime | None:
        if not value:
            return None
        for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None
