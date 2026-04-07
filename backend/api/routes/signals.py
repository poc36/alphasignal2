from __future__ import annotations

from fastapi import APIRouter

from core.services import service
from models.schemas import GenerateSignalRequest, GenerateSignalResponse, SignalListResponse


router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get("", response_model=SignalListResponse)
async def get_signals(ticker: str | None = None, limit: int = 50):
    return SignalListResponse(signals=service.list_signals(ticker=ticker, limit=limit))


@router.post("/generate", response_model=GenerateSignalResponse)
async def generate_signal(request: GenerateSignalRequest):
    return await service.generate_signal(request.ticker)
