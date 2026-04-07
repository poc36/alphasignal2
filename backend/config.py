from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = Path(tempfile.gettempdir()) / 'alphasignal'
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / '.env')
load_dotenv(BASE_DIR.parent / '.env')


def _normalize_database_url(raw_url: str | None) -> str:
    if not raw_url:
        return f"sqlite:///{(RUNTIME_DIR / 'alphasignal.db').as_posix()}"
    if raw_url.startswith('sqlite:///./'):
        relative_path = raw_url.removeprefix('sqlite:///./')
        return f"sqlite:///{(BASE_DIR.parent / relative_path).resolve().as_posix()}"
    return raw_url


@dataclass
class Settings:
    app_name: str = os.getenv('APP_NAME', 'AlphaSignal')
    debug: bool = os.getenv('DEBUG', 'false').lower() == 'true'
    api_host: str = os.getenv('API_HOST', '0.0.0.0')
    api_port: int = int(os.getenv('API_PORT', os.getenv('PORT', '8000')))
    database_url: str = _normalize_database_url(os.getenv('DATABASE_URL'))
    llm_provider: str = os.getenv('LLM_PROVIDER', 'gemini')
    gemini_api_key: str | None = os.getenv('GEMINI_API_KEY')
    gemini_model: str = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
    openai_api_key: str | None = os.getenv('OPENAI_API_KEY')
    llm_model: str = os.getenv('LLM_MODEL', 'gpt-4o-mini')
    embedding_model: str = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small')
    ingestion_interval_hours: int = int(os.getenv('INGESTION_INTERVAL_HOURS', '6'))
    chroma_path: str = os.getenv('CHROMA_PATH', str(RUNTIME_DIR / 'chroma'))
    vector_store_path: str = os.getenv('VECTOR_STORE_PATH', str(RUNTIME_DIR / 'vector_store.json'))
    use_sentence_transformers: bool = os.getenv('USE_SENTENCE_TRANSFORMERS', 'false').lower() == 'true'
    use_chromadb: bool = os.getenv('USE_CHROMADB', 'true').lower() == 'true'
    supported_tickers_raw: str = os.getenv(
        'SUPPORTED_TICKERS',
        'AAPL,TSLA,NVDA,MSFT,GOOGL,AMZN,META,AMD,SPY,BTC-USD',
    )

    @property
    def supported_tickers(self) -> list[str]:
        return [ticker.strip().upper() for ticker in self.supported_tickers_raw.split(',') if ticker.strip()]


settings = Settings()
