"""Celery application instance: broker, result backend, and queue isolation."""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "docintel",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

# Queue isolation (NFR): CPU-heavy OCR cannot starve LLM-bound extract or index work.
INGEST_QUEUE = "ingest"
OCR_QUEUE = "ocr"
EXTRACT_QUEUE = "extract"
INDEX_QUEUE = "index"

celery_app.conf.update(
    task_default_queue=INGEST_QUEUE,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
)

celery_app.autodiscover_tasks(["app.workers"])
