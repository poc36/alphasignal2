from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Iterable
from uuid import uuid4

from sqlalchemy import desc, select

from config import settings
from core.ingestion.rss_parser import RSSArticle, RSSParser
from core.ingestion.sec_fetcher import SECFetcher
from core.rag.chunker import TextChunker
from core.rag.embedder import Embedder
from core.rag.generator import AnswerGenerator
from core.rag.retriever import Retriever
from core.signals.classifier import SignalClassifier
from mock_data import get_mock_signals
from models.database import DocumentChunk, NewsArticle, SessionLocal, SignalRecord
from models.schemas import ArticleOut, IngestionStatusResponse, SignalOut


class AlphaSignalService:
    def __init__(self) -> None:
        self.chunker = TextChunker()
        self.embedder = Embedder()
        self.retriever = Retriever()
        self.answer_generator = AnswerGenerator()
        self.classifier = SignalClassifier()
        self.rss_parser = RSSParser()
        self.sec_fetcher = SECFetcher()

    def list_signals(self, ticker: str | None = None, limit: int = 50) -> list[SignalOut]:
        with SessionLocal() as session:
            stmt = select(SignalRecord).order_by(desc(SignalRecord.created_at)).limit(limit)
            if ticker:
                stmt = (
                    select(SignalRecord)
                    .where(SignalRecord.ticker == ticker.upper())
                    .order_by(desc(SignalRecord.created_at))
                    .limit(limit)
                )
            records = session.execute(stmt).scalars().all()
            return [self._to_signal_out(record) for record in records]

    def get_signal_history(self, ticker: str, days: int = 30, limit: int = 100) -> list[SignalOut]:
        cutoff = datetime.utcnow().timestamp() - days * 24 * 60 * 60
        cutoff_dt = datetime.utcfromtimestamp(cutoff)
        with SessionLocal() as session:
            stmt = (
                select(SignalRecord)
                .where(SignalRecord.ticker == ticker.upper(), SignalRecord.created_at >= cutoff_dt)
                .order_by(desc(SignalRecord.created_at))
                .limit(limit)
            )
            records = session.execute(stmt).scalars().all()
            return [self._to_signal_out(record) for record in records]

    async def generate_signal(self, ticker: str) -> SignalOut:
        ticker = ticker.upper()
        recent = self.list_signals(ticker=ticker, limit=1)
        if recent:
            return recent[0]

        filings = await self.sec_fetcher.fetch_recent_filings(ticker)
        contexts = self.retriever.search(self.embedder.embed([ticker])[0], ticker=ticker, top_k=5)

        summary_parts = []
        sources: list[str] = []
        if contexts:
            summary_parts.append("Recent market context indicates active coverage around the company.")
            for item in contexts[:2]:
                summary_parts.append(item["content"][:180])
                if item["source_url"] and item["source_url"] not in sources:
                    sources.append(item["source_url"])
        if filings:
            summary_parts.append(f"Recent SEC filing activity includes {filings[0].title}.")
            if filings[0].source_url not in sources:
                sources.append(filings[0].source_url)

        if not summary_parts:
            summary_parts.append(
                f"{ticker} is available in demo mode. Generate more ingestion data to move from placeholder context to live research."
            )

        sentiment_score = self._sentiment_from_text(" ".join(summary_parts))
        signal_type = self.classifier.classify(sentiment_score)
        sentiment_label = self.classifier.sentiment_label(sentiment_score)
        confidence = 72 if contexts or filings else 58
        fallback_summary = " ".join(summary_parts)[:900]

        generated = await self.answer_generator.generate_signal(
            ticker=ticker,
            contexts=contexts,
            fallback_summary=fallback_summary,
            fallback_sources=sources,
        )
        if generated:
            signal_type = generated.signal if generated.signal in {"BUY", "SELL", "HOLD"} else signal_type
            sentiment_label = generated.sentiment if generated.sentiment in {"Positive", "Negative", "Neutral"} else sentiment_label
            confidence = generated.confidence
            fallback_summary = generated.summary
            sources = generated.sources or sources

        record = SignalRecord(
            id=str(uuid4()),
            ticker=ticker,
            signal_type=signal_type,
            confidence=confidence,
            sentiment=sentiment_label,
            summary=fallback_summary,
            sources=sources,
            metadata_json={
                "generated_via": "gemini" if generated else "service",
                "llm_provider": settings.llm_provider,
                "contexts": len(contexts),
                "filings": len(filings),
            },
            created_at=datetime.utcnow(),
        )
        with SessionLocal() as session:
            session.add(record)
            session.commit()
            session.refresh(record)
        return self._to_signal_out(record)

    async def answer_question(self, query: str, ticker: str | None = None) -> tuple[str, list[str], float]:
        vector = self.embedder.embed([query])[0]
        contexts = self.retriever.search(vector, ticker=ticker, top_k=5)
        answer, confidence = await self.answer_generator.answer(query, contexts, ticker)
        sources = []
        for context in contexts:
            url = context.get("source_url")
            if url and url not in sources:
                sources.append(url)
        return answer, sources, confidence

    async def ingest_all(self) -> dict:
        articles = await self.rss_parser.fetch_articles()
        added_rss = self._store_articles(articles)

        sec_articles: list[RSSArticle] = []
        for ticker in settings.supported_tickers[:5]:
            filings = await self.sec_fetcher.fetch_recent_filings(ticker)
            for filing in filings:
                content_hash = hashlib.sha256(filing.content.encode("utf-8")).hexdigest()
                sec_articles.append(
                    RSSArticle(
                        ticker=filing.ticker,
                        title=filing.title,
                        content=filing.content,
                        source_url=filing.source_url,
                        source_name="SEC EDGAR",
                        published_at=filing.published_at,
                        content_hash=content_hash,
                    )
                )
        added_sec = self._store_articles(sec_articles)
        return {"rss_articles": added_rss, "sec_filings": added_sec}

    async def seed_demo_signals(self) -> int:
        count = 0
        with SessionLocal() as session:
            for raw in get_mock_signals(count=10):
                record = SignalRecord(
                    id=str(uuid4()),
                    ticker=raw["ticker"],
                    signal_type=self.classifier.classify(raw.get("sentiment", 0.0)),
                    confidence=round(raw.get("confidence", 0.0) * 100),
                    sentiment=self.classifier.sentiment_label(raw.get("sentiment", 0.0)),
                    summary=raw["summary"],
                    sources=[raw["source_url"]] if raw.get("source_url") else [],
                    metadata_json={"demo": True, "event_type": raw.get("event_type")},
                    created_at=datetime.utcnow(),
                )
                session.add(record)
                count += 1
            session.commit()
        return count

    def list_tickers(self) -> list[str]:
        with SessionLocal() as session:
            stmt = select(SignalRecord.ticker).distinct().order_by(SignalRecord.ticker.asc())
            tickers = [row[0] for row in session.execute(stmt).all()]
        return tickers or settings.supported_tickers

    def list_articles(self, limit: int = 20) -> list[ArticleOut]:
        with SessionLocal() as session:
            stmt = select(NewsArticle).order_by(desc(NewsArticle.ingested_at)).limit(limit)
            records = session.execute(stmt).scalars().all()
            return [
                ArticleOut(
                    id=record.id,
                    ticker=record.ticker,
                    title=record.title,
                    source_name=record.source_name,
                    source_url=record.source_url,
                    published_at=record.published_at,
                    ingested_at=record.ingested_at,
                )
                for record in records
            ]

    def get_status(self, scheduler_running: bool, interval_hours: int) -> IngestionStatusResponse:
        with SessionLocal() as session:
            signal_count = session.query(SignalRecord).count()
            article_count = session.query(NewsArticle).count()
        return IngestionStatusResponse(
            scheduler_running=scheduler_running,
            interval_hours=interval_hours,
            tracked_tickers=self.list_tickers(),
            signal_count=signal_count,
            article_count=article_count,
            llm_provider=settings.llm_provider,
            llm_model=settings.gemini_model if settings.llm_provider == "gemini" else settings.llm_model,
            llm_last_error=self.answer_generator.last_error,
            vector_backend="chromadb" if self.retriever._collection is not None else "json",
        )

    def _store_articles(self, articles: Iterable[RSSArticle]) -> int:
        articles = list(articles)
        if not articles:
            return 0

        added = 0
        with SessionLocal() as session:
            for article in articles:
                exists = session.execute(
                    select(NewsArticle).where(
                        (NewsArticle.source_url == article.source_url) | (NewsArticle.content_hash == article.content_hash)
                    )
                ).scalar_one_or_none()
                if exists:
                    continue

                article_id = str(uuid4())
                db_article = NewsArticle(
                    id=article_id,
                    ticker=article.ticker,
                    title=article.title,
                    content=article.content,
                    source_url=article.source_url,
                    source_name=article.source_name,
                    published_at=article.published_at,
                    ingested_at=datetime.utcnow(),
                    content_hash=article.content_hash,
                )
                session.add(db_article)
                session.flush()

                chunks = self.chunker.split(article.content)
                embeddings = self.embedder.embed([chunk.text for chunk in chunks]) if chunks else []
                vector_items = []
                for chunk, embedding in zip(chunks, embeddings):
                    db_chunk = DocumentChunk(
                        id=str(uuid4()),
                        article_id=article_id,
                        ticker=article.ticker,
                        content=chunk.text,
                        chunk_index=chunk.index,
                        metadata_json={"title": article.title, "source_name": article.source_name},
                        created_at=datetime.utcnow(),
                    )
                    session.add(db_chunk)
                    vector_items.append(
                        {
                            "article_id": article_id,
                            "chunk_index": chunk.index,
                            "ticker": article.ticker,
                            "content": chunk.text,
                            "source_url": article.source_url,
                            "source_name": article.source_name,
                            "embedding": embedding,
                        }
                    )
                if vector_items:
                    self.retriever.upsert(vector_items)
                added += 1

            session.commit()
        return added

    def _to_signal_out(self, record: SignalRecord) -> SignalOut:
        return SignalOut(
            id=record.id,
            ticker=record.ticker,
            signal=record.signal_type,
            confidence=record.confidence,
            sentiment=record.sentiment,
            summary=record.summary,
            sources=record.sources or [],
            created_at=record.created_at,
        )

    @staticmethod
    def _sentiment_from_text(text: str) -> float:
        positive_hits = len(re.findall(r"\b(beat|growth|surge|upgrade|approval|record|strong)\b", text.lower()))
        negative_hits = len(re.findall(r"\b(miss|drop|risk|lawsuit|probe|investigation|slow)\b", text.lower()))
        total = positive_hits + negative_hits
        if total == 0:
            return 0.0
        return (positive_hits - negative_hits) / total


service = AlphaSignalService()
