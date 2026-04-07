from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from config import settings


class SignalDraft(BaseModel):
    signal: str = Field(description="Trading signal decision: BUY, SELL, or HOLD.")
    confidence: int = Field(description="Confidence score from 0 to 100.", ge=0, le=100)
    sentiment: str = Field(description="Positive, Negative, or Neutral.")
    summary: str = Field(description="A concise 2-3 sentence rationale.")
    sources: list[str] = Field(description="A list of source URLs used in the answer.")


class AnswerGenerator:
    def __init__(self) -> None:
        self.provider = settings.llm_provider.lower()
        self.gemini_api_key = settings.gemini_api_key
        self.model = settings.gemini_model if self.provider == "gemini" else settings.llm_model
        self.last_error: str | None = None

    async def generate_signal(
        self,
        ticker: str,
        contexts: list[dict],
        fallback_summary: str,
        fallback_sources: list[str],
    ) -> SignalDraft | None:
        if self.provider != "gemini" or not self.gemini_api_key or not contexts:
            return None
        return await asyncio.to_thread(self._generate_signal_sync, ticker, contexts, fallback_summary, fallback_sources)

    async def answer(self, query: str, contexts: list[dict], ticker: str | None = None) -> tuple[str, float]:
        if not contexts:
            subject = ticker.upper() if ticker else "the requested company"
            return (
                f"I do not have enough retrieved context for {subject} yet. Ingest more articles or generate a fresh signal and try again.",
                0.24,
            )

        if self.provider == "gemini" and self.gemini_api_key:
            gemini_answer = await asyncio.to_thread(self._answer_sync, query, contexts, ticker)
            if gemini_answer:
                return gemini_answer

        joined_context = " ".join(item["content"] for item in contexts[:5])
        subject = ticker.upper() if ticker else "the company"
        answer = (
            f"AlphaSignal view for {subject}: {joined_context[:700]} "
            f"Answer synthesized from the top retrieved chunks for the question: {query}"
        )
        confidence = min(0.95, 0.45 + len(contexts) * 0.1)
        return answer, round(confidence, 2)

    def _answer_sync(self, query: str, contexts: list[dict], ticker: str | None) -> tuple[str, float] | None:
        try:
            from google import genai
        except Exception:
            return None

        prompt = self._build_answer_prompt(query, contexts, ticker)
        try:
            client = genai.Client(api_key=self.gemini_api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
            )
            text = (response.text or "").strip()
            if not text:
                return None
            self.last_error = None
            return text, min(0.97, 0.55 + len(contexts) * 0.08)
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            return None

    def _generate_signal_sync(
        self,
        ticker: str,
        contexts: list[dict],
        fallback_summary: str,
        fallback_sources: list[str],
    ) -> SignalDraft | None:
        try:
            from google import genai
        except Exception:
            return None

        prompt = self._build_signal_prompt(ticker, contexts, fallback_summary, fallback_sources)
        try:
            client = genai.Client(api_key=self.gemini_api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": SignalDraft,
                },
            )
            parsed = getattr(response, "parsed", None)
            if isinstance(parsed, SignalDraft):
                self.last_error = None
                return parsed
            if isinstance(parsed, dict):
                self.last_error = None
                return SignalDraft(**parsed)
            return None
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            return None

    @staticmethod
    def _build_answer_prompt(query: str, contexts: list[dict], ticker: str | None) -> str:
        subject = ticker.upper() if ticker else "the company"
        context_text = "\n\n".join(
            f"Source: {item.get('source_name', 'Unknown')} | URL: {item.get('source_url', '')}\n{item.get('content', '')}"
            for item in contexts[:5]
        )
        return (
            f"You are AlphaSignal, an AI trading research assistant.\n"
            f"Answer the question about {subject} using only the supplied context. "
            f"Be concise, balanced, and mention risks when relevant.\n\n"
            f"Question: {query}\n\nContext:\n{context_text}"
        )

    @staticmethod
    def _build_signal_prompt(ticker: str, contexts: list[dict], fallback_summary: str, fallback_sources: list[str]) -> str:
        context_text = "\n\n".join(
            f"Source: {item.get('source_name', 'Unknown')} | URL: {item.get('source_url', '')}\n{item.get('content', '')}"
            for item in contexts[:5]
        )
        return (
            f"You are generating a trading signal for {ticker}.\n"
            f"Return BUY, SELL, or HOLD with a confidence score, sentiment label, short summary, and sources.\n"
            f"If the evidence is mixed, prefer HOLD.\n\n"
            f"Fallback summary:\n{fallback_summary}\n\n"
            f"Fallback sources:\n{fallback_sources}\n\n"
            f"Context:\n{context_text}"
        )
