from datetime import date, datetime, timedelta

import requests

from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from database.db import (
    get_latest_audit_job,
    get_sites,
)
from services.yandex_metrika_service import (
    find_matching_counter,
    get_search_traffic_anomaly,
    get_traffic_summary,
)
from services.yandex_oauth_service import get_yandex_access_token, get_yandex_integration_status
from services.yandex_webmaster_service import (
    find_matching_host,
    get_host_diagnostics,
    get_host_summary,
    get_indexing_status,
)


TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
TELEGRAM_TIMEOUT = 20


def _today():
    return date.today().isoformat()


def _same_day_previous_year(value):
    try:
        return date(value.year - 1, value.month, value.day)
    except ValueError:
        return date(value.year - 1, value.month, 28)


def _safe_int(value):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _percent(current, previous):
    current = float(current or 0)
    previous = float(previous or 0)
    if previous == 0:
        return "нет данных" if current == 0 else "+100%"
    return f"{((current - previous) / previous) * 100:+.1f}%"


def _first_value(data, keys, default="нет данных"):
    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if value not in (None, ""):
                return value
        for value in data.values():
            nested = _first_value(value, keys, None)
            if nested not in (None, ""):
                return nested
    elif isinstance(data, list):
        for item in data:
            nested = _first_value(item, keys, None)
            if nested not in (None, ""):
                return nested
    return default


def _latest_monthly_result(user_id, site_url):
    job = get_latest_audit_job(user_id=user_id, site_url=site_url, audit_type="monthly")
    audit_data = job.get("result") if job else None
    if not audit_data:
        return None, job
    return audit_data.get("result") or {}, job


def _status_line(has_problem):
    return "⚠️ есть проблемы" if has_problem else "✅ всё хорошо"


def _audit_short_summary(result, job):
    if not result:
        return {
            "overview_status": "⚠️ нет данных аудита",
            "pages_checked": 0,
            "critical": 0,
            "warnings": 0,
            "sitemap": "нет данных",
            "meta": "нет данных",
            "links": "нет данных",
            "errors": 0,
            "problems": ["нет данных ежемесячного аудита"],
        }

    errors = result.get("errors") or []
    assistant_issues = result.get("seo_assistant_issues") or []
    critical = len([issue for issue in assistant_issues if issue.get("severity") == "critical"])
    warnings = len([issue for issue in assistant_issues if issue.get("severity") in ("important", "warning")])
    errors_count = job.get("errors_count") if job else len(errors)
    pages_checked = result.get("crawled_pages_count") or len(result.get("crawled_pages") or [])

    sitemap_problems = []
    if not result.get("sitemap_valid", True):
        sitemap_problems.append("sitemap требует проверки")
    if result.get("robots_errors"):
        sitemap_problems.append("robots содержит замечания")

    meta_summary = result.get("meta_audit", {}).get("summary", {})
    canonical_summary = result.get("canonical_analysis", {}).get("summary", {})
    meta_problems = (
        _safe_int(meta_summary.get("title_issues"))
        + _safe_int(meta_summary.get("description_issues"))
        + _safe_int(meta_summary.get("h1_issues"))
        + _safe_int(canonical_summary.get("missing"))
        + _safe_int(canonical_summary.get("broken"))
        + _safe_int(canonical_summary.get("external"))
        + _safe_int(canonical_summary.get("loops"))
    )

    broken_links = _safe_int(result.get("broken_links_total") or len(result.get("broken_links") or []))
    redirects = len(result.get("redirect_analysis", {}).get("rows") or result.get("redirect_chains") or [])
    reviews_connected = bool(result.get("reviews") or result.get("reviews_summary"))

    problems = []
    if critical:
        problems.append(f"критичные проблемы: {critical}")
    if sitemap_problems:
        problems.extend(sitemap_problems[:2])
    if meta_problems:
        problems.append(f"meta/canonical: {meta_problems}")
    if broken_links:
        problems.append(f"404: {broken_links}")
    if redirects:
        problems.append(f"редиректы: {redirects}")

    return {
        "overview_status": "⚠️ требует внимания" if errors_count or critical or warnings else "✅ всё хорошо",
        "pages_checked": pages_checked,
        "critical": critical,
        "warnings": warnings,
        "sitemap": "⚠️ есть проблемы: " + ", ".join(sitemap_problems) if sitemap_problems else "✅ всё хорошо",
        "meta": f"⚠️ title/meta/canonical: {meta_problems} проблем" if meta_problems else "✅ всё хорошо",
        "links": (
            f"⚠️ 404: {broken_links}, редиректы: {redirects}, отзывы: {'есть' if reviews_connected else 'нет'}"
            if broken_links or redirects else
            f"✅ всё хорошо, отзывы: {'есть' if reviews_connected else 'нет'}"
        ),
        "errors": _safe_int(errors_count),
        "problems": problems,
    }


