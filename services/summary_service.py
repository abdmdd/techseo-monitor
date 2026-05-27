from datetime import datetime, timedelta

from database.db import (
    get_latest_audit_job,
    get_sites,
    get_telegram_integration,
    get_users_with_sites,
)
from services.audit_service import enqueue_monthly_audit
from services.telegram_service import send_telegram_message


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


def _run_audit_for_site(user_id, site):
    site_id = site[0]
    url = _site_url(site)
    try:
        job = enqueue_monthly_audit(url=url, user_id=user_id, site_id=site_id)
    except Exception as exc:
        return {"success": False, "audit_created": False, "message": str(exc)}

    return {
        "success": True,
        "job_id": job.get("id") if job else None,
        "audit_created": bool(job and not job.get("already_running")),
        "already_running": bool(job and job.get("already_running")),
    }


def ensure_fresh_audits_for_user(user_id, period="daily", force_refresh=False):
    sites = get_sites(user_id=user_id)
    if not sites:
        return {
            "success": False,
            "message": "Добавьте первый сайт для мониторинга, чтобы получить SEO-сводку.",
            "audits_created": 0,
            "errors_count": 0,
            "projects_checked": 0,
        }

    audits_created = 0
    errors = []
    checked = 0

    for site in sites:
        checked += 1
        latest = get_latest_audit_job(user_id=user_id, site_url=_site_url(site), audit_type="monthly")
        has_completed_audit = bool(latest and latest.get("status") == "completed" and latest.get("result"))
        if not force_refresh and has_completed_audit:
            continue

        result = _run_audit_for_site(user_id, site)
        if result.get("audit_created"):
            audits_created += 1
        if not result.get("success"):
            errors.append({"site_url": _site_url(site), "message": result.get("message") or "Неизвестная ошибка"})

    return {
        "success": not errors,
        "message": "Аудиты обновлены." if not errors else "Часть сайтов не удалось проверить.",
        "audits_created": audits_created,
        "errors_count": len(errors),
        "projects_checked": checked,
        "errors": errors,
    }


def _safe_int(value):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _latest_result(user_id, site_url):
    job = get_latest_audit_job(user_id=user_id, site_url=site_url, audit_type="monthly")
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
        return f"""Сайт: {url}
Статус: Нет данных аудита

Рекомендация:
Запустите первый аудит сайта.
"""

    if job.get("status") in ("queued", "running"):
        return f"""Сайт: {url}
Статус: Аудит уже выполняется. Дождитесь завершения.
Последний запуск: {job.get("started_at") or job.get("created_at") or "-"}

Рекомендация:
Сводка обновится после завершения аудита.
"""

    if job.get("status") == "error":
        return f"""Сайт: {url}
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


def _was_recently_created(job, minutes=10):
    created_at = _parse_datetime((job or {}).get("created_at"))
    if not created_at:
        return False
    return datetime.utcnow() - created_at <= timedelta(minutes=minutes)


def build_telegram_summary(user_id, period="daily"):
    sites = get_sites(user_id=user_id)
    if not sites:
        message = "Добавьте первый сайт для мониторинга, чтобы получить SEO-сводку."
        return {"success": False, "message": message, "text": message}

    period_label = {
        "daily": "день",
        "weekly": "неделю",
        "monthly": "месяц",
    }.get(period, "день")

    blocks = [_project_block(user_id, site) for site in sites]
    has_sparse_data = False
    for site in sites:
        latest = get_latest_audit_job(user_id=user_id, site_url=_site_url(site), audit_type="monthly")
        if latest and latest.get("status") == "completed" and _was_recently_created(latest):
            has_sparse_data = True
            break
    note = (
        "\nМы автоматически запустили первый аудит, поэтому следующие сводки будут точнее."
        if has_sparse_data
        else ""
    )
    text = f"SEO-сводка за {period_label}\n\n" + "\n---\n".join(blocks) + note
    return {"success": True, "message": "Сводка сформирована.", "text": text}


def send_telegram_summary(user_id, period="daily", force_refresh=False):
    ensure_result = ensure_fresh_audits_for_user(user_id, period=period, force_refresh=force_refresh)
    summary = build_telegram_summary(user_id, period=period)
    telegram = get_telegram_integration(user_id)

    if not telegram:
        return {
            "success": False,
            "message": "Telegram не подключён.",
            "text": summary.get("text"),
            "ensure": ensure_result,
        }

    ok, error = send_telegram_message(summary.get("text"), telegram.get("telegram_chat_id"))
    return {
        "success": bool(ok),
        "message": "Telegram-сводка отправлена." if ok else f"Не удалось отправить Telegram-сводку: {error}",
        "text": summary.get("text"),
        "error": error,
        "ensure": ensure_result,
    }


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

        if get_telegram_integration(user_id):
            send_result = send_telegram_summary(user_id, period="monthly", force_refresh=False)
            if not send_result.get("success"):
                stats["errors_count"] += 1

    return stats
