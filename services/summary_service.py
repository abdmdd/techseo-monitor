from datetime import datetime, timedelta

from database.db import (
    create_pending_telegram_summary,
    get_active_audit_job,
    get_latest_audit_job,
    get_pending_telegram_summaries,
    get_sites,
    get_telegram_integration,
    get_users_with_sites,
    has_pending_telegram_summary,
    mark_pending_telegram_summary_failed,
    mark_pending_telegram_summary_sent,
)
from services.audit_service import enqueue_monthly_audit
from services.telegram_service import send_admin_copy, send_telegram_message


AUDIT_TYPE = "monthly"
FRESH_AUDIT_HOURS = 24
ADD_FIRST_SITE_MESSAGE = "Добавьте первый сайт для мониторинга, чтобы получить SEO-сводку."
TEST_PENDING_MESSAGE = "Аудиты запущены. Telegram-сводка придёт после завершения проверки."
TEST_ALREADY_RUNNING_MESSAGE = "Аудиты уже выполняются. Telegram-сводка придёт после завершения проверки."


def _parse_datetime(value):
    if isinstance(value, datetime):
        return value
    if not value:
        return None

    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.strptime(text.split(".", 1)[0], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

    if parsed.tzinfo:
        parsed = parsed.replace(tzinfo=None)
    return parsed


def _site_name(site):
    return site[1]


def _site_url(site):
    return site[2]


def _is_fresh_audit(job):
    if not job or job.get("status") != "completed" or not job.get("result"):
        return False

    finished_at = _parse_datetime(job.get("finished_at") or job.get("created_at"))
    if not finished_at:
        return False

    return datetime.utcnow() - finished_at <= timedelta(hours=FRESH_AUDIT_HOURS)


def _latest_site_job(user_id, site):
    return get_latest_audit_job(user_id=user_id, site_url=_site_url(site), audit_type=AUDIT_TYPE)


def _active_site_job(user_id, site):
    return get_active_audit_job(user_id=user_id, site_url=_site_url(site), audit_type=AUDIT_TYPE)


def _sites_without_fresh_audits(user_id, sites):
    return [site for site in sites if not _is_fresh_audit(_latest_site_job(user_id, site))]


def _all_sites_have_fresh_audits(user_id, sites):
    return bool(sites) and not _sites_without_fresh_audits(user_id, sites)


def _user_has_running_audits(user_id, sites):
    return any(_active_site_job(user_id, site) for site in sites)


def _enqueue_audits(user_id, sites):
    queued = 0
    already_running = 0
    errors = []

    for site in sites:
        try:
            job = enqueue_monthly_audit(url=_site_url(site), user_id=user_id, site_id=site[0])
            if job and job.get("already_running"):
                already_running += 1
            elif job:
                queued += 1
        except Exception as exc:
            errors.append({"site_url": _site_url(site), "message": str(exc)})

    return {
        "queued": queued,
        "already_running": already_running,
        "errors": errors,
    }


def ensure_fresh_audits_for_user(user_id, period="daily", force_refresh=False):
    sites = get_sites(user_id=user_id)
    if not sites:
        return {
            "success": False,
            "message": ADD_FIRST_SITE_MESSAGE,
            "audits_created": 0,
            "errors_count": 0,
            "projects_checked": 0,
        }

    target_sites = sites if force_refresh else _sites_without_fresh_audits(user_id, sites)
    result = _enqueue_audits(user_id, target_sites)
    return {
        "success": not result["errors"],
        "message": "Аудиты поставлены в очередь." if target_sites else "Свежие аудиты уже есть.",
        "audits_created": result["queued"],
        "already_running": result["already_running"],
        "errors_count": len(result["errors"]),
        "projects_checked": len(sites),
        "errors": result["errors"],
    }


def _safe_int(value):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _latest_result(user_id, site_url):
    job = get_latest_audit_job(user_id=user_id, site_url=site_url, audit_type=AUDIT_TYPE)
    if not job:
        return None, None
    audit_data = job.get("result") or {}
    return audit_data.get("result") or {}, job


def _recommendation(result):
    issues = result.get("seo_assistant_issues") or []
    for issue in issues:
        fix = (issue.get("fix") or "").strip()
        if fix:
            return fix

    meta = result.get("meta_audit", {}).get("summary", {})
    if _safe_int(meta.get("description_issues")):
        return "Исправьте страницы с отсутствующими или слабыми meta description."
    if _safe_int(result.get("broken_links_total") or len(result.get("broken_links") or [])):
        return "Исправьте внутренние ссылки, которые ведут на 404 или недоступные страницы."
    if result.get("robots_errors"):
        return "Проверьте robots.txt и убедитесь, что важные страницы открыты для обхода."
    return "Продолжайте мониторинг и сравните динамику после следующего аудита."


def _critical_count(result):
    issues = result.get("seo_assistant_issues") or []
    return len([issue for issue in issues if issue.get("severity") == "critical"])


def _project_block(user_id, site):
    url = _site_url(site)
    result, job = _latest_result(user_id, url)
    if not job:
        return f"""Сайт: {_site_name(site)} ({url})
Статус: Нет данных аудита

Рекомендация:
Запустите первый аудит сайта.
"""

    if job.get("status") == "error":
        return f"""Сайт: {_site_name(site)} ({url})
Статус: Не удалось проверить сайт
Причина: {job.get("error_message") or "неизвестная ошибка"}
Последний аудит: {job.get("finished_at") or job.get("created_at") or "-"}
"""

    score = job.get("seo_score")
    errors_count = job.get("errors_count")
    pages_checked = result.get("crawled_pages_count") or len(result.get("crawled_pages") or [])
    broken_links = result.get("broken_links_total") or len(result.get("broken_links") or [])
    indexed = result.get("indexed_pages_count") or result.get("searchable_pages_count") or "нет данных"

    return f"""Сайт: {_site_name(site)} ({url})
SEO score: {score if score is not None else 0}/100
Проверено страниц: {pages_checked}
Ошибки: {_safe_int(errors_count)}
Критические: {_critical_count(result)}
404: {_safe_int(broken_links)}
Индексация: {indexed} страниц
Последний аудит: {job.get("finished_at") or job.get("created_at") or "-"}

Рекомендация:
{_recommendation(result)}
"""


def build_telegram_summary(user_id, period="daily"):
    sites = get_sites(user_id=user_id)
    if not sites:
        return {"success": False, "message": ADD_FIRST_SITE_MESSAGE, "text": ADD_FIRST_SITE_MESSAGE}

    period_label = {
        "daily": "день",
        "weekly": "неделю",
        "monthly": "месяц",
    }.get(period, "день")

    blocks = [_project_block(user_id, site) for site in sites]
    text = f"SEO-сводка за {period_label}\n\n" + "\n---\n".join(blocks)
    return {"success": True, "message": "Сводка сформирована.", "text": text}


def _send_text_to_user(user_id, text):
    telegram = get_telegram_integration(user_id)
    if not telegram:
        return False, "telegram_not_connected"
    return send_telegram_message(text, telegram.get("telegram_chat_id"))


def send_completed_telegram_summary(user_id, period="daily", send_admin=True):
    summary = build_telegram_summary(user_id, period=period)
    text = summary.get("text") or summary.get("message")
    ok, error = _send_text_to_user(user_id, text)
    admin_ok = False
    admin_error = None
    if send_admin:
        admin_ok, admin_error = send_admin_copy(text, user_id=user_id)

    return {
        "success": bool(ok),
        "message": "Telegram-сводка отправлена." if ok else f"Не удалось отправить Telegram-сводку: {error}",
        "text": text,
        "error": error,
        "admin_success": bool(admin_ok),
        "admin_error": admin_error,
    }


def send_telegram_summary(user_id, period="daily", force_refresh=False):
    if force_refresh:
        return request_test_telegram_summary(user_id, period=period)
    return send_completed_telegram_summary(user_id, period=period)


def request_test_telegram_summary(user_id, period="daily"):
    sites = get_sites(user_id=user_id)
    if not sites:
        ok, error = _send_text_to_user(user_id, ADD_FIRST_SITE_MESSAGE)
        return {
            "success": bool(ok),
            "status": "no_sites",
            "message": ADD_FIRST_SITE_MESSAGE if ok else f"Не удалось отправить Telegram-сообщение: {error}",
            "text": ADD_FIRST_SITE_MESSAGE,
            "error": error,
        }

    if _all_sites_have_fresh_audits(user_id, sites):
        result = send_completed_telegram_summary(user_id, period=period)
        result["status"] = "sent"
        return result

    missing_sites = _sites_without_fresh_audits(user_id, sites)
    enqueue_result = _enqueue_audits(user_id, missing_sites)
    create_pending_telegram_summary(user_id, period, created_by="test")

    if enqueue_result["errors"]:
        return {
            "success": False,
            "status": "queued_with_errors",
            "message": "Часть аудитов не удалось поставить в очередь. Telegram-сводка придёт после завершения доступных проверок.",
            "ensure": enqueue_result,
        }

    already_pending = has_pending_telegram_summary(user_id, period)
    message = TEST_ALREADY_RUNNING_MESSAGE if enqueue_result["already_running"] and not enqueue_result["queued"] else TEST_PENDING_MESSAGE
    return {
        "success": True,
        "status": "pending" if already_pending else "queued",
        "message": message,
        "ensure": enqueue_result,
    }


def start_scheduled_daily_summary(user_id):
    sites = get_sites(user_id=user_id)
    if not sites:
        ok, error = _send_text_to_user(user_id, ADD_FIRST_SITE_MESSAGE)
        return {"success": bool(ok), "status": "no_sites", "message": ADD_FIRST_SITE_MESSAGE, "error": error}

    enqueue_result = _enqueue_audits(user_id, sites)
    create_pending_telegram_summary(user_id, "daily", created_by="scheduled")
    return {
        "success": not enqueue_result["errors"],
        "status": "pending",
        "message": "Ежедневные аудиты поставлены в очередь.",
        "ensure": enqueue_result,
    }


def _pending_ready(summary):
    sites = get_sites(user_id=summary["user_id"])
    if not sites:
        return True
    return not _user_has_running_audits(summary["user_id"], sites)


def process_pending_telegram_summaries(user_id=None):
    processed = 0
    sent = 0
    failed = 0

    for summary in get_pending_telegram_summaries(user_id=user_id):
        if not _pending_ready(summary):
            continue

        processed += 1
        result = send_completed_telegram_summary(summary["user_id"], period=summary.get("period") or "daily")
        if result.get("success"):
            mark_pending_telegram_summary_sent(summary["id"])
            sent += 1
        else:
            mark_pending_telegram_summary_failed(summary["id"], result.get("error") or result.get("message"))
            failed += 1

    return {"processed": processed, "sent": sent, "failed": failed}


def run_monthly_audit_for_all_users():
    stats = {
        "users_processed": 0,
        "projects_checked": 0,
        "audits_created": 0,
        "errors_count": 0,
    }

    for user_id in get_users_with_sites():
        stats["users_processed"] += 1
        result = ensure_fresh_audits_for_user(user_id, period="monthly", force_refresh=True)
        stats["projects_checked"] += result.get("projects_checked", 0)
        stats["audits_created"] += result.get("audits_created", 0)
        stats["errors_count"] += result.get("errors_count", 0)
        create_pending_telegram_summary(user_id, "monthly", created_by="scheduled")

    return stats