def _yandex_webmaster_summary(user_id, site_url):
    if not get_yandex_integration_status(user_id).get("connected"):
        return {
            "iks": "нет данных",
            "loaded": "нет данных",
            "indexed": "нет данных",
            "problems": "нет данных",
        }

    access_token, token_error = get_yandex_access_token(user_id)
    if token_error or not access_token:
        return {
            "iks": "нет данных",
            "loaded": "нет данных",
            "indexed": "нет данных",
            "problems": "нет данных",
        }

    match = find_matching_host(access_token, site_url)
    if match.get("status_code") == 401:
        access_token, token_error = get_yandex_access_token(user_id, force_refresh=True)
        if token_error or not access_token:
            return {
                "iks": "нет данных",
                "loaded": "нет данных",
                "indexed": "нет данных",
                "problems": "нет данных",
            }
        match = find_matching_host(access_token, site_url)

    if not match.get("ok") or not match.get("found"):
        return {
            "iks": "нет данных",
            "loaded": "нет данных",
            "indexed": "нет данных",
            "problems": "нет данных",
        }

    host_id = match.get("host_id")
    webmaster_user_id = match.get("user_id")
    summary = get_host_summary(access_token, host_id, webmaster_user_id)
    diagnostics = get_host_diagnostics(access_token, host_id, webmaster_user_id)
    indexing = get_indexing_status(access_token, host_id, webmaster_user_id)

    summary_data = summary.get("data") if summary.get("ok") else {}
    diagnostics_data = diagnostics.get("data") if diagnostics.get("ok") else {}
    indexing_data = indexing.get("data") if indexing.get("ok") else {}
    problems = _first_value(diagnostics_data, ["problems", "diagnostics", "items", "host_problems"], [])
    if isinstance(problems, dict):
        problems = list(problems.values())
    problems_label = "есть" if isinstance(problems, list) and problems else "нет"

    indexed = _first_value(summary_data, ["indexed_pages_count", "searchable_pages_count", "pages_in_search", "indexed_pages"])
    if indexed == "нет данных":
        indexed = _first_value(indexing_data, ["indexed_pages_count", "searchable_pages_count", "pages_in_search"])

    return {
        "iks": _first_value(summary_data, ["sqi", "tic", "iks", "site_quality_index"]),
        "loaded": _first_value(summary_data, ["downloaded_pages_count", "loaded_pages", "downloaded_pages", "pages_loaded"]),
        "indexed": indexed,
        "problems": problems_label,
    }


def _yandex_metrika_summary(user_id, site_url):
    empty = {
        "visits": "нет данных",
        "pageviews": "нет данных",
        "users": "нет данных",
        "search": "нет данных",
        "ads": "нет данных",
        "visits_delta": "нет данных",
        "search_delta": "нет данных",
        "ads_delta": "нет данных",
        "anomaly": "✅ нет",
    }
    if not get_yandex_integration_status(user_id).get("connected"):
        return empty

    access_token, token_error = get_yandex_access_token(user_id)
    if token_error or not access_token:
        return empty

    match = find_matching_counter(access_token, site_url)
    if match.get("status_code") == 401:
        access_token, token_error = get_yandex_access_token(user_id, force_refresh=True)
        if token_error or not access_token:
            return empty
        match = find_matching_counter(access_token, site_url)

    if not match.get("ok") or not match.get("found"):
        return empty

    counter_id = match.get("counter_id")
    today = date.today()
    current_to = today - timedelta(days=1)
    current_from = current_to - timedelta(days=6)
    compare_from = _same_day_previous_year(current_from)
    compare_to = _same_day_previous_year(current_to)

    current = get_traffic_summary(access_token, counter_id, current_from.isoformat(), current_to.isoformat())
    compare = get_traffic_summary(access_token, counter_id, compare_from.isoformat(), compare_to.isoformat())
    anomaly = get_search_traffic_anomaly(access_token, counter_id)

    if not current.get("ok"):
        return empty

    current_summary = current.get("summary") or {}
    compare_summary = compare.get("summary") if compare.get("ok") else {}
    anomaly_label = "⚠️ поисковый трафик изменился более чем на 20%" if anomaly.get("ok") and anomaly.get("anomaly") else "✅ нет"

    return {
        "visits": _safe_int(current_summary.get("visits")),
        "pageviews": _safe_int(current_summary.get("pageviews")),
        "users": _safe_int(current_summary.get("users")),
        "search": _safe_int(current_summary.get("search_visits")),
        "ads": _safe_int(current_summary.get("ads_visits")),
        "visits_delta": _percent(current_summary.get("visits"), compare_summary.get("visits")),
        "search_delta": _percent(current_summary.get("search_visits"), compare_summary.get("search_visits")),
        "ads_delta": _percent(current_summary.get("ads_visits"), compare_summary.get("ads_visits")),
        "anomaly": anomaly_label,
    }


