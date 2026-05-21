import os

from celery import Celery


# ==================================================
# CELERY
# ==================================================

celery = Celery(
    "techseo_monitor",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
)

# ==================================================
# CONFIG
# ==================================================

celery.conf.update(

    task_serializer="json",

    accept_content=["json"],

    result_serializer="json",

    timezone="Europe/Moscow",

    enable_utc=True
)
