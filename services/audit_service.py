from crawlers.seo_crawler import check_technical_seo

from database.db import (
    create_audit_job,
    get_active_audit_job,
    get_latest_audit_job,
    set_audit_job_task_id,
    update_audit_job
)
from services.score_service import (
    calculate_seo_score,
    get_errors_count
)


# ==================================================
# MONTHLY AUDIT
# ==================================================

def run_monthly_audit(url):

    result = check_technical_seo(url)

    errors_count = get_errors_count(result)
    score = calculate_seo_score(result)

    return {
        "result": result,
        "errors_count": errors_count,
        "score": score
    }


def enqueue_monthly_audit(url, user_id, site_id=None):
    active_job = get_active_audit_job(user_id=user_id, site_url=url, audit_type="monthly")
    if active_job:
        active_job["already_running"] = True
        return active_job

    job_id = create_audit_job(
        user_id=user_id,
        site_id=site_id,
        site_url=url,
        audit_type="monthly"
    )

    try:
        from tasks.audit_tasks import run_monthly_audit_task

        async_result = run_monthly_audit_task.apply_async(args=[job_id, url, user_id])
        set_audit_job_task_id(job_id, async_result.id)
    except Exception as exc:
        update_audit_job(
            job_id,
            status="error",
            progress=100,
            error_message=f"Не удалось поставить аудит в очередь Celery: {exc}",
            finished=True
        )
        raise

    return get_latest_audit_job(user_id=user_id, site_url=url, audit_type="monthly")


def get_latest_monthly_audit_job(user_id, site_url=None):
    return get_latest_audit_job(user_id=user_id, site_url=site_url, audit_type="monthly")


def get_active_monthly_audit_job(user_id, site_url=None):
    return get_active_audit_job(user_id=user_id, site_url=site_url, audit_type="monthly")


# ==================================================
# QUARTERLY AUDIT
# ==================================================

def run_quarterly_audit(url):

    result = check_technical_seo(url)

    errors_count = get_errors_count(result)
    score = calculate_seo_score(result)

    advanced_checks = {

        "pagespeed": "Не подключено",
        "core_web_vitals": "Не подключено",
        "google_indexing": "Не подключено",
        "safe_browsing": "Не подключено",
        "mobile_usability": "Не подключено",
        "structured_data": "Не подключено"
    }

    return {
        "result": result,
        "errors_count": errors_count,
        "score": score,
        "advanced_checks": advanced_checks
    }
