from urllib.parse import quote, urlparse

import requests


YANDEX_WEBMASTER_API_URL = "https://api.webmaster.yandex.net/v4"
YANDEX_WEBMASTER_TIMEOUT = 20


def _headers(access_token):
    return {
        "Authorization": f"OAuth {access_token}",
        "Content-Type": "application/json",
    }


def _api_get(access_token, path):
    try:
        response = requests.get(
            f"{YANDEX_WEBMASTER_API_URL}{path}",
            headers=_headers(access_token),
            timeout=YANDEX_WEBMASTER_TIMEOUT,
        )
        if response.status_code >= 400:
            return {
                "ok": False,
                "status_code": response.status_code,
                "error": _safe_error(response),
            }
        return {"ok": True, "data": response.json()}
    except requests.Timeout:
        return {"ok": False, "status_code": None, "error": "timeout"}
    except requests.RequestException as exc:
        return {"ok": False, "status_code": None, "error": exc.__class__.__name__}
    except ValueError:
        return {"ok": False, "status_code": None, "error": "invalid_json"}


def _safe_error(response):
    try:
        data = response.json()
        if isinstance(data, dict):
            return data.get("message") or data.get("error") or response.reason
    except ValueError:
        pass
    return response.reason or f"HTTP {response.status_code}"


def normalize_domain(value):
    raw = str(value or "").strip()
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = parsed.netloc or parsed.path
    host = host.lower().split("@")[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host.rstrip("/")


def _host_candidates(host):
    return [
        host.get("unicode_host_url", ""),
        host.get("ascii_host_url", ""),
        host.get("host_url", ""),
        host.get("host_id", ""),
    ]


def _encoded_host_id(host_id):
    return quote(str(host_id or ""), safe="")


def _get_user_id(access_token):
    result = _api_get(access_token, "/user")
    if not result["ok"]:
        return None, result
    return result["data"].get("user_id"), result


def get_user_hosts(access_token):
    user_id, user_result = _get_user_id(access_token)
    if not user_id:
        return {
            "ok": False,
            "user_id": None,
            "hosts": [],
            "error": user_result.get("error") if user_result else "user_not_found",
        }

    hosts_result = _api_get(access_token, f"/user/{user_id}/hosts")
    if not hosts_result["ok"]:
        return {
            "ok": False,
            "user_id": user_id,
            "hosts": [],
            "error": hosts_result.get("error"),
        }

    return {
        "ok": True,
        "user_id": user_id,
        "hosts": hosts_result["data"].get("hosts", []),
        "error": None,
    }


def find_matching_host(access_token, site_url):
    hosts_result = get_user_hosts(access_token)
    if not hosts_result["ok"]:
        return {
            "ok": False,
            "found": False,
            "user_id": hosts_result.get("user_id"),
            "host": None,
            "host_id": None,
            "hosts": hosts_result.get("hosts", []),
            "error": hosts_result.get("error"),
        }

    site_domain = normalize_domain(site_url)
    for host in hosts_result["hosts"]:
        for candidate in _host_candidates(host):
            if normalize_domain(candidate) == site_domain:
                return {
                    "ok": True,
                    "found": True,
                    "user_id": hosts_result["user_id"],
                    "host": host,
                    "host_id": host.get("host_id"),
                    "hosts": hosts_result["hosts"],
                    "error": None,
                }

    return {
        "ok": True,
        "found": False,
        "user_id": hosts_result["user_id"],
        "host": None,
        "host_id": None,
        "hosts": hosts_result["hosts"],
        "error": None,
    }


def get_host_summary(access_token, host_id):
    user_id, user_result = _get_user_id(access_token)
    if not user_id:
        return {"ok": False, "data": None, "error": user_result.get("error")}
    return _api_get(access_token, f"/user/{user_id}/hosts/{_encoded_host_id(host_id)}/summary")


def get_indexing_status(access_token, host_id):
    user_id, user_result = _get_user_id(access_token)
    if not user_id:
        return {"ok": False, "data": None, "error": user_result.get("error")}
    return _api_get(access_token, f"/user/{user_id}/hosts/{_encoded_host_id(host_id)}/indexing-history")


def get_sitemap_info(access_token, host_id):
    user_id, user_result = _get_user_id(access_token)
    if not user_id:
        return {"ok": False, "data": None, "error": user_result.get("error")}
    return _api_get(access_token, f"/user/{user_id}/hosts/{_encoded_host_id(host_id)}/sitemaps")


def get_robots_info(access_token, host_id):
    user_id, user_result = _get_user_id(access_token)
    if not user_id:
        return {"ok": False, "data": None, "error": user_result.get("error")}
    return _api_get(access_token, f"/user/{user_id}/hosts/{_encoded_host_id(host_id)}/robots")
