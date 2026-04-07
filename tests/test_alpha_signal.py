from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from backend.core.rag.chunker import TextChunker
from backend.core.rag.retriever import Retriever
from backend.core.signals.classifier import SignalClassifier
from backend.models.schemas import ChatResponse, GenerateSignalRequest, SignalOut
from fastapi.testclient import TestClient


def test_chunker_returns_single_chunk_for_short_text():
    chunker = TextChunker(chunk_size=10, overlap=2)
    chunks = chunker.split("one two three")
    assert len(chunks) == 1


def test_chunker_creates_multiple_chunks():
    chunker = TextChunker(chunk_size=4, overlap=1)
    chunks = chunker.split("a b c d e f g h i")
    assert len(chunks) >= 2


def test_classifier_buy():
    assert SignalClassifier().classify(0.8) == "BUY"


def test_classifier_sell():
    assert SignalClassifier().classify(-0.8) == "SELL"


def test_classifier_hold():
    assert SignalClassifier().classify(0.0) == "HOLD"


def test_sentiment_label_positive():
    assert SignalClassifier().sentiment_label(0.5) == "Positive"


def test_sentiment_label_negative():
    assert SignalClassifier().sentiment_label(-0.5) == "Negative"


def test_sentiment_label_neutral():
    assert SignalClassifier().sentiment_label(0.0) == "Neutral"


def test_retriever_returns_top_match(tmp_path):
    retriever = Retriever(store_path=str(tmp_path / "vectors.json"))
    retriever.upsert(
        [
            {
                "article_id": "1",
                "chunk_index": 0,
                "ticker": "AAPL",
                "content": "Apple earnings beat expectations",
                "source_url": "https://example.com/aapl",
                "source_name": "Example",
                "embedding": [1.0, 0.0],
            },
            {
                "article_id": "2",
                "chunk_index": 0,
                "ticker": "TSLA",
                "content": "Tesla delivery miss",
                "source_url": "https://example.com/tsla",
                "source_name": "Example",
                "embedding": [0.0, 1.0],
            },
        ]
    )
    result = retriever.search([1.0, 0.0], ticker="AAPL", top_k=1)
    assert result[0]["ticker"] == "AAPL"


def test_generate_signal_request_validation():
    model = GenerateSignalRequest(ticker="NVDA")
    assert model.ticker == "NVDA"


def test_signal_out_model():
    signal = SignalOut(
        id="1",
        ticker="AAPL",
        signal="BUY",
        confidence=88,
        sentiment="Positive",
        summary="Strong quarter",
        sources=["https://example.com"],
        created_at=datetime.utcnow(),
    )
    assert signal.signal == "BUY"


def test_chat_response_model():
    response = ChatResponse(answer="Test", sources=["https://example.com"], confidence=0.7)
    assert response.confidence == 0.7


def test_api_smoke_endpoints():
    import main

    client = TestClient(main.app)
    assert client.get("/health").status_code == 200
    assert client.get("/admin/status").status_code == 200
    assert client.post("/admin/demo/load").status_code == 200
    assert client.get("/api/signals").status_code == 200
    assert client.get("/api/history/NVDA").status_code == 200
