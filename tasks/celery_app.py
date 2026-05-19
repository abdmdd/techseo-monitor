from celery import Celery


# ==================================================
# CELERY
# ==================================================

celery = Celery(
    "techseo_monitor",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
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