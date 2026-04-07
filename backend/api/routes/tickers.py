from __future__ import annotations

from fastapi import APIRouter

from core.services import service
from models.schemas import TickerHistoryResponse


router = APIRouter(prefix="/api/tickers", tags=["tickers"])


@router.get("/{symbol}", response_model=TickerHistoryResponse)
async def ticker_history(symbol: str):
    history = service.list_signals(ticker=symbol.upper(), limit=30)
    latest = history[0] if history else None
    return TickerHistoryResponse(
        ticker=symbol.upper(),
        latest_signal=latest,
        history=history,
        total=len(history),
    )
