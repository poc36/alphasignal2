from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import settings
from core.services import service


scheduler = AsyncIOScheduler()


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(service.ingest_all, "interval", hours=settings.ingestion_interval_hours, id="ingest_job", replace_existing=True)
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