def collect_project_short_summary(user_id, site_id):
    sites = [site for site in get_sites(user_id=user_id) if site[0] == site_id]
    if not sites:
        return None

    site = sites[0]
    site_name = site[1]
    site_url = site[2]
    result, job = _latest_monthly_result(user_id, site_url)
    audit = _audit_short_summary(result, job)
    webmaster = _yandex_webmaster_summary(user_id, site_url)
    metrika = _yandex_metrika_summary(user_id, site_url)

    total_problems = list(audit["problems"])
    if webmaster["problems"] == "есть":
        total_problems.append("проблемы Вебмастера")
    if str(metrika["anomaly"]).startswith("⚠️"):
        total_problems.append("аномалия поискового трафика")

    return {
        "site_name": site_name,
        "site_url": site_url,
        "audit": audit,
        "webmaster": webmaster,
        "metrika": metrika,
        "total_problems": total_problems,
    }


def _format_project(summary):
    audit = summary["audit"]
    webmaster = summary["webmaster"]
    metrika = summary["metrika"]
    problems = summary["total_problems"]
    final_line = "✅ Всё хорошо" if not problems else "⚠️ Есть проблемы: " + "; ".join(problems[:4])
    errors_line = "✅ ошибок нет" if not audit["errors"] else f"⚠️ {audit['errors']} ошибок требуют внимания"

    return f"""━━━━━━━━━━━━
Проект: {summary['site_name']}
URL: {summary['site_url']}

Обзор:
{audit['overview_status']}

* страниц проверено: {audit['pages_checked']}
* критичных проблем: {audit['critical']}
* предупреждений: {audit['warnings']}

Sitemap / Robots:
{audit['sitemap']}

Meta / Canonical:
{audit['meta']}

Ссылки / редиректы / отзывы:
{audit['links']}

Центр ошибок:
{errors_line}

Яндекс Вебмастер:
* ИКС: {webmaster['iks']}
* страниц загружено: {webmaster['loaded']}
* страниц в поиске: {webmaster['indexed']}
* проблемы: {webmaster['problems']}

Яндекс Метрика:
Период: последние 7 дней

* визиты: {metrika['visits']}
* просмотры: {metrika['pageviews']}
* пользователи: {metrika['users']}
* поиск: {metrika['search']}
* реклама: {metrika['ads']}

Сравнение с такой же неделей прошлого года:
* визиты: {metrika['visits_delta']}
* поиск: {metrika['search_delta']}
* реклама: {metrika['ads_delta']}

Аномалии:
{metrika['anomaly']}

Итог:
{final_line}
"""


def format_all_projects_seo_summary(user_id):
    sites = get_sites(user_id=user_id)
    header = f"📊 SEO-сводка TechSEO Monitor\nДата: {_today()}\nПроектов: {len(sites)}\n"

    if not sites:
        return header + "\nПроекты пока не добавлены."

    project_blocks = []
    for site in sites:
        summary = collect_project_short_summary(user_id, site[0])
        if summary:
            project_blocks.append(_format_project(summary))

    return header + "\n" + "\n".join(project_blocks) + "\n━━━━━━━━━━━━"


def send_telegram_message(text):
    token = (TELEGRAM_BOT_TOKEN or "").strip()
    chat_id = (TELEGRAM_CHAT_ID or "").strip()
    if not token or not chat_id:
        return False, "telegram_not_configured"

    chunks = []
    current = ""
    for line in str(text or "").splitlines():
        if len(current) + len(line) + 1 > 3900:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)

    try:
        for chunk in chunks:
            response = requests.post(
                TELEGRAM_API_URL.format(token=token),
                data={
                    "chat_id": chat_id,
                    "text": chunk,
                    "disable_web_page_preview": True,
                },
                timeout=TELEGRAM_TIMEOUT,
            )
            response.raise_for_status()
    except requests.RequestException as exc:
        return False, exc.__class__.__name__

    return True, None
