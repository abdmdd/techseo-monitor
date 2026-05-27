from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from tasks.celery_app import celery

from database.db import (
    get_due_seo_monitoring_settings,
    get_telegram_integration,
    mark_seo_monitoring_sent,
    update_audit_job,
)
from services.audit_service import (
    run_monthly_audit,
    run_quarterly_audit
)
from services.history_service import save_audit_history
from services.summary_service import process_pending_telegram_summaries, start_scheduled_daily_summary


MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def _next_monitoring_run(now, frequency):
    if frequency == "weekly":
        return (now + timedelta(days=7)).isoformat(timespec="seconds")

    moscow_now = datetime.now(MOSCOW_TZ)
    next_run = moscow_now.replace(hour=8, minute=0, second=0, microsecond=0)
    if next_run <= moscow_now:
        next_run += timedelta(days=1)
    return next_run.astimezone(ZoneInfo("UTC")).replace(tzinfo=None).isoformat(timespec="seconds")


# ==================================================
# MONTHLY TASK
# ==================================================

@celery.task(bind=True)
def run_monthly_audit_task(self, job_id, url=None, user_id=None):
    if url is None:
        return run_monthly_audit(job_id)

    update_audit_job(
        job_id,
        status="running",
        progress=10,
        started=True
    )

    try:
        update_audit_job(job_id, progress=25)
        audit_data = run_monthly_audit(url)
        update_audit_job(job_id, progress=85)

        result = audit_data["result"]
        score = audit_data["score"]
        errors_count = audit_data["errors_count"]

        save_audit_history(
            url=url,
            audit_type="Ежемесячный аудит",
            result=result,
            score=score,
            errors_count=errors_count,
            user_id=user_id
        )

        update_audit_job(
            job_id,
            status="completed",
            progress=100,
            result=audit_data,
            seo_score=score,
            errors_count=errors_count,
            finished=True
        )

        process_pending_telegram_summaries(user_id=user_id)
        return audit_data
    except Exception as exc:
        update_audit_job(
            job_id,
            status="error",
            progress=100,
            error_message=str(exc),
            finished=True
        )
        process_pending_telegram_summaries(user_id=user_id)
        raise


# ==================================================
# QUARTERLY TASK
# ==================================================

@celery.task

def run_quarterly_audit_task(url):

    return run_quarterly_audit(url)


@celery.task
def send_scheduled_seo_summaries():
    now = datetime.utcnow()
    now_value = now.isoformat(timespec="seconds")
    sent = 0
    failed = 0

    for settings in get_due_seo_monitoring_settings(now_value):
        try:
            if settings.get("frequency") != "daily" or not get_telegram_integration(settings["user_id"]):
                continue

            result = start_scheduled_daily_summary(settings["user_id"])
            if result.get("success"):
                mark_seo_monitoring_sent(
                    settings["user_id"],
                    now_value,
                    _next_monitoring_run(now, "daily"),
                )
                sent += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    return {"sent": sent, "failed": failed}
