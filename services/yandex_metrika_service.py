from urllib.parse import urlparse

import requests

from database.db import (
    get_site_by_id,
    save_yandex_traffic_snapshot,
)
from services.yandex_oauth_service import get_yandex_access_token


YANDEX_METRIKA_MANAGEMENT_API_URL = "https://api-metrika.yandex.net/management/v1"
YANDEX_METRIKA_STAT_API_URL = "https://api-metrika.yandex.net/stat/v1"
YANDEX_METRIKA_TIMEOUT = 20


def _headers(access_token):
    return {
        "Authorization": f"OAuth {access_token}",
        "Content-Type": "application/json",
    }


def _safe_error(response):
    try:
        data = response.json()
        if isinstance(data, dict):
            errors = data.get("errors")
            if errors and isinstance(errors, list):
                first_error = errors[0] or {}
                return first_error.get("message") or first_error.get("error_type")
            return data.get("message") or data.get("error") or response.reason
    except ValueError:
        pass
    return response.reason or f"HTTP {response.status_code}"


def _api_get(access_token, base_url, path, params=None):
    try:
        response = requests.get(
            f"{base_url}{path}",
            headers=_headers(access_token),
            params=params or {},
            timeout=YANDEX_METRIKA_TIMEOUT,
        )
        if response.status_code >= 400:
            return {
                "ok": False,
                "status_code": response.status_code,
                "error": _safe_error(response),
            }
        return {"ok": True, "data": response.json(), "error": None}
    except requests.Timeout:
        return {"ok": False, "status_code": None, "data": None, "error": "timeout"}
    except requests.RequestException as exc:
        return {"ok": False, "status_code": None, "data": None, "error": exc.__class__.__name__}
    except ValueError:
        return {"ok": False, "status_code": None, "data": None, "error": "invalid_json"}


