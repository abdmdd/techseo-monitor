from tasks.celery_app import celery

from database.db import update_audit_job
from services.audit_service import (
    run_monthly_audit,
    run_quarterly_audit
)
from services.history_service import save_audit_history


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
