from celery import Celery

from app.config import settings

# Inisialisasi Celery App
celery_app = Celery(
    "pln_geomatch",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.spatial_tasks"],
)

# Konfigurasi Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Jakarta",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    broker_connection_timeout=2,
    broker_transport_options={"socket_connect_timeout": 2, "socket_timeout": 2},
)
