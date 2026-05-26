from urllib.parse import urlparse

import requests


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
        return {"ok": False, "counters": [], "error": result.get("error")}

    data = result.get("data") or {}
    return {
        "ok": True,
        "counters": data.get("counters") or [],
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
                    "error": None,
                }

    return {
        "ok": True,
        "found": False,
        "counter": None,
        "counter_id": None,
        "counters": counters_result["counters"],
        "error": None,
    }


def get_counter_summary(access_token, counter_id):
    return _api_get(
        access_token,
        YANDEX_METRIKA_MANAGEMENT_API_URL,
        f"/counter/{counter_id}",
        params={"field": "goals,mirrors,grants,operations,counter_flags"},
    )


def get_visits_report(access_token, counter_id):
    result = _api_get(
        access_token,
        YANDEX_METRIKA_STAT_API_URL,
        "/data",
        params={
            "ids": counter_id,
            "metrics": "ym:s:visits,ym:s:pageviews,ym:s:bounceRate",
            "date1": "30daysAgo",
            "date2": "today",
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
            "bounce_rate": totals[2] if len(totals) > 2 else 0,
        },
        "error": None,
    }


def get_goals(access_token, counter_id):
    result = get_counter_summary(access_token, counter_id)
    if not result["ok"]:
        return {"ok": False, "goals": [], "error": result.get("error")}

    counter = (result.get("data") or {}).get("counter") or {}
    return {
        "ok": True,
        "goals": counter.get("goals") or [],
        "error": None,
    }
