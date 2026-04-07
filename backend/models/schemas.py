from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


SignalType = Literal["BUY", "SELL", "HOLD"]
SentimentLabel = Literal["Positive", "Negative", "Neutral"]


class SignalOut(BaseModel):
    id: str
    ticker: str
    signal: SignalType
    confidence: int = Field(ge=0, le=100)
    sentiment: SentimentLabel
    summary: str
    sources: list[str]
    created_at: datetime


class SignalListResponse(BaseModel):
    signals: list[SignalOut]


class GenerateSignalRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)


class GenerateSignalResponse(SignalOut):
    pass


class ChatRequest(BaseModel):
    query: str = Field(min_length=5, max_length=2000)
    ticker: str | None = Field(default=None, max_length=10)


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


class TickerHistoryResponse(BaseModel):
    ticker: str
    latest_signal: SignalOut | None
    history: list[SignalOut]
    total: int


class IngestedArticle(BaseModel):
    id: str
    ticker: str
    title: str
    content: str
    source_url: str
    source_name: str
    published_at: datetime | None


class HealthResponse(BaseModel):
    status: str
    database: str
    vector_store: str
    scheduler_running: bool
    timestamp: datetime


class ArticleOut(BaseModel):
    id: str
    ticker: str
    title: str
    source_name: str
    source_url: str
    published_at: datetime | None
    ingested_at: datetime


class IngestionStatusResponse(BaseModel):
    scheduler_running: bool
    interval_hours: int
    tracked_tickers: list[str]
    signal_count: int
    article_count: int
    llm_provider: str
    llm_model: str
    llm_last_error: str | None
    vector_backend: str
