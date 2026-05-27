import re
from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup

from database.db import get_serp_results_cache, save_serp_results_cache
from services.yandex_search_service import search_yandex_serp


MAX_SERP_LIMIT = 10

BLOCKED_DOMAINS = {
    "yandex.ru",
    "ya.ru",
    "maps.yandex.ru",
    "yandex.com",
    "vk.com",
    "ok.ru",
    "facebook.com",
    "instagram.com",
    "t.me",
    "telegram.me",
    "youtube.com",
    "youtu.be",
    "dzen.ru",
    "zen.yandex.ru",
    "avito.ru",
    "2gis.ru",
    "zoon.ru",
    "yell.ru",
    "tripadvisor.ru",
    "otzovik.com",
    "irecommend.ru",
}


def normalize_domain(url):
    value = (url or "").strip()
    if not value:
        return ""

    if "://" not in value:
        value = f"https://{value}"

    parsed = urlparse(value)
    domain = (parsed.netloc or parsed.path).lower()
    if "@" in domain:
        domain = domain.rsplit("@", 1)[-1]
    domain = domain.split(":", 1)[0].strip(".")
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def _clean_yandex_url(href):
    if not href:
        return ""

    href = href.strip()
    if href.startswith("//"):
        href = f"https:{href}"

    parsed = urlparse(href)
    if "yandex." in parsed.netloc and parsed.path.startswith("/clck"):
        query = parse_qs(parsed.query)
        for key in ("url", "u"):
            if query.get(key):
                return unquote(query[key][0])

    if parsed.scheme in ("http", "https"):
        return href

    return ""


def _clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _looks_like_captcha(html):
    lowered = (html or "").lower()
    markers = [
        "showcaptcha",
        "captcha",
        "smartcaptcha",
        "подтвердите, что запросы отправляли вы",
        "доступ к сервису временно ограничен",
    ]
    return any(marker in lowered for marker in markers)


def extract_serp_results(html):
    soup = BeautifulSoup(html or "", "lxml")
    results = []
    seen_urls = set()

    containers = soup.select("li.serp-item, div.serp-item, div.organic, li[data-cid]")
    if not containers:
        containers = soup.select("a.Link, a.link, a[href]")

    for container in containers:
        if getattr(container, "name", "") == "a":
            link = container
            title_text = _clean_text(link.get_text(" "))
            snippet_text = ""
        else:
            link = (
                container.select_one("a.Link[href]")
                or container.select_one("a.link[href]")
                or container.select_one("h2 a[href]")
                or container.select_one("a[href]")
            )
            title_node = container.select_one("h2, .organic__title-wrapper, .organic__url-text, a.Link")
            snippet_node = container.select_one(".TextContainer, .organic__text, .extended-text, .serp-item__text")
            title_text = _clean_text(title_node.get_text(" ") if title_node else link.get_text(" ") if link else "")
            snippet_text = _clean_text(snippet_node.get_text(" ") if snippet_node else "")

        url = _clean_yandex_url(link.get("href") if link else "")
        domain = normalize_domain(url)

        if not url or not domain or url in seen_urls:
            continue

        seen_urls.add(url)
        results.append({
            "position": len(results) + 1,
            "title": title_text,
            "url": url,
            "snippet": snippet_text,
            "domain": domain,
        })

        if len(results) >= 30:
            break

    return results


def filter_competitors(results, own_site):
    own_domain = normalize_domain(own_site)
    filtered = []
    seen_domains = set()

    for item in results or []:
        url = item.get("url", "")
        domain = normalize_domain(url or item.get("domain", ""))
        if not url or not domain:
            continue
        if own_domain and (domain == own_domain or domain.endswith(f".{own_domain}") or own_domain.endswith(f".{domain}")):
            continue
        if domain in seen_domains:
            continue
        if domain in BLOCKED_DOMAINS:
            continue
        if any(domain.endswith(f".{blocked}") for blocked in BLOCKED_DOMAINS):
            continue

        seen_domains.add(domain)
        filtered.append({
            "position": item.get("position") or len(filtered) + 1,
            "title": item.get("title", ""),
            "url": url,
            "snippet": item.get("snippet", ""),
            "domain": domain,
        })

    return filtered


def search_competitors(query, city=None, own_site=None, limit=10):
    normalized_query = (query or "").strip()
    normalized_city = (city or "").strip()
    normalized_own_site = (own_site or "").strip()
    safe_limit = max(1, min(int(limit or MAX_SERP_LIMIT), MAX_SERP_LIMIT))
    search_text = " ".join(part for part in [normalized_query, normalized_city] if part).strip()

    if not search_text:
        return {
            "ok": False,
            "source": "error",
            "from_cache": False,
            "message": "Введите поисковый запрос для поиска конкурентов.",
            "results": [],
            "raw_count": 0,
            "error": "Введите поисковый запрос для поиска конкурентов.",
            "status_code": None,
            "raw_preview": "",
        }

    cache = get_serp_results_cache(normalized_query, normalized_city, normalized_own_site, max_age_days=7)
    if cache and isinstance(cache.get("results"), dict):
        cached_results = cache["results"].get("results", [])
        return {
            "ok": bool(cached_results),
            "source": "cache",
            "from_cache": True,
            "message": "Результат из кэша.",
            "results": cached_results[:safe_limit],
            "raw_count": cache["results"].get("raw_count", len(cached_results)),
            "cached_at": cache.get("created_at"),
            "error": None,
            "status_code": None,
            "raw_preview": "",
        }

    api_result = search_yandex_serp(normalized_query, city=normalized_city, limit=safe_limit)
    raw_results = api_result.get("results", [])
    competitors = filter_competitors(raw_results, normalized_own_site)[:safe_limit]

    payload = {
        "results": competitors,
        "raw_count": len(raw_results),
        "search_text": search_text,
    }
    if competitors:
        save_serp_results_cache(normalized_query, normalized_city, normalized_own_site, payload)

    return {
        "ok": bool(competitors),
        "source": "api" if competitors else api_result.get("source", "error"),
        "from_cache": False,
        "message": f"Найдено {len(competitors)} конкурентов." if competitors else api_result.get("message", "Не удалось получить выдачу. Попробуйте позже или введите конкурентов вручную."),
        "results": competitors,
        "raw_count": len(raw_results),
        "status_code": api_result.get("status_code"),
        "error": None if competitors else api_result.get("error"),
        "raw_preview": api_result.get("raw_preview", ""),
    }
