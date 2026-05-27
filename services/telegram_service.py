import base64
import hashlib
import hmac
from datetime import date, datetime, timedelta

import requests

from config.settings import TELEGRAM_ADMIN_CHAT_ID, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, YANDEX_CLIENT_SECRET
from database.db import (
    get_latest_audit_job,
    get_sites,
    get_telegram_integration,
    get_user_by_id,
    save_telegram_integration,
)
from services.yandex_metrika_service import (
    find_matching_counter,
    get_traffic_summary,
)
from services.yandex_oauth_service import get_yandex_access_token, get_yandex_integration_status
from services.yandex_webmaster_service import (
    find_matching_host,
    get_host_diagnostics,
    get_host_summary,
    get_indexing_status,
)


TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/{method}"
TELEGRAM_TIMEOUT = 20
TELEGRAM_CONNECT_TTL_SECONDS = 24 * 60 * 60


def _today():
    return date.today().isoformat()


def _telegram_secret():
    return (YANDEX_CLIENT_SECRET or TELEGRAM_BOT_TOKEN or "techseo-monitor").strip().encode("utf-8")


def _b64encode(value):
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value):
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def generate_telegram_connect_token(user_id):
    timestamp = int(datetime.utcnow().timestamp())
    payload = f"{int(user_id)}:{timestamp}"
    signature = hmac.new(_telegram_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return _b64encode(f"{payload}:{signature}".encode("utf-8"))


def verify_telegram_connect_token(token):
    try:
        decoded = _b64decode(str(token or "")).decode("utf-8")
        user_id_text, timestamp_text, signature = decoded.split(":", 2)
        payload = f"{int(user_id_text)}:{int(timestamp_text)}"
    except (TypeError, ValueError, UnicodeDecodeError):
        return None

    expected = hmac.new(_telegram_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None

    age = int(datetime.utcnow().timestamp()) - int(timestamp_text)
    if age < 0 or age > TELEGRAM_CONNECT_TTL_SECONDS:
        return None

    return int(user_id_text)


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
        return "нет данных"
    return f"{((current - previous) / previous) * 100:+.1f}%"


def _fmt_date(value):
    return value.strftime("%d.%m.%Y")


def _metrika_period(days):
    current_to = date.today() - timedelta(days=1)
    current_from = current_to - timedelta(days=days - 1)
    compare_from = _same_day_previous_year(current_from)
    compare_to = _same_day_previous_year(current_to)
    return current_from, current_to, compare_from, compare_to


def _has_period_data(summary):
    return any(float((summary or {}).get(key) or 0) > 0 for key in ("visits", "search_visits", "direct_visits", "ads_visits"))


def _value_or_no_data(value, has_data=True):
    if not has_data:
        return "нет данных"
    return _safe_int(value)


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
            "indexed": "нет данных",
            "excluded": "нет данных",
            "problems": "нет данных",
            "recommendations": "нет данных",
        }

    access_token, token_error = get_yandex_access_token(user_id)
    if token_error or not access_token:
        return {
            "iks": "нет данных",
            "indexed": "нет данных",
            "excluded": "нет данных",
            "problems": "нет данных",
            "recommendations": "нет данных",
        }

    match = find_matching_host(access_token, site_url)
    if match.get("status_code") == 401:
        access_token, token_error = get_yandex_access_token(user_id, force_refresh=True)
        if token_error or not access_token:
            return {
                "iks": "нет данных",
                "indexed": "нет данных",
                "excluded": "нет данных",
                "problems": "нет данных",
                "recommendations": "нет данных",
            }
        match = find_matching_host(access_token, site_url)

    if not match.get("ok") or not match.get("found"):
        return {
            "iks": "нет данных",
            "indexed": "нет данных",
            "excluded": "нет данных",
            "problems": "нет данных",
            "recommendations": "нет данных",
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
    excluded = _first_value(summary_data, ["excluded_pages_count", "excluded_pages", "not_indexed_pages_count"])
    if excluded == "нет данных":
        excluded = _first_value(indexing_data, ["excluded_pages_count", "excluded_pages", "not_indexed_pages_count"])

    return {
        "iks": _first_value(summary_data, ["sqi", "tic", "iks", "site_quality_index"]),
        "indexed": indexed,
        "excluded": excluded,
        "problems": problems_label,
        "recommendations": "Проверьте найденные проблемы в Вебмастере" if problems_label == "есть" else "Критичных проблем из доступных данных не найдено",
    }


def _yandex_metrika_summary(user_id, site_url):
    def empty_period(days):
        current_from, current_to, compare_from, compare_to = _metrika_period(days)
        return {
            "current_from": current_from,
            "current_to": current_to,
            "compare_from": compare_from,
            "compare_to": compare_to,
            "current": {},
            "compare": {},
            "compare_has_data": False,
        }

    empty = {
        "period_7": empty_period(7),
        "period_30": empty_period(30),
        "anomaly": "Существенных аномалий поискового трафика не обнаружено.",
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
    result = {}
    for days, key in ((7, "period_7"), (30, "period_30")):
        current_from, current_to, compare_from, compare_to = _metrika_period(days)
        current = get_traffic_summary(access_token, counter_id, current_from.isoformat(), current_to.isoformat())
        compare = get_traffic_summary(access_token, counter_id, compare_from.isoformat(), compare_to.isoformat())
        if not current.get("ok"):
            result[key] = empty[key]
            continue
        compare_summary = compare.get("summary") if compare.get("ok") else {}
        result[key] = {
            "current_from": current_from,
            "current_to": current_to,
            "compare_from": compare_from,
            "compare_to": compare_to,
            "current": current.get("summary") or {},
            "compare": compare_summary,
            "compare_has_data": compare.get("ok") and _has_period_data(compare_summary),
        }

    period_30 = result.get("period_30") or empty["period_30"]
    current_search = float((period_30.get("current") or {}).get("search_visits") or 0)
    previous_search = float((period_30.get("compare") or {}).get("search_visits") or 0)
    if not period_30.get("compare_has_data") or previous_search <= 0:
        anomaly = "Недостаточно данных прошлого года для анализа аномалий поискового трафика."
    else:
        change = ((current_search - previous_search) / previous_search) * 100
        anomaly = (
            f"⚠️ поисковый трафик изменился более чем на 20% относительно прошлого года: {change:+.1f}%"
            if abs(change) > 20
            else "Существенных аномалий поискового трафика не обнаружено."
        )

    return {
        "period_7": result.get("period_7") or empty["period_7"],
        "period_30": period_30,
        "anomaly": anomaly,
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


def _metric_line(label, current, previous, key, previous_has_data):
    current_value = _safe_int((current or {}).get(key))
    previous_value = _value_or_no_data((previous or {}).get(key), previous_has_data)
    delta = _percent((current or {}).get(key), (previous or {}).get(key)) if previous_has_data else "нет данных"
    return f"* {label}: {current_value} / было {previous_value} / изменение {delta}"


def _format_metrika_period(title, period):
    current = period.get("current") or {}
    previous = period.get("compare") or {}
    previous_has_data = bool(period.get("compare_has_data"))
    return f"""{title}:
{_fmt_date(period['current_from'])} — {_fmt_date(period['current_to'])}
Сравнение с прошлым годом:
{_fmt_date(period['compare_from'])} — {_fmt_date(period['compare_to'])}

{_metric_line('Визиты', current, previous, 'visits', previous_has_data)}
{_metric_line('Поиск', current, previous, 'search_visits', previous_has_data)}
{_metric_line('Прямые', current, previous, 'direct_visits', previous_has_data)}
{_metric_line('Реклама', current, previous, 'ads_visits', previous_has_data)}
"""


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
* страниц в поиске: {webmaster['indexed']}
* исключено: {webmaster['excluded']}
* проблемы: {webmaster['problems']}
* рекомендации: {webmaster['recommendations']}

Яндекс Метрика:
{_format_metrika_period('Метрика, последние 7 полных дней', metrika['period_7'])}
{_format_metrika_period('Метрика, последние 30 полных дней', metrika['period_30'])}

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


def _telegram_chunks(text):
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
    return chunks or [""]


def send_telegram_message(text, chat_id):
    token = (TELEGRAM_BOT_TOKEN or "").strip()
    chat_id = str(chat_id or "").strip()
    if not token or not chat_id:
        return False, "telegram_not_configured"

    try:
        for chunk in _telegram_chunks(text):
            response = requests.post(
                TELEGRAM_API_URL.format(token=token, method="sendMessage"),
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


def _admin_chat_id():
    return (TELEGRAM_ADMIN_CHAT_ID or TELEGRAM_CHAT_ID or "").strip()


def send_admin_copy(text, user_id=None):
    chat_id = _admin_chat_id()
    if not chat_id:
        return False, "telegram_admin_not_configured"

    if user_id is not None:
        user_telegram = get_telegram_integration(user_id)
        if user_telegram and str(user_telegram.get("telegram_chat_id") or "").strip() == str(chat_id).strip():
            return True, "telegram_admin_same_as_user"

    user_label = str(user_id or "unknown")
    if user_id is not None:
        user = get_user_by_id(user_id)
        if user:
            user_label = f"{user[0]} / {user[2]}"

    admin_text = f"Админ-копия. Пользователь: {user_label}\n\n{text}"
    return send_telegram_message(admin_text, chat_id)


def sync_telegram_updates():
    token = (TELEGRAM_BOT_TOKEN or "").strip()
    if not token:
        return {
            "ok": False,
            "connected": 0,
            "message": "TELEGRAM_BOT_TOKEN не настроен.",
        }

    try:
        response = requests.get(
            TELEGRAM_API_URL.format(token=token, method="getUpdates"),
            timeout=TELEGRAM_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        return {
            "ok": False,
            "connected": 0,
            "message": f"Не удалось получить обновления Telegram ({exc.__class__.__name__}).",
        }
    except ValueError:
        return {
            "ok": False,
            "connected": 0,
            "message": "Telegram вернул невалидный ответ.",
        }

    connected = 0
    for update in payload.get("result", []):
        message = update.get("message") or {}
        text = (message.get("text") or "").strip()
        parts = text.split()
        if not parts or not parts[0].startswith("/start"):
            continue

        token_part = next((part for part in parts[1:] if part.startswith("connect_")), "")
        if not token_part and "connect_" in text:
            token_part = "connect_" + text.split("connect_", 1)[1].split()[0].strip()
        if not token_part.startswith("connect_"):
            continue

        token_value = token_part.split("connect_", 1)[1].strip()
        user_id = verify_telegram_connect_token(token_value)
        if not user_id:
            continue

        chat = message.get("chat") or {}
        from_user = message.get("from") or {}
        chat_id = chat.get("id")
        username = from_user.get("username") or chat.get("username")
        if not chat_id:
            continue

        save_telegram_integration(user_id, chat_id, username=username)
        connected += 1

    return {
        "ok": True,
        "connected": connected,
        "message": f"Подключений найдено: {connected}.",
    }
