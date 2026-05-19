from urllib.parse import quote

import requests


YANDEX_WEBMASTER_API_URL = "https://api.webmaster.yandex.net/v4"


def get_headers(oauth_token):
    return {
        "Authorization": f"OAuth {oauth_token}",
        "Content-Type": "application/json"
    }


def normalize_domain(value):
    return (
        value
        .replace("https://", "")
        .replace("http://", "")
        .replace("www.", "")
        .replace("/", "")
        .strip()
    )


def get_user_id(oauth_token):
    url = f"{YANDEX_WEBMASTER_API_URL}/user"
    response = requests.get(url, headers=get_headers(oauth_token), timeout=15)

    if response.status_code != 200:
        return None, response.text

    data = response.json()
    return data.get("user_id"), None


def get_hosts(oauth_token, user_id):
    url = f"{YANDEX_WEBMASTER_API_URL}/user/{user_id}/hosts"
    response = requests.get(url, headers=get_headers(oauth_token), timeout=15)

    if response.status_code != 200:
        return None, response.text

    return response.json().get("hosts", []), None


def find_host(hosts, site_domain):
    clean_site_domain = normalize_domain(site_domain)

    for host in hosts:
        unicode_url = host.get("unicode_host_url", "")
        ascii_url = host.get("ascii_host_url", "")
        host_id = host.get("host_id", "")

        if clean_site_domain in normalize_domain(unicode_url):
            return host
        if clean_site_domain in normalize_domain(ascii_url):
            return host
        if clean_site_domain in host_id:
            return host

    return None


def get_summary(oauth_token, user_id, host_id):
    encoded_host_id = quote(host_id, safe="")
    url = f"{YANDEX_WEBMASTER_API_URL}/user/{user_id}/hosts/{encoded_host_id}/summary"
    response = requests.get(url, headers=get_headers(oauth_token), timeout=15)

    if response.status_code != 200:
        return {
            "success": False,
            "error": response.text,
            "status_code": response.status_code
        }

    return {
        "success": True,
        "data": response.json()
    }


def get_diagnostics(oauth_token, user_id, host_id):
    encoded_host_id = quote(host_id, safe="")
    url = f"{YANDEX_WEBMASTER_API_URL}/user/{user_id}/hosts/{encoded_host_id}/diagnostics"
    response = requests.get(url, headers=get_headers(oauth_token), timeout=15)

    if response.status_code != 200:
        return {
            "success": False,
            "error": response.text,
            "status_code": response.status_code
        }

    return {
        "success": True,
        "data": response.json()
    }


def get_yandex_webmaster_data(oauth_token, host_id):
    if not oauth_token:
        return {
            "success": False,
            "error": "OAuth-токен Яндекс Вебмастера не найден."
        }

    user_id, user_error = get_user_id(oauth_token)

    if user_error:
        return {
            "success": False,
            "error": user_error
        }

    hosts, hosts_error = get_hosts(oauth_token, user_id)

    if hosts_error:
        return {
            "success": False,
            "error": hosts_error
        }

    found_host = find_host(hosts, host_id)

    if not found_host:
        return {
            "success": False,
            "error": {
                "message": "Сайт не найден среди доступных сайтов Яндекс Вебмастера",
                "searched_host": host_id,
                "available_hosts": hosts
            }
        }

    real_host_id = found_host.get("host_id")

    summary = get_summary(
        oauth_token=oauth_token,
        user_id=user_id,
        host_id=real_host_id
    )

    diagnostics = get_diagnostics(
        oauth_token=oauth_token,
        user_id=user_id,
        host_id=real_host_id
    )

    return {
        "success": True,
        "user_id": user_id,
        "found_host": found_host,
        "summary": summary,
        "diagnostics": diagnostics
    }
