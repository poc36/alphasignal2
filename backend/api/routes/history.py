from __future__ import annotations

from fastapi import APIRouter

from core.services import service
from models.schemas import SignalListResponse


router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("/{symbol}", response_model=SignalListResponse)
async def signal_history(symbol: str, days: int = 30, limit: int = 100):
    return SignalListResponse(signals=service.get_signal_history(symbol, days=days, limit=limit))
