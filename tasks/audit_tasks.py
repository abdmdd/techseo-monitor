from datetime import datetime, timedelta

from tasks.celery_app import celery

from database.db import (
    get_due_seo_monitoring_settings,
    mark_seo_monitoring_sent,
    update_audit_job,
)
from services.audit_service import (
    run_monthly_audit,
    run_quarterly_audit
)
from services.history_service import save_audit_history
from services.summary_service import send_telegram_summary
from services.telegram_service import send_admin_copy


def _next_monitoring_run(now, frequency):
    days = 7 if frequency == "weekly" else 1
    return (now + timedelta(days=days)).isoformat(timespec="seconds")


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

        return audit_data
    except Exception as exc:
        update_audit_job(
            job_id,
            status="error",
            progress=100,
            error_message=str(exc),
            finished=True
        )
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
            period = "weekly" if settings.get("frequency") == "weekly" else "daily"
            result = send_telegram_summary(settings["user_id"], period=period, force_refresh=False)
            admin_ok, _ = send_admin_copy(result.get("text") or result.get("message"), user_id=settings["user_id"])
            if result.get("success") or admin_ok:
                mark_seo_monitoring_sent(
                    settings["user_id"],
                    now_value,
                    _next_monitoring_run(now, settings.get("frequency")),
                )
                sent += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    return {"sent": sent, "failed": failed}
