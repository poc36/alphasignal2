from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.chat import router as chat_router
from api.routes.history import router as history_router
from api.routes.signals import router as signals_router
from api.routes.tickers import router as tickers_router
from config import settings
from core.services import service
from models.database import init_db
from models.schemas import HealthResponse
from scheduler import scheduler, start_scheduler, stop_scheduler


init_db()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()
        await service.rss_parser.close()
        await service.sec_fetcher.close()


app = FastAPI(
    title='AlphaSignal API',
    description='AI Trading Research Assistant backend',
    version='2.0.0',
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(signals_router)
app.include_router(chat_router)
app.include_router(tickers_router)
app.include_router(history_router)


@app.get('/health', response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status='ok',
        database=settings.database_url,
        vector_store=settings.vector_store_path,
        scheduler_running=scheduler.running,
        timestamp=datetime.utcnow(),
    )


@app.get('/sources')
async def get_sources() -> dict:
    return {
        'sources': [
            {'name': 'Yahoo Finance', 'category': 'general'},
            {'name': 'Reuters Business', 'category': 'general'},
            {'name': 'Bloomberg Markets', 'category': 'general'},
            {'name': 'SEC EDGAR', 'category': 'filings'},
        ]
    }


@app.post('/admin/ingest')
async def run_ingestion() -> dict:
    return await service.ingest_all()


@app.post('/admin/demo/load')
async def load_demo() -> dict:
    loaded = await service.seed_demo_signals()
    return {'loaded': loaded}


@app.get('/admin/status')
async def admin_status():
    return service.get_status(scheduler.running, settings.ingestion_interval_hours)


@app.get('/admin/articles')
async def admin_articles(limit: int = 20):
    return {'articles': service.list_articles(limit=limit)}


@app.post('/admin/scheduler/start')
async def scheduler_start() -> dict:
    start_scheduler()
    return {'running': scheduler.running, 'interval_hours': settings.ingestion_interval_hours}


@app.post('/admin/scheduler/stop')
async def scheduler_stop() -> dict:
    stop_scheduler()
    return {'running': scheduler.running}


@app.get('/tickers')
async def list_tickers() -> dict:
    return {'tickers': service.list_tickers()}


if __name__ == '__main__':
    uvicorn.run('main:app', host=settings.api_host, port=settings.api_port, reload=settings.debug)
