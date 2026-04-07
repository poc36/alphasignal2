from __future__ import annotations

from fastapi import APIRouter

from core.services import service
from models.schemas import ChatRequest, ChatResponse


router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def ask_question(request: ChatRequest):
    answer, sources, confidence = await service.answer_question(request.query, request.ticker)
    return ChatResponse(answer=answer, sources=sources, confidence=confidence)