def normalize_domain(value):
    raw = str(value or "").strip()
    if not raw:
        return ""

    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = parsed.netloc or parsed.path
    host = host.lower().split("@")[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host.rstrip("/")


def _counter_candidates(counter):
    values = [
        counter.get("site"),
        counter.get("site2"),
        counter.get("name"),
        counter.get("domain"),
    ]

    for mirror in counter.get("mirrors") or []:
        if isinstance(mirror, dict):
            values.extend([mirror.get("site"), mirror.get("url"), mirror.get("name")])
        else:
            values.append(mirror)

    return [value for value in values if value]


def get_counters(access_token):
    result = _api_get(
        access_token,
        YANDEX_METRIKA_MANAGEMENT_API_URL,
        "/counters",
        params={"field": "goals,mirrors", "per_page": 10000},
    )
    if not result["ok"]:
        return {
            "ok": False,
            "counters": [],
            "status_code": result.get("status_code"),
            "error": result.get("error"),
        }

    data = result.get("data") or {}
    return {
        "ok": True,
        "counters": data.get("counters") or [],
        "status_code": result.get("status_code"),
        "error": None,
    }


def find_matching_counter(access_token, site_url):
    counters_result = get_counters(access_token)
    if not counters_result["ok"]:
        return {
            "ok": False,
            "found": False,
            "counter": None,
            "counter_id": None,
            "counters": [],
            "site_domain": normalize_domain(site_url),
            "status_code": counters_result.get("status_code"),
            "error": counters_result.get("error"),
        }

    site_domain = normalize_domain(site_url)
    for counter in counters_result["counters"]:
        for candidate in _counter_candidates(counter):
            if normalize_domain(candidate) == site_domain:
                counter_id = counter.get("id")
                return {
                    "ok": True,
                    "found": True,
                    "counter": counter,
                    "counter_id": counter_id,
                    "counters": counters_result["counters"],
                    "site_domain": site_domain,
                    "status_code": counters_result.get("status_code"),
                    "error": None,
                }

    return {
        "ok": True,
        "found": False,
        "counter": None,
        "counter_id": None,
        "counters": counters_result["counters"],
        "site_domain": site_domain,
        "status_code": counters_result.get("status_code"),
        "error": None,
    }


def get_counter_summary(access_token, counter_id):
    return _api_get(
        access_token,
        YANDEX_METRIKA_MANAGEMENT_API_URL,
        f"/counter/{counter_id}",
        params={"field": "goals,mirrors,grants,operations,counter_flags"},
    )


def get_visits_report(access_token, counter_id, date_from="30daysAgo", date_to="today"):
    result = _api_get(
        access_token,
        YANDEX_METRIKA_STAT_API_URL,
        "/data",
        params={
            "ids": counter_id,
            "metrics": "ym:s:visits,ym:s:pageviews,ym:s:users,ym:s:bounceRate",
            "date1": date_from,
            "date2": date_to,
            "accuracy": "full",
            "lang": "ru",
        },
    )
    if not result["ok"]:
        return result

    data = result.get("data") or {}
    totals = data.get("totals") or []
    return {
        "ok": True,
        "data": data,
        "summary": {
            "visits": totals[0] if len(totals) > 0 else 0,
            "pageviews": totals[1] if len(totals) > 1 else 0,
            "users": totals[2] if len(totals) > 2 else 0,
            "bounce_rate": totals[3] if len(totals) > 3 else 0,
        },
        "status_code": result.get("status_code"),
        "error": None,
    }


def get_goals(access_token, counter_id):
    result = get_counter_summary(access_token, counter_id)
    if not result["ok"]:
        return {
            "ok": False,
            "goals": [],
            "status_code": result.get("status_code"),
            "error": result.get("error"),
        }

    counter = (result.get("data") or {}).get("counter") or {}
    return {
        "ok": True,
        "goals": counter.get("goals") or [],
        "status_code": result.get("status_code"),
        "error": None,
    }


def get_traffic_sources_report(access_token, counter_id, date_from="30daysAgo", date_to="today"):
    result = _api_get(
        access_token,
        YANDEX_METRIKA_STAT_API_URL,
        "/data",
        params={
            "ids": counter_id,
            "metrics": "ym:s:visits",
            "dimensions": "ym:s:lastsignTrafficSource",
            "date1": date_from,
            "date2": date_to,
            "accuracy": "full",
            "lang": "ru",
            "limit": 100,
        },
    )
    if not result["ok"]:
        return result

    search_visits = 0
    ads_visits = 0
    rows = (result.get("data") or {}).get("data") or []
    for row in rows:
        dimensions = row.get("dimensions") or []
        source = (dimensions[0] if dimensions else {}) or {}
        source_text = " ".join([
            str(source.get("id") or ""),
            str(source.get("name") or ""),
        ]).lower()
        visits = (row.get("metrics") or [0])[0] or 0

        if any(marker in source_text for marker in ("organic", "search", "поиск", "переходы из поисковых")):
            search_visits += visits
        if any(marker in source_text for marker in ("ad", "advert", "yandex_direct", "ya_direct", "реклам", "директ")):
            ads_visits += visits

    return {
        "ok": True,
        "data": result.get("data") or {},
        "summary": {
            "search_visits": search_visits,
            "ads_visits": ads_visits,
        },
        "status_code": result.get("status_code"),
        "error": None,
    }


def get_traffic_summary(access_token, counter_id, date_from="30daysAgo", date_to="today"):
    visits_report = get_visits_report(access_token, counter_id, date_from, date_to)
    if not visits_report.get("ok"):
        return visits_report

    sources_report = get_traffic_sources_report(access_token, counter_id, date_from, date_to)
    summary = dict(visits_report.get("summary") or {})
    if sources_report.get("ok"):
        summary.update(sources_report.get("summary") or {})
    else:
        summary.update({"search_visits": 0, "ads_visits": 0})

    return {
        "ok": True,
        "summary": summary,
        "visits_report": visits_report,
        "sources_report": sources_report,
        "status_code": visits_report.get("status_code"),
        "error": None,
    }


def get_search_traffic_anomaly(access_token, counter_id):
    yesterday_report = get_traffic_sources_report(access_token, counter_id, "yesterday", "yesterday")
    baseline_report = get_traffic_sources_report(access_token, counter_id, "29daysAgo", "2daysAgo")

    if not yesterday_report.get("ok"):
        return yesterday_report
    if not baseline_report.get("ok"):
        return baseline_report

    yesterday_value = float((yesterday_report.get("summary") or {}).get("search_visits") or 0)
    baseline_total = float((baseline_report.get("summary") or {}).get("search_visits") or 0)
    baseline_average = baseline_total / 28 if baseline_total else 0

    if baseline_average <= 0:
        return {
            "ok": True,
            "has_enough_data": False,
            "anomaly": False,
            "yesterday_value": yesterday_value,
            "baseline_average": baseline_average,
            "deviation_percent": 0,
            "error": None,
        }

    deviation_percent = ((yesterday_value - baseline_average) / baseline_average) * 100
    return {
        "ok": True,
        "has_enough_data": True,
        "anomaly": abs(deviation_percent) > 20,
        "yesterday_value": round(yesterday_value, 2),
        "baseline_average": round(baseline_average, 2),
        "deviation_percent": round(deviation_percent, 1),
        "error": None,
    }


def friendly_metrika_error(result):
    status_code = (result or {}).get("status_code")
    if status_code == 403:
        return "Нет доступа к Метрике. Проверьте права OAuth-приложения и доступ к счётчику."
    if status_code == 401:
        return "Нужно переподключить Яндекс."
    return "API Яндекс Метрики сейчас недоступен или вернул ошибку."


def collect_yandex_traffic_snapshot(user_id, site_id):
    site = get_site_by_id(site_id, user_id=user_id)
    if not site:
        return {"ok": False, "error": "site_not_found"}

    access_token, token_error = get_yandex_access_token(user_id)
    if token_error or not access_token:
        return {"ok": False, "error": token_error or "token_not_found"}

    match = find_matching_counter(access_token, site[3])
    if match.get("status_code") == 401:
        access_token, token_error = get_yandex_access_token(user_id, force_refresh=True)
        if token_error or not access_token:
            return {"ok": False, "error": "reconnect_required"}
        match = find_matching_counter(access_token, site[3])

    if not match.get("ok"):
        return {"ok": False, "error": match.get("error"), "status_code": match.get("status_code")}
    if not match.get("found"):
        return {"ok": False, "error": "counter_not_found"}

    traffic = get_traffic_summary(access_token, match.get("counter_id"), "3daysAgo", "yesterday")
    if traffic.get("status_code") == 401:
        access_token, token_error = get_yandex_access_token(user_id, force_refresh=True)
        if token_error or not access_token:
            return {"ok": False, "error": "reconnect_required"}
        traffic = get_traffic_summary(access_token, match.get("counter_id"), "3daysAgo", "yesterday")

    if not traffic.get("ok"):
        return {"ok": False, "error": traffic.get("error"), "status_code": traffic.get("status_code")}

    summary = traffic.get("summary") or {}
    snapshot_id = save_yandex_traffic_snapshot(
        user_id=user_id,
        site_id=site_id,
        counter_id=match.get("counter_id"),
        date_from="3daysAgo",
        date_to="yesterday",
        visits=summary.get("visits"),
        pageviews=summary.get("pageviews"),
        users=summary.get("users"),
        bounce_rate=summary.get("bounce_rate"),
        search_visits=summary.get("search_visits"),
        ads_visits=summary.get("ads_visits"),
    )
    return {
        "ok": True,
        "snapshot_id": snapshot_id,
        "counter_id": match.get("counter_id"),
        "summary": summary,
    }
