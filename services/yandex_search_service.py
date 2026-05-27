import base64
import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import requests

from config.settings import YANDEX_SEARCH_API_KEY, YANDEX_SEARCH_FOLDER_ID


YANDEX_SEARCH_API_URL = "https://searchapi.api.cloud.yandex.net/v2/web/search"
YANDEX_SEARCH_TIMEOUT = 10
MAX_SERP_LIMIT = 10
RAW_PREVIEW_LIMIT = 700


def _response(ok=False, results=None, error=None, status_code=None, source="error", raw_preview="", **extra):
    safe_error = _safe_preview(error, limit=500) if error else None
    payload = {
        "ok": bool(ok),
        "results": results or [],
        "error": safe_error,
        "status_code": status_code,
        "source": source if source in {"api", "cache", "error"} else "error",
        "raw_preview": _safe_preview(raw_preview),
    }
    payload.update(extra)
    payload.setdefault("message", safe_error or (f"Найдено {len(payload['results'])} результатов." if ok else "Не удалось получить выдачу."))
    payload.setdefault("raw_count", len(payload["results"]))
    return payload


def _safe_preview(value, limit=RAW_PREVIEW_LIMIT):
    if value is None:
        return ""
    if not isinstance(value, str):
        try:
            value = json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            value = str(value)
    value = value.replace(YANDEX_SEARCH_API_KEY or "\0", "[hidden]")
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit]


def _clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _tag_name(element):
    return element.tag.rsplit("}", 1)[-1].lower()


def _first_text(element, names):
    wanted = {name.lower() for name in names}
    for child in element.iter():
        if _tag_name(child) in wanted:
            text = _clean_text("".join(child.itertext()))
            if text:
                return text
    return ""


def _snippet_text(element):
    snippets = []
    for child in element.iter():
        if _tag_name(child) in {"passage", "headline"}:
            text = _clean_text("".join(child.itertext()))
            if text:
                snippets.append(text)
    return _clean_text(" ".join(snippets[:3]))


def _maybe_decode_raw_data(raw_data):
    value = raw_data or ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    value = str(value).strip()
    if value.startswith("<"):
        return value
    try:
        decoded = base64.b64decode(value).decode("utf-8", errors="ignore").strip()
    except (ValueError, TypeError):
        return value
    return decoded if decoded.startswith("<") else value


def _extract_raw_data(data):
    if not isinstance(data, dict):
        return ""
    candidates = [
        data.get("rawData"),
        data.get("raw_data"),
        data.get("response", {}).get("rawData") if isinstance(data.get("response"), dict) else None,
        data.get("result", {}).get("rawData") if isinstance(data.get("result"), dict) else None,
    ]
    for value in candidates:
        if value:
            return value
    return ""


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


def normalize_serp_results(raw_data, limit=10):
    safe_limit = max(1, min(int(limit or MAX_SERP_LIMIT), MAX_SERP_LIMIT))
    xml_text = _maybe_decode_raw_data(raw_data)
    if not xml_text:
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    results = []
    seen_urls = set()
    for element in root.iter():
        if _tag_name(element) != "doc":
            continue
        url = _first_text(element, ["url"])
        domain = normalize_domain(url or _first_text(element, ["domain"]))
        if not url or not domain or url in seen_urls:
            continue
        seen_urls.add(url)
        title = _first_text(element, ["title", "headline"])
        snippet = _snippet_text(element)
        results.append({
            "position": len(results) + 1,
            "title": title,
            "url": url,
            "snippet": snippet,
            "domain": domain,
        })
        if len(results) >= safe_limit:
            break
    return results


def extract_domains(results):
    domains = []
    seen = set()
    for item in results or []:
        domain = normalize_domain(item.get("url") or item.get("domain"))
        if domain and domain not in seen:
            seen.add(domain)
            domains.append(domain)
    return domains


def search_yandex_serp(query, city=None, limit=10):
    try:
        normalized_query = (query or "").strip()
        normalized_city = (city or "").strip()
        safe_limit = max(1, min(int(limit or MAX_SERP_LIMIT), MAX_SERP_LIMIT))
        search_text = " ".join(part for part in [normalized_query, normalized_city] if part).strip()

        if not search_text:
            return _response(
                error="Введите поисковый запрос для поиска конкурентов.",
                request_sent=False,
            )

        if not YANDEX_SEARCH_API_KEY or not YANDEX_SEARCH_FOLDER_ID:
            return _response(
                error="Yandex Search API не настроен.",
                request_sent=False,
            )

        body = {
            "query": {
                "searchType": "SEARCH_TYPE_RU",
                "queryText": search_text,
                "familyMode": "FAMILY_MODE_MODERATE",
                "page": "0",
                "fixTypoMode": "FIX_TYPO_MODE_ON",
            },
            "sortSpec": {
                "sortMode": "SORT_MODE_BY_RELEVANCE",
                "sortOrder": "SORT_ORDER_DESC",
            },
            "groupSpec": {
                "groupMode": "GROUP_MODE_DEEP",
                "groupsOnPage": str(safe_limit),
                "docsInGroup": "1",
            },
            "maxPassages": "3",
            "l10n": "LOCALIZATION_RU",
            "folderId": YANDEX_SEARCH_FOLDER_ID,
            "responseFormat": "FORMAT_XML",
            "userAgent": "TechSEO Monitor competitor analysis",
        }
        headers = {
            "Authorization": f"Api-Key {YANDEX_SEARCH_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            response = requests.post(
                YANDEX_SEARCH_API_URL,
                headers=headers,
                json=body,
                timeout=YANDEX_SEARCH_TIMEOUT,
            )
        except requests.RequestException as exc:
            return _response(
                error=f"Не удалось обратиться к Yandex Search API: {exc.__class__.__name__}.",
                source="error",
                request_sent=True,
            )

        status_code = response.status_code
        raw_preview = response.text
        try:
            data = response.json()
        except ValueError:
            data = {}

        if status_code >= 400:
            api_error = None
            if isinstance(data, dict):
                api_error = data.get("message") or data.get("error") or data.get("description")
            return _response(
                error=api_error or f"Yandex Search API вернул HTTP {status_code}.",
                status_code=status_code,
                source="error",
                raw_preview=raw_preview,
                request_sent=True,
            )

        raw_data = _extract_raw_data(data)
        if not raw_data and response.text.lstrip().startswith("<"):
            raw_data = response.text
        results = normalize_serp_results(raw_data, safe_limit)
        if not results:
            return _response(
                error="Yandex Search API не вернул органическую выдачу или формат ответа не распознан.",
                status_code=status_code,
                source="api",
                raw_preview=raw_data or raw_preview,
                request_sent=True,
                search_text=search_text,
            )

        return _response(
            ok=True,
            results=results,
            error=None,
            status_code=status_code,
            source="api",
            raw_preview=raw_data,
            request_sent=True,
            search_text=search_text,
            message=f"Найдено {len(results)} результатов через Yandex Search API.",
        )
    except Exception as exc:
        return _response(
            error=f"Внутренняя ошибка диагностики Yandex Search API: {exc.__class__.__name__}.",
            source="error",
            request_sent=False,
        )
