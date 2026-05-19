from tasks.celery_app import celery

from services.audit_service import (
    run_monthly_audit,
    run_quarterly_audit
)


# ==================================================
# MONTHLY TASK
# ==================================================

@celery.task

def run_monthly_audit_task(url):

    return run_monthly_audit(url)


# ==================================================
# QUARTERLY TASK
# ==================================================

@celery.task

def run_quarterly_audit_task(url):

    return run_quarterly_audit(url)