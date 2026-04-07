# AlphaSignal

AlphaSignal is an AI trading research assistant prototype that ingests financial news and SEC filings, builds a lightweight retrieval layer, generates ticker-level signals, and exposes both an API and a Streamlit dashboard.

## Implemented scope

This repository now includes the full product skeleton described in the specification:

- FastAPI backend with `/api/signals`, `/api/signals/generate`, `/api/chat`, and `/api/tickers/{symbol}`
- Data ingestion from RSS plus SEC EDGAR recent filing discovery
- Deduplication by URL and content hash
- Chunking at roughly 512-token windows with overlap
- Local embedding and retrieval pipeline with ChromaDB when available and JSON fallback otherwise
- Optional sentence-transformers local embeddings can be enabled separately, but the default install keeps embeddings lightweight to avoid dependency conflicts
- Signal generation with `BUY`, `SELL`, and `HOLD` outputs plus confidence and sentiment labels
- Streamlit dashboard with latest signals, ticker history, price chart, and chat panel
- APScheduler-based recurring ingestion job
- Environment template, Dockerfile, and docker-compose for local setup

## Project structure

```text
backend/
  api/
    main.py
    routes/
      signals.py
      chat.py
      tickers.py
  core/
    ingestion/
      rss_parser.py
      sec_fetcher.py
    rag/
      chunker.py
      embedder.py
      retriever.py
      generator.py
    signals/
      classifier.py
    services.py
  models/
    database.py
    schemas.py
  config.py
  scheduler.py
  main.py
frontend/
  app.py
```

## Quickstart

### Install

```bash
pip install -r requirements.txt
```

### Run backend

```bash
python backend/main.py
```

### Run frontend

```bash
streamlit run frontend/app.py
```

Backend defaults to `http://localhost:8000` and Streamlit to `http://localhost:8501`.

## API summary

- `GET /health`
- `GET /sources`
- `GET /tickers`
- `POST /admin/ingest`
- `POST /admin/demo/load`
- `GET /api/signals`
- `POST /api/signals/generate`
- `POST /api/chat`
- `GET /api/tickers/{symbol}`

## Environment

Copy `.env.example` to `.env` and fill in values as needed. By default the app uses a file-backed SQLite database in the system temp directory for easy local persistence; set `DATABASE_URL` to PostgreSQL when you want closer production parity.

## Notes

The implementation favors a runnable local MVP over heavyweight infrastructure. Where the original specification suggested PostgreSQL and ChromaDB as the default stack, this code keeps those integration points flexible while remaining usable out of the box without extra services.
