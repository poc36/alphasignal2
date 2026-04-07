from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import httpx


CIK_BY_TICKER = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "NVDA": "0001045810",
    "TSLA": "0001318605",
    "GOOGL": "0001652044",
}


@dataclass
class SECFiling:
    ticker: str
    title: str
    content: str
    source_url: str
    published_at: datetime | None


class SECFetcher:
    def __init__(self) -> None:
        self.client = httpx.AsyncClient(
            timeout=20.0,
            headers={"User-Agent": "AlphaSignal/1.0 research prototype"},
        )

    async def fetch_recent_filings(self, ticker: str) -> list[SECFiling]:
        cik = CIK_BY_TICKER.get(ticker.upper())
        if not cik:
            return []

        url = f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            payload = response.json()
        except Exception:
            return []

        forms = payload.get("filings", {}).get("recent", {})
        results: list[SECFiling] = []
        for idx, form in enumerate(forms.get("form", [])[:5]):
            if form not in {"10-Q", "10-K"}:
                continue
            accession = forms["accessionNumber"][idx].replace("-", "")
            primary_doc = forms["primaryDocument"][idx]
            filing_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{primary_doc}"
            filing_date = forms.get("filingDate", [None])[idx]
            results.append(
                SECFiling(
                    ticker=ticker.upper(),
                    title=f"{ticker.upper()} {form}",
                    content=f"Recent SEC filing detected for {ticker.upper()}: {form}. Filing date: {filing_date}.",
                    source_url=filing_url,
                    published_at=datetime.fromisoformat(filing_date) if filing_date else None,
                )
            )
        return results

    async def close(self) -> None:
        await self.client.aclose()
