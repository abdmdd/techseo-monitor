import logging
import os
import xml.etree.ElementTree as ET
from collections import deque
from urllib.parse import parse_qsl, urlencode, urldefrag, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright
from requests import exceptions as request_exceptions


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "12"))
PLAYWRIGHT_TIMEOUT = int(os.getenv("PLAYWRIGHT_TIMEOUT", "45000"))
MAX_SITEMAP_URLS = 200
MAX_SITEMAP_BYTES = 5 * 1024 * 1024
MAX_REDIRECT_HOPS = 10
FULL_CRAWL_MAX_PAGES = int(os.getenv("FULL_CRAWL_MAX_PAGES", "30"))
FULL_CRAWL_MAX_LINKS_PER_PAGE = int(os.getenv("FULL_CRAWL_MAX_LINKS_PER_PAGE", "250"))


# ==================================================
# BASIC HELPERS
# ==================================================

def add_warning(results, message):
    results.setdefault("crawler_warnings", []).append(message)
    logger.warning(message)


def compact_exception_message(exc, limit=240):
    message = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
    return message[:limit]


def get_base_url(url):
    parsed = urlparse(url)

    if not parsed.scheme or not parsed.netloc:
        return ""

    return f"{parsed.scheme}://{parsed.netloc}"


def normalize_domain(url):
    parsed = urlparse(url)
    return parsed.netloc.replace("www.", "").lower()


def is_internal_link(base_url, link_url):
    return normalize_domain(base_url) == normalize_domain(link_url)


def clean_url(url):
    return url.split("#")[0].strip()


def normalize_url(url, base_url=""):
    if not url:
        return ""

    raw_url = str(url).strip()
    lowered = raw_url.lower()

    if lowered.startswith(("mailto:", "tel:", "javascript:", "data:", "sms:", "whatsapp:")):
        return ""

    joined_url = urljoin(base_url, raw_url) if base_url else raw_url
    joined_url, _ = urldefrag(joined_url)
    parsed = urlparse(joined_url)

    if parsed.scheme not in ["http", "https"] or not parsed.netloc:
        return ""

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    path = parsed.path or "/"

    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    query = urlencode(sorted(query_pairs), doseq=True)

    return urlunparse((scheme, netloc, path, "", query, ""))


def should_crawl_url(url, base_url):
    normalized_url = normalize_url(url, base_url)

    if not normalized_url:
        return ""

    if not is_internal_link(base_url, normalized_url):
        return ""

    return normalized_url


def response_status_label(response):
    if response.status_code in [403, 429]:
        return f"HTTP {response.status_code}: доступ ограничен"

    if 500 <= response.status_code <= 599:
        return f"HTTP {response.status_code}: ошибка сервера"

    return f"HTTP {response.status_code}"


def safe_get(url, headers, timeout=REQUEST_TIMEOUT, allow_redirects=True):
    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=allow_redirects
        )
        return response, None
    except request_exceptions.Timeout:
        return None, "timeout"
    except request_exceptions.SSLError:
        return None, "ssl_error"
    except request_exceptions.TooManyRedirects:
        return None, "too_many_redirects"
    except request_exceptions.ConnectionError:
        return None, "connection_error"
    except request_exceptions.RequestException as exc:
        return None, f"request_error: {exc}"


# ==================================================
# SITEMAP
# ==================================================

def extract_sitemap_urls(sitemap_content):
    try:
        ET.fromstring(sitemap_content.encode("utf-8"))
    except ET.ParseError:
        return [], False

    soup = BeautifulSoup(sitemap_content, "xml")
    loc_tags = soup.find_all("loc")
    return [tag.get_text(strip=True) for tag in loc_tags], True


def analyze_sitemap(base_url, headers, results):
    sitemap_url = urljoin(base_url, "/sitemap.xml")
    results["sitemap_url"] = sitemap_url
    response, error = safe_get(sitemap_url, headers=headers, timeout=15)

    if error:
        results["sitemap_status_code"] = "request_error"
        results["sitemap"] = "❌ Ошибка"
        results["errors"].append(f"Ошибка проверки sitemap.xml: {error}")
        add_warning(results, f"Sitemap request failed for {sitemap_url}: {error}")
        return []

    results["sitemap_status_code"] = response.status_code

    if response.status_code == 404:
        results["sitemap"] = "❌ Не найден"
        results["errors"].append("Sitemap.xml не найден")
        results["recommendations"].append("Добавить sitemap.xml и указать его в robots.txt.")
        return []

    if response.status_code != 200:
        results["sitemap"] = "❌ Недоступен"
        status_label = response_status_label(response)
        results["errors"].append(f"Sitemap.xml недоступен: {status_label}")
        add_warning(results, f"Sitemap returned {status_label} for {sitemap_url}")
        return []

    sitemap_content = response.text or ""
    results["sitemap_content"] = sitemap_content
    results["sitemap"] = "✅ Найден"

    if len(response.content or b"") > MAX_SITEMAP_BYTES:
        add_warning(
            results,
            f"Sitemap.xml слишком большой, обработка ограничена первыми {MAX_SITEMAP_URLS} URL"
        )

    sitemap_urls, is_valid_xml = extract_sitemap_urls(sitemap_content)

    if is_valid_xml:
        results["sitemap_valid"] = "✅ XML валиден"
    else:
        results["sitemap_valid"] = "❌ Некорректный XML"
        results["errors"].append("Sitemap.xml содержит некорректный XML")
        return []

    sitemap_lower = sitemap_content.lower()

    if "<sitemapindex" in sitemap_lower:
        results["sitemap_type"] = "sitemapindex"
    elif "<urlset" in sitemap_lower:
        results["sitemap_type"] = "urlset"
    else:
        results["sitemap_type"] = "не определен"
        results["errors"].append("Не удалось определить тип sitemap.xml")

    if len(sitemap_urls) > MAX_SITEMAP_URLS:
        add_warning(
            results,
            f"Sitemap содержит {len(sitemap_urls)} URL, для аудита взяты первые {MAX_SITEMAP_URLS}"
        )
        sitemap_urls = sitemap_urls[:MAX_SITEMAP_URLS]

    results["sitemap_urls_count"] = len(sitemap_urls)
    results["sitemap_urls"] = sitemap_urls[:MAX_SITEMAP_URLS]
    results["sitemap_sample_urls"] = sitemap_urls[:10]

    if "<lastmod>" in sitemap_lower:
        results["sitemap_lastmod"] = "✅ Используется"
        lastmod_tags = BeautifulSoup(sitemap_content, "xml").find_all("lastmod")
        results["sitemap_lastmod_values"] = [tag.get_text(strip=True) for tag in lastmod_tags[:5]]
    else:
        results["sitemap_lastmod"] = "❌ Не используется"
        results["sitemap_lastmod_values"] = []

    if sitemap_urls:
        results["sitemap_empty"] = "✅ Sitemap не пустой"
    else:
        results["sitemap_empty"] = "❌ Sitemap пустой"
        results["errors"].append("Sitemap.xml пустой")

    if "http://" in sitemap_content:
        results["errors"].append("В sitemap найдены HTTP URL")

    return sitemap_urls


# ==================================================
# ROBOTS
# ==================================================

def analyze_robots(base_url, headers, results):
    robots_url = urljoin(base_url, "/robots.txt")
    results["robots_url"] = robots_url
    response, error = safe_get(robots_url, headers=headers, timeout=10)

    if error:
        results["robots_status_code"] = "request_error"
        results["robots_txt"] = "Ошибка проверки"
        message = f"Не удалось получить robots.txt: {error}"
        results["robots_errors"].append(message)
        results["errors"].append("Ошибка проверки robots.txt")
        add_warning(results, f"Robots request failed for {robots_url}: {error}")
        return

    results["robots_status_code"] = response.status_code

    if response.status_code == 404:
        results["robots_txt"] = "❌ Не найден"
        results["errors"].append("robots.txt не найден")
        results["recommendations"].append("Добавить robots.txt в корень сайта.")
        return

    if response.status_code != 200:
        results["robots_txt"] = "❌ Недоступен"
        status_label = response_status_label(response)
        results["errors"].append(f"robots.txt недоступен: {status_label}")
        add_warning(results, f"Robots returned {status_label} for {robots_url}")
        return

    robots_text = response.text or ""
    robots_lower = robots_text.lower()

    results["robots_txt"] = "✅ Найден"
    results["robots_content"] = robots_text

    if not robots_text.strip():
        results["robots_errors"].append("robots.txt пустой")

    if "sitemap:" not in robots_lower:
        results["robots_errors"].append("В robots.txt отсутствует Sitemap")

    if "user-agent" not in robots_lower:
        results["robots_errors"].append("В robots.txt отсутствует User-agent")

    if "disallow: /" in robots_lower:
        results["robots_errors"].append(
            "Есть правило Disallow: / — проверьте, не закрыт ли сайт от индексации"
        )

    important_paths = [
        "/catalog",
        "/category",
        "/product",
        "/shop",
        "/services",
        "/blog",
        "/articles",
        "/contacts",
    ]
    blocked_important_sections = []

    for line in robots_text.splitlines():
        cleaned_line = line.strip().lower()
        if not cleaned_line.startswith("disallow:"):
            continue

        rule_path = cleaned_line.split(":", 1)[1].strip()
        for important_path in important_paths:
            normalized_rule = rule_path.rstrip("*")
            if rule_path and (important_path.startswith(normalized_rule) or normalized_rule.startswith(important_path)):
                blocked_important_sections.append(rule_path)

    results["robots_has_user_agent"] = "user-agent" in robots_lower
    results["robots_has_sitemap"] = "sitemap:" in robots_lower
    results["robots_full_block"] = "disallow: /" in robots_lower
    results["robots_blocked_important_sections"] = sorted(set(blocked_important_sections))

    for error_message in results["robots_errors"]:
        results["errors"].append(error_message)


# ==================================================
# PAGE SEO
# ==================================================

def parse_page_meta(page_url, html):
    soup = BeautifulSoup(html or "", "lxml")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    meta_description = soup.find("meta", attrs={"name": "description"})
    description = (
        meta_description.get("content", "").strip()
        if meta_description and meta_description.get("content")
        else ""
    )

    canonical_tag = soup.find("link", rel="canonical")
    canonical = (
        canonical_tag.get("href", "").strip()
        if canonical_tag and canonical_tag.get("href")
        else ""
    )

    meta_robots_tag = soup.find("meta", attrs={"name": "robots"})
    meta_robots = (
        meta_robots_tag.get("content", "").strip()
        if meta_robots_tag and meta_robots_tag.get("content")
        else ""
    )

    h1_tags = soup.find_all("h1")
    h1_list = [h.get_text(strip=True) for h in h1_tags]
    viewport = soup.find("meta", attrs={"name": "viewport"})
    body = soup.find("body")

    images = soup.find_all("img")
    images_without_alt_list = []

    for img in images:
        alt = img.get("alt")
        src = img.get("src")

        if not alt:
            image_url = urljoin(page_url, src) if src else "src не найден"
            images_without_alt_list.append({
                "image_url": image_url,
                "page_url": page_url
            })

    links = soup.find_all("a", href=True)
    found_links = []

    for link in links:
        href = link.get("href")

        if not href or href.startswith("#"):
            continue

        if href.startswith("mailto:") or href.startswith("tel:"):
            continue

        full_link = clean_url(urljoin(page_url, href))
        parsed = urlparse(full_link)

        if parsed.scheme in ["http", "https"]:
            found_links.append(full_link)

    return {
        "url": page_url,
        "title": title,
        "description": description,
        "canonical": canonical,
        "meta_robots": meta_robots,
        "h1_list": h1_list,
        "h1_count": len(h1_list),
        "mobile_friendly": viewport is not None,
        "body_empty": body is None or not body.get_text(strip=True),
        "images_total": len(images),
        "images_without_alt_list": images_without_alt_list,
        "image_alt_coverage": (
            round(((len(images) - len(images_without_alt_list)) / len(images)) * 100, 1)
            if images else 100
        ),
        "links": found_links
    }


def fetch_main_page_html(url, headers, results):
    browser = None
    playwright = None

    try:
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 390, "height": 844})
        response = page.goto(url, wait_until="domcontentloaded", timeout=PLAYWRIGHT_TIMEOUT)
        if response and response.status >= 400:
            status_label = f"HTTP {response.status}"
            results["errors"].append(f"Главная страница вернула {status_label}")
            add_warning(results, f"Main page returned {status_label} for {url}")
        return page.content(), "playwright"
    except PlaywrightTimeoutError:
        add_warning(results, f"Playwright timeout for {url}; fallback to requests")
    except PlaywrightError as exc:
        message = compact_exception_message(exc)
        add_warning(results, f"Playwright failed for {url}; fallback to requests: {message}")
    except Exception as exc:
        message = compact_exception_message(exc)
        add_warning(results, f"Unexpected Playwright error for {url}; fallback to requests: {message}")
    finally:
        if browser:
            try:
                browser.close()
            except Exception as exc:
                add_warning(results, f"Failed to close Playwright browser: {exc}")
        if playwright:
            try:
                playwright.stop()
            except Exception as exc:
                add_warning(results, f"Failed to stop Playwright: {exc}")

    response, error = safe_get(url, headers=headers, timeout=20)

    if error:
        results["errors"].append(f"Не удалось получить главную страницу: {error}")
        add_warning(results, f"Main page fallback request failed for {url}: {error}")
        return "", "error"

    if response.status_code != 200:
        status_label = response_status_label(response)
        results["errors"].append(f"Главная страница недоступна: {status_label}")
        add_warning(results, f"Main page returned {status_label} for {url}")
        return response.text or "", "requests"

    return response.text or "", "requests"


def analyze_main_page(url, headers, results):
    html, source = fetch_main_page_html(url, headers, results)
    results["main_page_fetch_source"] = source

    if not html.strip():
        results["errors"].append("Главная страница пустая или недоступна")
        results["recommendations"].append("Проверить доступность главной страницы и ответ сервера.")

    meta = parse_page_meta(url, html)

    title = meta["title"]
    description = meta["description"]
    canonical = meta["canonical"]
    h1_list = meta["h1_list"]

    if meta["body_empty"]:
        results["errors"].append("Body страницы пустой")
        results["recommendations"].append("Проверить HTML-разметку и серверный ответ страницы.")

    if title:
        results["title"] = title
        results["title_length"] = len(title)

        if len(title) < 30:
            results["errors"].append("Title слишком короткий")
            results["recommendations"].append("Увеличить Title до 50–70 символов.")

        if len(title) > 80:
            results["errors"].append("Title слишком длинный")
            results["recommendations"].append("Сократить Title до 50–70 символов.")
    else:
        results["title"] = "Нет Title"
        results["errors"].append("Отсутствует Title")
        results["recommendations"].append("Добавить уникальный Title для страницы.")

    if description:
        results["description"] = description
        results["description_length"] = len(description)

        if len(description) < 70:
            results["errors"].append("Description слишком короткий")
            results["recommendations"].append("Расширить Description до 120–160 символов.")

        if len(description) > 200:
            results["errors"].append("Description слишком длинный")
            results["recommendations"].append("Сократить Description до 120–160 символов.")
    else:
        results["description"] = "Нет Description"
        results["errors"].append("Отсутствует Description")
        results["recommendations"].append("Добавить Description с описанием страницы.")

    if canonical:
        results["canonical"] = canonical
    else:
        results["canonical"] = "Нет canonical"
        results["errors"].append("Отсутствует canonical")
        results["recommendations"].append("Добавить canonical на основную версию страницы.")

    results["h1_count"] = meta["h1_count"]

    if len(h1_list) == 0:
        results["h1"] = "Нет H1"
        results["errors"].append("Отсутствует H1")
        results["recommendations"].append("Добавить один основной H1 на страницу.")
    elif len(h1_list) == 1:
        results["h1"] = h1_list[0]
    else:
        results["h1"] = " | ".join(h1_list)
        results["errors"].append("На странице несколько H1")
        results["recommendations"].append("Оставить один H1, остальные заменить на H2/H3.")

    results["mobile_friendly"] = meta["mobile_friendly"]

    if not meta["mobile_friendly"]:
        results["errors"].append("Не найден viewport для мобильной версии")
        results["recommendations"].append("Добавить meta viewport для мобильной версии.")

    results["images_total"] = meta["images_total"]
    results["images_without_alt_list"] = meta["images_without_alt_list"]
    results["images_without_alt"] = len(meta["images_without_alt_list"])

    if results["images_without_alt"] > 0:
        results["errors"].append(f"Изображений без alt: {results['images_without_alt']}")
        results["recommendations"].append("Добавить alt-тексты для всех важных изображений.")

    results["links_total"] = len(meta["links"])

    return meta


# ==================================================
# FULL WEBSITE CRAWL
# ==================================================

def build_redirect_chain_from_response(response):
    chain = []

    for history_response in response.history:
        chain.append({
            "url": history_response.url,
            "status": history_response.status_code,
            "location": history_response.headers.get("Location", "")
        })

    chain.append({
        "url": response.url,
        "status": response.status_code,
        "location": ""
    })

    return chain


def page_record_from_response(page_url, response, html):
    meta = parse_page_meta(page_url, html)
    first_h1 = meta["h1_list"][0] if meta["h1_list"] else ""
    internal_links = []

    return {
        "url": page_url,
        "final_url": response.url,
        "status_code": response.status_code,
        "title": meta["title"],
        "description": meta["description"],
        "h1": first_h1,
        "h1_list": meta["h1_list"],
        "h1_count": meta["h1_count"],
        "canonical": meta["canonical"],
        "meta_robots": meta["meta_robots"],
        "images_total": meta["images_total"],
        "images_without_alt": len(meta["images_without_alt_list"]),
        "image_alt_coverage": meta["image_alt_coverage"],
        "internal_links": internal_links,
        "internal_links_count": 0,
        "redirect_chain": build_redirect_chain_from_response(response),
        "content_type": response.headers.get("Content-Type", "")
    }, meta


def collect_page_issues(page, results):
    url = page["url"]

    if page["status_code"] >= 400:
        results["broken_links"].append({
            "url": url,
            "status_code": page["status_code"],
            "found_on": "crawler"
        })

    if 300 <= page["status_code"] < 400:
        return

    if not page["title"]:
        results["errors"].append(f"Missing Title: {url}")

    if not page["description"]:
        results["errors"].append(f"Missing Description: {url}")

    if not page["h1"]:
        results["errors"].append(f"Missing H1: {url}")

    if not page["canonical"]:
        results["errors"].append(f"Missing canonical: {url}")

    if page["images_total"] and page["image_alt_coverage"] < 100:
        results["errors"].append(f"Images without alt on {url}: {page['images_without_alt']}")


def update_full_crawl_reports(results, crawled_pages, redirect_chains):
    title_map = {}
    description_map = {}
    h1_map = {}
    canonical_report = []
    pages_meta = []

    for page in crawled_pages:
        pages_meta.append({
            "url": page["url"],
            "status_code": page["status_code"],
            "title": page["title"],
            "description": page["description"],
            "h1": page["h1"],
            "h1_list": page.get("h1_list", []),
            "h1_count": page["h1_count"],
            "canonical": page["canonical"],
            "meta_robots": page["meta_robots"],
            "image_alt_coverage": page["image_alt_coverage"],
            "internal_links_count": page["internal_links_count"]
        })

        canonical_report.append({
            "url": page["url"],
            "canonical": page["canonical"],
            "status": "present" if page["canonical"] else "missing",
            "canonical_normalized": normalize_url(page["canonical"], page["url"]) if page["canonical"] else "",
            "is_self_canonical": (
                normalize_url(page["canonical"], page["url"]) == normalize_url(page["url"])
                if page["canonical"] else False
            )
        })

        normalized_title = normalize_meta_text(page["title"])
        normalized_description = normalize_meta_text(page["description"])
        normalized_h1 = normalize_meta_text(page["h1"])

        if normalized_title:
            title_map.setdefault(normalized_title, {
                "text": page["title"],
                "urls": []
            })
            title_map[normalized_title]["urls"].append(page["url"])

        if normalized_description:
            description_map.setdefault(normalized_description, {
                "text": page["description"],
                "urls": []
            })
            description_map[normalized_description]["urls"].append(page["url"])

        if normalized_h1:
            h1_map.setdefault(normalized_h1, {
                "text": page["h1"],
                "urls": []
            })
            h1_map[normalized_h1]["urls"].append(page["url"])

    results["crawled_pages"] = crawled_pages
    results["crawled_pages_count"] = len(crawled_pages)
    results["pages_meta"] = pages_meta
    results["canonical_report"] = canonical_report
    results["redirect_chains"] = redirect_chains
    results["broken_links_total"] = len(results["broken_links"])
    results["internal_links_total"] = sum(page["internal_links_count"] for page in crawled_pages)

    results["duplicate_titles"] = {
        item["text"]: item["urls"]
        for item in title_map.values()
        if len(item["urls"]) > 1
    }
    results["duplicate_descriptions"] = {
        item["text"]: item["urls"]
        for item in description_map.values()
        if len(item["urls"]) > 1
    }
    results["duplicate_h1"] = {
        item["text"]: item["urls"]
        for item in h1_map.values()
        if len(item["urls"]) > 1
    }

    results["meta_audit"] = build_meta_audit(
        pages_meta=pages_meta,
        duplicate_titles=results["duplicate_titles"],
        duplicate_descriptions=results["duplicate_descriptions"],
        duplicate_h1=results["duplicate_h1"]
    )

    if results["duplicate_titles"]:
        results["errors"].append(f"Duplicate titles found: {len(results['duplicate_titles'])}")

    if results["duplicate_descriptions"]:
        results["errors"].append(f"Duplicate descriptions found: {len(results['duplicate_descriptions'])}")

    if results["duplicate_h1"]:
        results["errors"].append(f"Duplicate H1 found: {len(results['duplicate_h1'])}")


def severity_class(severity):
    return {
        "critical": "ts-severity-critical",
        "warning": "ts-severity-important",
        "important": "ts-severity-important",
        "recommendation": "ts-severity-recommendation",
    }.get(severity, "ts-severity-recommendation")


def meta_issue(issue_type, field, title, severity, explanation):
    return {
        "type": issue_type,
        "field": field,
        "title": title,
        "severity": severity,
        "severity_label": {
            "critical": "Критично",
            "warning": "Предупреждение",
            "recommendation": "Рекомендация",
        }.get(severity, "Рекомендация"),
        "severity_class": severity_class(severity),
        "explanation": explanation,
    }


def build_meta_audit(pages_meta, duplicate_titles=None, duplicate_descriptions=None, duplicate_h1=None):
    duplicate_titles = duplicate_titles or {}
    duplicate_descriptions = duplicate_descriptions or {}
    duplicate_h1 = duplicate_h1 or {}
    duplicate_title_urls = {url for urls in duplicate_titles.values() for url in urls}
    duplicate_description_urls = {url for urls in duplicate_descriptions.values() for url in urls}
    duplicate_h1_urls = {url for urls in duplicate_h1.values() for url in urls}

    rows = []
    summary = {
        "pages_total": len(pages_meta),
        "pages_with_issues": 0,
        "critical": 0,
        "warning": 0,
        "recommendation": 0,
        "title_issues": 0,
        "description_issues": 0,
        "h1_issues": 0,
    }

    for page in pages_meta:
        url = page.get("url", "")
        title = page.get("title", "") or ""
        description = page.get("description", "") or ""
        h1 = page.get("h1", "") or ""
        h1_count = int(page.get("h1_count") or 0)
        issues = []

        if not title:
            issues.append(meta_issue(
                "missing_title",
                "Title",
                "Title отсутствует",
                "critical",
                "Страница без title хуже объясняет поиску и клиенту, о чем она."
            ))
        elif len(title) < 30:
            issues.append(meta_issue(
                "short_title",
                "Title",
                "Title слишком короткий",
                "recommendation",
                "Короткий title часто не успевает показать услугу, категорию или пользу страницы."
            ))
        elif len(title) > 80:
            issues.append(meta_issue(
                "long_title",
                "Title",
                "Title слишком длинный",
                "warning",
                "Длинный title может обрезаться в поиске и выглядеть менее аккуратно."
            ))

        if url in duplicate_title_urls:
            issues.append(meta_issue(
                "duplicate_title",
                "Title",
                "Title повторяется на нескольких страницах",
                "warning",
                "Одинаковые title мешают страницам отличаться друг от друга в поиске."
            ))

        if not description:
            issues.append(meta_issue(
                "missing_description",
                "Description",
                "Description пустой",
                "warning",
                "Description помогает сделать сниппет понятнее и повысить шанс перехода из поиска."
            ))
        elif len(description) < 70:
            issues.append(meta_issue(
                "short_description",
                "Description",
                "Description слишком короткий",
                "recommendation",
                "Короткое описание обычно не раскрывает пользу страницы для клиента."
            ))
        elif len(description) > 200:
            issues.append(meta_issue(
                "long_description",
                "Description",
                "Description слишком длинный",
                "recommendation",
                "Длинное описание может обрезаться и терять главный смысл."
            ))

        if url in duplicate_description_urls:
            issues.append(meta_issue(
                "duplicate_description",
                "Description",
                "Description повторяется",
                "recommendation",
                "Повторяющиеся описания делают страницы менее различимыми в поиске."
            ))

        if not h1 or h1_count == 0:
            issues.append(meta_issue(
                "missing_h1",
                "H1",
                "H1 отсутствует",
                "warning",
                "H1 помогает посетителю быстро понять главный смысл страницы."
            ))
        elif h1_count > 1:
            issues.append(meta_issue(
                "multiple_h1",
                "H1",
                "На странице несколько H1",
                "recommendation",
                "Несколько H1 могут размывать главный акцент страницы."
            ))

        if url in duplicate_h1_urls:
            issues.append(meta_issue(
                "duplicate_h1",
                "H1",
                "H1 повторяется на разных страницах",
                "recommendation",
                "Одинаковые H1 могут мешать страницам выглядеть уникальными."
            ))

        if issues:
            summary["pages_with_issues"] += 1

        for issue in issues:
            summary[issue["severity"]] += 1
            if issue["field"] == "Title":
                summary["title_issues"] += 1
            elif issue["field"] == "Description":
                summary["description_issues"] += 1
            elif issue["field"] == "H1":
                summary["h1_issues"] += 1

        rows.append({
            "url": url,
            "title": title,
            "title_length": len(title),
            "description": description,
            "description_length": len(description),
            "h1": h1,
            "h1_count": h1_count,
            "issues": issues,
            "issues_count": len(issues),
            "max_severity": issues[0]["severity"] if issues else "ok",
        })

    return {
        "summary": summary,
        "rows": rows,
        "duplicate_titles": duplicate_titles,
        "duplicate_descriptions": duplicate_descriptions,
        "duplicate_h1": duplicate_h1,
    }


def add_seo_assistant_issue(
    results,
    issue_id,
    category,
    title,
    severity,
    why,
    fix,
    affected_urls=None,
    details=None
):
    affected_urls = list(dict.fromkeys([url for url in (affected_urls or []) if url]))
    details = details or {}

    results.setdefault("seo_assistant_issues", []).append({
        "id": issue_id,
        "category": category,
        "title": title,
        "severity": severity,
        "severity_label": {
            "critical": "Критично",
            "important": "Важно",
            "recommendation": "Рекомендация",
        }.get(severity, "Рекомендация"),
        "severity_class": severity_class(severity),
        "why": why,
        "fix": fix,
        "affected_urls": affected_urls,
        "details": details,
    })


def build_seo_assistant_issues(results, base_url, headers):
    results["seo_assistant_issues"] = []
    crawled_pages = results.get("crawled_pages") or []
    pages_meta = results.get("pages_meta") or []
    pages = crawled_pages or pages_meta
    home_url = results.get("url") or base_url

    robots_status = results.get("robots_status_code")
    robots_content = results.get("robots_content", "")
    robots_lower = robots_content.lower()

    if robots_status in [None, "request_error"] or robots_status == 404 or "не найден" in str(results.get("robots_txt", "")).lower():
        add_seo_assistant_issue(
            results,
            "robots_missing",
            "Robots.txt",
            "robots.txt не найден или недоступен",
            "important",
            "robots.txt помогает поисковикам понять, какие разделы сайта можно обходить и где находится sitemap.xml.",
            "Добавьте файл robots.txt в корень сайта и проверьте, что он открывается по адресу /robots.txt.",
            [results.get("robots_url") or urljoin(base_url, "/robots.txt")],
            {"status": robots_status or results.get("robots_txt")}
        )
    elif robots_status != 200:
        add_seo_assistant_issue(
            results,
            "robots_status",
            "Robots.txt",
            f"robots.txt отвечает статусом {robots_status}",
            "important",
            "Если robots.txt отдает ошибку, поисковики могут некорректно понять правила обхода сайта.",
            "Проверьте ответ сервера для /robots.txt и настройте отдачу HTTP 200.",
            [results.get("robots_url")],
            {"status": robots_status}
        )

    if robots_content and "sitemap:" not in robots_lower:
        add_seo_assistant_issue(
            results,
            "robots_without_sitemap",
            "Robots.txt",
            "В robots.txt не указан sitemap.xml",
            "recommendation",
            "Ссылка на sitemap.xml помогает поисковикам быстрее найти важные страницы сайта.",
            "Добавьте строку Sitemap: https://ваш-сайт.ru/sitemap.xml в robots.txt.",
            [results.get("robots_url")],
        )

    if "disallow: /" in robots_lower:
        add_seo_assistant_issue(
            results,
            "robots_full_block",
            "Robots.txt",
            "В robots.txt есть полная блокировка сайта",
            "critical",
            "Правило Disallow: / может закрыть весь сайт от обхода поисковыми роботами.",
            "Проверьте, действительно ли сайт нужно закрывать. Для открытого сайта уберите полную блокировку или ограничьте ее только служебными разделами.",
            [results.get("robots_url")],
        )

    sitemap_status = results.get("sitemap_status_code")
    sitemap_text = str(results.get("sitemap", "")).lower()
    sitemap_valid_text = str(results.get("sitemap_valid", "")).lower()
    sitemap_found = sitemap_status == 200 or ("найден" in sitemap_text and "не найден" not in sitemap_text)
    sitemap_valid = "некоррект" not in sitemap_valid_text and "invalid" not in sitemap_valid_text

    if sitemap_status in [None, "request_error"] or sitemap_status == 404 or not sitemap_found:
        add_seo_assistant_issue(
            results,
            "sitemap_missing",
            "Sitemap.xml",
            "sitemap.xml не найден или недоступен",
            "important",
            "Sitemap помогает поисковикам быстрее находить важные страницы и понимать структуру сайта.",
            "Создайте sitemap.xml, откройте его по адресу /sitemap.xml и добавьте ссылку на него в robots.txt.",
            [results.get("sitemap_url") or urljoin(base_url, "/sitemap.xml")],
            {"status": sitemap_status or results.get("sitemap")}
        )
    elif sitemap_status != 200:
        add_seo_assistant_issue(
            results,
            "sitemap_status",
            "Sitemap.xml",
            f"sitemap.xml отвечает статусом {sitemap_status}",
            "important",
            "Если sitemap недоступен, поисковикам сложнее быстро обнаруживать новые и обновленные страницы.",
            "Проверьте серверный ответ sitemap.xml и настройте отдачу HTTP 200.",
            [results.get("sitemap_url")],
            {"status": sitemap_status}
        )
    elif not sitemap_valid:
        add_seo_assistant_issue(
            results,
            "sitemap_invalid_xml",
            "Sitemap.xml",
            "sitemap.xml содержит некорректный XML",
            "critical",
            "Ошибки XML могут помешать поисковикам прочитать карту сайта.",
            "Проверьте sitemap.xml валидатором, исправьте структуру XML и повторите аудит.",
            [results.get("sitemap_url")],
            {"urls_count": results.get("sitemap_urls_count", 0)}
        )
    elif int(results.get("sitemap_urls_count") or 0) == 0:
        add_seo_assistant_issue(
            results,
            "sitemap_empty",
            "Sitemap.xml",
            "sitemap.xml найден, но в нем нет URL",
            "important",
            "Пустая карта сайта не помогает поисковикам находить страницы.",
            "Добавьте в sitemap.xml важные страницы сайта и обновляйте файл при изменениях.",
            [results.get("sitemap_url")],
        )

    missing_title = []
    short_title = []
    long_title = []
    missing_description = []
    short_description = []
    long_description = []
    missing_h1 = []

    for page in pages:
        page_url = page.get("url") or home_url
        title = page.get("title") or ""
        description = page.get("description") or ""
        h1 = page.get("h1") or ""
        h1_count = int(page.get("h1_count") or (1 if h1 else 0))

        if not title:
            missing_title.append(page_url)
        elif len(title) < 30:
            short_title.append(page_url)
        elif len(title) > 80:
            long_title.append(page_url)

        if not description:
            missing_description.append(page_url)
        elif len(description) < 70:
            short_description.append(page_url)
        elif len(description) > 200:
            long_description.append(page_url)

        if not h1 and h1_count == 0:
            missing_h1.append(page_url)

    if missing_title:
        add_seo_assistant_issue(results, "missing_title", "Мета-теги", "На страницах нет title", "critical", "Title часто виден в поиске и помогает клиенту понять, куда он попадет.", "Добавьте уникальный title для каждой важной страницы: кратко, понятно, с основным запросом.", missing_title[:20])
    if short_title:
        add_seo_assistant_issue(results, "short_title", "Мета-теги", "Title слишком короткий", "recommendation", "Слишком короткий title обычно хуже объясняет ценность страницы.", "Расширьте title до 50-70 символов: добавьте услугу, город, категорию или выгоду.", short_title[:20])
    if long_title:
        add_seo_assistant_issue(results, "long_title", "Мета-теги", "Title слишком длинный", "recommendation", "Длинный title может обрезаться в поиске и выглядеть неаккуратно.", "Сократите title до 50-70 символов и оставьте самое важное в начале.", long_title[:20])
    if missing_description:
        add_seo_assistant_issue(results, "missing_description", "Мета-теги", "На страницах пустой description", "important", "Description помогает сделать сниппет в поиске понятнее и привлекательнее.", "Добавьте описание на 120-160 символов: что на странице, для кого и почему стоит перейти.", missing_description[:20])
    if short_description:
        add_seo_assistant_issue(results, "short_description", "Мета-теги", "Description слишком короткий", "recommendation", "Короткое описание часто не раскрывает пользу страницы для клиента.", "Дополните description преимуществом, ассортиментом, услугой или призывом к действию.", short_description[:20])
    if long_description:
        add_seo_assistant_issue(results, "long_description", "Мета-теги", "Description слишком длинный", "recommendation", "Слишком длинное описание может обрезаться и терять смысл.", "Сократите description до 120-160 символов и оставьте основную пользу.", long_description[:20])
    if missing_h1:
        add_seo_assistant_issue(results, "missing_h1", "Мета-теги", "На страницах отсутствует H1", "important", "H1 помогает посетителю и поисковику быстро понять главную тему страницы.", "Добавьте один понятный H1, совпадающий с содержанием страницы.", missing_h1[:20])

    canonical_report = results.get("canonical_report") or []
    canonical_map = {
        normalize_url(item.get("url", "")): normalize_url(item.get("canonical", ""), item.get("url", ""))
        for item in canonical_report
        if item.get("url")
    }
    missing_canonical = []
    non_self_canonical = []
    external_canonical = []
    loop_canonical = []
    broken_canonical = []

    for item in canonical_report:
        page_url = normalize_url(item.get("url", ""))
        canonical_url = normalize_url(item.get("canonical", ""), item.get("url", ""))

        if not canonical_url:
            missing_canonical.append(item.get("url", ""))
            continue

        if canonical_url != page_url:
            non_self_canonical.append(item.get("url", ""))

        if canonical_url and not is_internal_link(base_url, canonical_url):
            external_canonical.append(item.get("url", ""))

        if canonical_map.get(canonical_url) == page_url and canonical_url != page_url:
            loop_canonical.append(item.get("url", ""))

    checked_canonicals = set()
    for canonical_url in list(canonical_map.values())[:30]:
        if not canonical_url or canonical_url in checked_canonicals or not is_internal_link(base_url, canonical_url):
            continue
        checked_canonicals.add(canonical_url)
        response, error = safe_get(canonical_url, headers=headers, timeout=8, allow_redirects=True)
        if error or (response and response.status_code >= 400):
            broken_canonical.append(canonical_url)

    if missing_canonical:
        add_seo_assistant_issue(results, "missing_canonical", "Canonical", "На страницах нет canonical", "important", "Canonical помогает не распылять SEO-вес между дублями одной страницы.", "Добавьте self canonical на основную версию каждой важной страницы.", missing_canonical[:20])
    if non_self_canonical:
        add_seo_assistant_issue(results, "non_self_canonical", "Canonical", "Canonical ведет на другой URL", "recommendation", "Иногда это правильно, но важно убедиться, что страница действительно является дублем.", "Проверьте, должен ли canonical вести на другую страницу. Если нет, поставьте self canonical.", non_self_canonical[:20])
    if external_canonical:
        add_seo_assistant_issue(results, "external_canonical", "Canonical", "Canonical ведет на внешний домен", "critical", "Такой canonical может передавать сигнал основной версии другой площадке.", "Проверьте canonical и оставьте внешний URL только если это осознанное решение.", external_canonical[:20])
    if loop_canonical:
        add_seo_assistant_issue(results, "canonical_loop", "Canonical", "Обнаружена canonical-петля", "critical", "Петли мешают поисковикам понять основную версию страницы.", "Настройте canonical так, чтобы все дубли указывали на одну конечную основную страницу.", loop_canonical[:20])
    if broken_canonical:
        add_seo_assistant_issue(results, "broken_canonical", "Canonical", "Canonical ведет на недоступную страницу", "critical", "Если canonical указывает на ошибку, поисковик может хуже понимать основную страницу.", "Исправьте canonical на доступный URL с HTTP 200.", broken_canonical[:20])

    broken_links = results.get("broken_links") or []
    broken_internal = [
        link
        for link in broken_links
        if is_internal_link(base_url, link.get("url", ""))
    ]

    if broken_internal:
        add_seo_assistant_issue(
            results,
            "broken_internal_links",
            "Битые ссылки",
            f"Найдены битые внутренние ссылки: {len(broken_internal)}",
            "critical",
            "Битые ссылки ведут клиентов на ошибки и мешают поисковикам нормально обходить сайт.",
            "Исправьте адрес ссылки, восстановите страницу или настройте 301-редирект на актуальную страницу.",
            [item.get("url") for item in broken_internal[:20]],
            {
                "found_on": [item.get("found_on") for item in broken_internal[:20]],
                "statuses": [item.get("status_code") for item in broken_internal[:20]],
            }
        )


def technical_status_label(ok, warning=False):
    if ok:
        return "Все хорошо"
    if warning:
        return "Нужно проверить"
    return "Есть проблема"


def technical_severity(ok, warning=False):
    if ok:
        return "recommendation"
    if warning:
        return "warning"
    return "critical"


def build_sitemap_analysis(results):
    status_code = results.get("sitemap_status_code")
    sitemap_url = results.get("sitemap_url", "")
    found = status_code == 200
    valid_xml = "некоррект" not in str(results.get("sitemap_valid", "")).lower() and found
    urls_count = int(results.get("sitemap_urls_count") or 0)
    broken_urls = []
    sitemap_urls = set(results.get("sitemap_urls") or [])

    for item in results.get("broken_links", []):
        if item.get("url") in sitemap_urls:
            broken_urls.append(item)

    checks = [
        {
            "title": "Sitemap найден",
            "status": technical_status_label(found),
            "severity": technical_severity(found, warning=True),
            "severity_label": "Рекомендация" if found else "Важно",
            "severity_class": severity_class("recommendation" if found else "warning"),
            "explanation": "Sitemap помогает поисковикам быстрее находить важные страницы сайта.",
            "helper": "Если sitemap нет, создайте его и укажите ссылку в robots.txt.",
        },
        {
            "title": "XML корректный",
            "status": technical_status_label(valid_xml),
            "severity": technical_severity(valid_xml),
            "severity_label": "Рекомендация" if valid_xml else "Критично",
            "severity_class": severity_class("recommendation" if valid_xml else "critical"),
            "explanation": "Если XML сломан, поисковик может не прочитать карту сайта.",
            "helper": "Проверьте sitemap.xml валидатором XML и исправьте структуру тегов.",
        },
        {
            "title": "В sitemap есть URL",
            "status": technical_status_label(urls_count > 0, warning=True),
            "severity": technical_severity(urls_count > 0, warning=True),
            "severity_label": "Рекомендация" if urls_count > 0 else "Важно",
            "severity_class": severity_class("recommendation" if urls_count > 0 else "warning"),
            "explanation": "Пустой sitemap не помогает поисковикам находить страницы.",
            "helper": "Добавьте в sitemap основные разделы, категории, услуги и важные посадочные страницы.",
        },
        {
            "title": "Нет битых URL в sitemap",
            "status": technical_status_label(not broken_urls, warning=True),
            "severity": technical_severity(not broken_urls, warning=True),
            "severity_label": "Рекомендация" if not broken_urls else "Важно",
            "severity_class": severity_class("recommendation" if not broken_urls else "warning"),
            "explanation": "Если sitemap содержит недоступные страницы, поисковики тратят время на ошибки.",
            "helper": "Удалите из sitemap URL с ошибками или восстановите эти страницы.",
        },
    ]

    return {
        "url": sitemap_url,
        "found": found,
        "status_code": status_code,
        "xml_valid": valid_xml,
        "urls_count": urls_count,
        "type": results.get("sitemap_type", "—"),
        "lastmod": results.get("sitemap_lastmod", "—"),
        "lastmod_values": results.get("sitemap_lastmod_values", []),
        "sample_urls": results.get("sitemap_sample_urls", []),
        "broken_urls": broken_urls,
        "checks": checks,
    }


def build_robots_analysis(results):
    status_code = results.get("robots_status_code")
    robots_url = results.get("robots_url", "")
    content = results.get("robots_content", "")
    found = status_code == 200
    has_user_agent = bool(results.get("robots_has_user_agent")) or "user-agent" in content.lower()
    has_sitemap = bool(results.get("robots_has_sitemap")) or "sitemap:" in content.lower()
    full_block = bool(results.get("robots_full_block")) or "disallow: /" in content.lower()
    blocked_sections = results.get("robots_blocked_important_sections") or []

    checks = [
        {
            "title": "robots.txt найден",
            "status": technical_status_label(found, warning=True),
            "severity_label": "Рекомендация" if found else "Важно",
            "severity_class": severity_class("recommendation" if found else "warning"),
            "explanation": "robots.txt задает правила обхода сайта для поисковых роботов.",
            "helper": "Файл должен открываться по адресу /robots.txt и отдавать HTTP 200.",
        },
        {
            "title": "Есть User-agent",
            "status": technical_status_label(has_user_agent, warning=True),
            "severity_label": "Рекомендация" if has_user_agent else "Важно",
            "severity_class": severity_class("recommendation" if has_user_agent else "warning"),
            "explanation": "User-agent показывает, к каким роботам относятся правила.",
            "helper": "Добавьте User-agent: * или отдельные правила для нужных поисковых систем.",
        },
        {
            "title": "Есть ссылка на sitemap",
            "status": technical_status_label(has_sitemap, warning=True),
            "severity_label": "Рекомендация" if has_sitemap else "Важно",
            "severity_class": severity_class("recommendation" if has_sitemap else "warning"),
            "explanation": "Sitemap directive помогает поисковикам быстрее найти карту сайта.",
            "helper": "Добавьте строку Sitemap: https://ваш-сайт.ru/sitemap.xml.",
        },
        {
            "title": "Нет полной блокировки сайта",
            "status": technical_status_label(not full_block),
            "severity_label": "Рекомендация" if not full_block else "Критично",
            "severity_class": severity_class("recommendation" if not full_block else "critical"),
            "explanation": "Disallow: / может закрыть весь сайт от обхода поисковыми роботами.",
            "helper": "Оставьте полную блокировку только для тестовых или закрытых сайтов.",
        },
        {
            "title": "Важные разделы не закрыты",
            "status": technical_status_label(not blocked_sections, warning=True),
            "severity_label": "Рекомендация" if not blocked_sections else "Важно",
            "severity_class": severity_class("recommendation" if not blocked_sections else "warning"),
            "explanation": "Если закрыть каталог, услуги или статьи, важные страницы могут не попасть в поиск.",
            "helper": "Проверьте Disallow-правила для коммерческих и контентных разделов.",
        },
    ]

    return {
        "url": robots_url,
        "found": found,
        "status_code": status_code,
        "has_user_agent": has_user_agent,
        "has_sitemap": has_sitemap,
        "full_block": full_block,
        "blocked_important_sections": blocked_sections,
        "content": content,
        "content_length": len(content),
        "checks": checks,
    }


def redirect_issue(title, severity, why, helper):
    return {
        "title": title,
        "severity": severity,
        "severity_label": {
            "critical": "Критично",
            "warning": "Предупреждение",
            "recommendation": "Рекомендация",
        }.get(severity, "Рекомендация"),
        "severity_class": severity_class(severity),
        "why": why,
        "helper": helper,
    }


def build_redirect_analysis(results):
    raw_redirects = (results.get("redirect_chains") or []) + (results.get("homepage_redirects") or [])
    rows = []
    summary = {
        "total": 0,
        "loops": 0,
        "temporary": 0,
        "mixed": 0,
        "long_chains": 0,
    }

    for item in raw_redirects:
        chain = item.get("chain") or []
        if not chain:
            continue

        source_url = item.get("url") or chain[0].get("url", "")
        destination_url = chain[-1].get("url", "") if chain else ""
        statuses = [hop.get("status") for hop in chain]
        redirect_statuses = [status for status in statuses if status in [301, 302, 303, 307, 308]]
        chain_length = max(0, len(chain) - 1)
        has_loop = any(str(status) == "redirect_loop" for status in statuses)
        has_temporary = any(status in [302, 303, 307] for status in redirect_statuses)
        permanent_count = len([status for status in redirect_statuses if status in [301, 308]])
        temporary_count = len([status for status in redirect_statuses if status in [302, 303, 307]])
        has_mixed = permanent_count > 0 and temporary_count > 0
        issues = []

        if has_loop:
            issues.append(redirect_issue(
                "Обнаружена петля редиректа",
                "critical",
                "Петля не дает пользователю и поисковику попасть на конечную страницу.",
                "Разорвите цикл и оставьте один понятный переход на финальный URL."
            ))
            summary["loops"] += 1

        if has_temporary:
            issues.append(redirect_issue(
                "Есть временный редирект",
                "warning",
                "302/307 обычно сообщает, что переезд временный, и поисковик может осторожнее передавать сигналы.",
                "Если переезд постоянный, замените временный редирект на 301 или 308."
            ))
            summary["temporary"] += 1

        if has_mixed:
            issues.append(redirect_issue(
                "Смешанная цепочка редиректов",
                "warning",
                "Смешение 301 и 302 делает намерение переезда менее понятным.",
                "Сделайте цепочку единообразной: для постоянных переездов используйте 301/308."
            ))
            summary["mixed"] += 1

        if chain_length > 1:
            issues.append(redirect_issue(
                "Длинная цепочка редиректов",
                "recommendation",
                "Чем длиннее цепочка, тем медленнее открывается страница и сложнее обход.",
                "Настройте переход сразу с исходного URL на конечный."
            ))
            summary["long_chains"] += 1

        rows.append({
            "source_url": source_url,
            "destination_url": destination_url,
            "redirect_type": " / ".join(str(status) for status in redirect_statuses) or "нет редиректа",
            "chain_length": chain_length,
            "has_loop": has_loop,
            "has_temporary": has_temporary,
            "has_mixed": has_mixed,
            "chain": chain,
            "issues": issues,
            "max_severity": issues[0]["severity"] if issues else "recommendation",
        })

    summary["total"] = len(rows)
    return {
        "summary": summary,
        "rows": rows,
    }


def canonical_issue(title, severity, why, fix):
    return {
        "title": title,
        "severity": severity,
        "severity_label": {
            "critical": "Критично",
            "warning": "Предупреждение",
            "recommendation": "Рекомендация",
        }.get(severity, "Рекомендация"),
        "severity_class": severity_class(severity),
        "why": why,
        "fix": fix,
    }


def build_canonical_analysis(results, base_url, headers):
    canonical_report = results.get("canonical_report") or []
    base_home = normalize_url(base_url)
    canonical_map = {
        normalize_url(item.get("url", "")): normalize_url(item.get("canonical", ""), item.get("url", ""))
        for item in canonical_report
        if item.get("url")
    }
    checked_targets = {}
    rows = []
    summary = {
        "total": len(canonical_report),
        "missing": 0,
        "self": 0,
        "other_url": 0,
        "loops": 0,
        "broken": 0,
        "home": 0,
        "external": 0,
    }

    for item in canonical_report:
        source_url = normalize_url(item.get("url", ""))
        canonical_target = normalize_url(item.get("canonical", ""), item.get("url", ""))
        issues = []
        is_self = bool(canonical_target and canonical_target == source_url)

        if not canonical_target:
            summary["missing"] += 1
            issues.append(canonical_issue(
                "Canonical не найден",
                "warning",
                "Без canonical поисковику сложнее понять основную версию страницы.",
                "Добавьте self canonical на основную версию страницы."
            ))
        elif is_self:
            summary["self"] += 1
        else:
            summary["other_url"] += 1
            issues.append(canonical_issue(
                "Canonical ведет на другой URL",
                "recommendation",
                "Это нормально для дублей, но опасно для самостоятельных страниц.",
                "Проверьте, действительно ли страница должна указывать на другой основной URL."
            ))

        if canonical_target and not is_internal_link(base_url, canonical_target):
            summary["external"] += 1
            issues.append(canonical_issue(
                "Canonical ведет на внешний домен",
                "critical",
                "Так страница может передавать сигнал основной версии другой площадке.",
                "Оставьте внешний canonical только если это осознанная бизнес-логика."
            ))

        if canonical_target and canonical_target == base_home and source_url != base_home:
            summary["home"] += 1
            issues.append(canonical_issue(
                "Canonical ведет на главную",
                "warning",
                "Если много внутренних страниц указывают canonical на главную, они могут хуже ранжироваться как отдельные страницы.",
                "Для важных страниц используйте self canonical или указывайте на точную основную версию."
            ))

        if canonical_target and canonical_map.get(canonical_target) == source_url and canonical_target != source_url:
            summary["loops"] += 1
            issues.append(canonical_issue(
                "Canonical-петля",
                "critical",
                "Петля мешает понять, какая страница основная.",
                "Выберите один финальный canonical и направьте все дубли на него."
            ))

        broken_status = None
        if canonical_target and is_internal_link(base_url, canonical_target):
            if canonical_target not in checked_targets:
                response, error = safe_get(canonical_target, headers=headers, timeout=8, allow_redirects=True)
                checked_targets[canonical_target] = error or (response.status_code if response else "request_error")

            broken_status = checked_targets[canonical_target]

            if isinstance(broken_status, int) and broken_status >= 400 or isinstance(broken_status, str):
                summary["broken"] += 1
                issues.append(canonical_issue(
                    "Canonical ведет на недоступный URL",
                    "critical",
                    "Если canonical указывает на ошибку, поисковик может потерять понятный основной адрес.",
                    "Исправьте canonical на доступный URL с HTTP 200."
                ))

        rows.append({
            "source_page": source_url,
            "canonical_target": canonical_target,
            "status": "self" if is_self else ("missing" if not canonical_target else "other"),
            "is_self": is_self,
            "is_external": bool(canonical_target and not is_internal_link(base_url, canonical_target)),
            "is_home": bool(canonical_target and canonical_target == base_home and source_url != base_home),
            "broken_status": broken_status,
            "issues": issues,
            "max_severity": issues[0]["severity"] if issues else "recommendation",
        })

    return {
        "summary": summary,
        "rows": rows,
    }


def crawl_website(start_url, headers, results, max_pages=FULL_CRAWL_MAX_PAGES):
    normalized_start_url = normalize_url(start_url)
    base_url = get_base_url(normalized_start_url)

    if not normalized_start_url or not base_url:
        results["errors"].append("Invalid start URL for full crawl")
        return []

    queue = deque([normalized_start_url])
    queued = {normalized_start_url}
    source_by_url = {normalized_start_url: normalized_start_url}
    visited = set()
    crawled_pages = []
    redirect_chains = []

    while queue and len(visited) < max_pages:
        current_url = queue.popleft()
        queued.discard(current_url)

        if current_url in visited:
            continue

        visited.add(current_url)
        response, error = safe_get(
            current_url,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True
        )

        if error:
            results["broken_links"].append({
                "url": current_url,
                "status_code": error,
                "found_on": source_by_url.get(current_url, "crawler")
            })
            add_warning(results, f"Full crawl skipped {current_url}: {error}")
            continue

        redirect_chain = build_redirect_chain_from_response(response)

        if len(redirect_chain) > 1:
            redirect_chains.append({
                "url": current_url,
                "chain": redirect_chain,
                "status": redirect_chain[0]["status"],
                "location": redirect_chain[0]["location"]
            })

        if response.status_code >= 400:
            results["broken_links"].append({
                "url": current_url,
                "status_code": response.status_code,
                "found_on": source_by_url.get(current_url, "crawler")
            })
            continue

        content_type = response.headers.get("Content-Type", "").lower()

        if "text/html" not in content_type and content_type:
            continue

        try:
            html = response.text or ""
            page, meta = page_record_from_response(current_url, response, html)
        except Exception as exc:
            add_warning(results, f"Full crawl HTML parse failed for {current_url}: {exc}")
            continue

        page_internal_links = []

        for link_url in meta.get("links", [])[:FULL_CRAWL_MAX_LINKS_PER_PAGE]:
            normalized_link = should_crawl_url(link_url, base_url)

            if not normalized_link:
                continue

            page_internal_links.append(normalized_link)

            if normalized_link not in visited and normalized_link not in queued and len(visited) + len(queue) < max_pages:
                queue.append(normalized_link)
                queued.add(normalized_link)
                source_by_url[normalized_link] = current_url

        page["internal_links"] = sorted(set(page_internal_links))
        page["internal_links_count"] = len(page["internal_links"])
        crawled_pages.append(page)
        collect_page_issues(page, results)

    if queue:
        add_warning(results, f"Full crawl reached max_pages={max_pages}; remaining queue={len(queue)}")

    update_full_crawl_reports(results, crawled_pages, redirect_chains)
    results["full_crawl"] = {
        "enabled": True,
        "start_url": normalized_start_url,
        "base_url": base_url,
        "max_pages": max_pages,
        "visited_urls_count": len(visited),
        "queued_urls_remaining": len(queue)
    }

    return crawled_pages


# ==================================================
# DUPLICATE META
# ==================================================

def normalize_meta_text(text):
    if not text:
        return ""

    return " ".join(
        text.lower()
        .replace("ё", "е")
        .replace("\n", " ")
        .replace("\t", " ")
        .split()
    )


def analyze_duplicate_meta(sitemap_urls, headers, results, max_pages=200):
    title_map = {}
    description_map = {}
    pages_meta = []

    urls = sitemap_urls[:max_pages]

    for page_url in urls:
        response, error = safe_get(page_url, headers=headers, timeout=10)

        if error:
            add_warning(results, f"Duplicate meta check skipped {page_url}: {error}")
            continue

        if response.status_code != 200:
            add_warning(results, f"Duplicate meta check skipped {page_url}: {response_status_label(response)}")
            continue

        meta = parse_page_meta(page_url, response.text)

        page_info = {
            "url": page_url,
            "title": meta["title"],
            "description": meta["description"],
            "canonical": meta["canonical"],
            "h1_count": meta["h1_count"]
        }
        pages_meta.append(page_info)

        normalized_title = normalize_meta_text(meta["title"])
        normalized_description = normalize_meta_text(meta["description"])

        if normalized_title:
            title_map.setdefault(normalized_title, {
                "text": meta["title"],
                "urls": []
            })
            title_map[normalized_title]["urls"].append(page_url)

        if normalized_description:
            description_map.setdefault(normalized_description, {
                "text": meta["description"],
                "urls": []
            })
            description_map[normalized_description]["urls"].append(page_url)

    duplicate_titles = {
        item["text"]: item["urls"]
        for item in title_map.values()
        if len(item["urls"]) > 1
    }

    duplicate_descriptions = {
        item["text"]: item["urls"]
        for item in description_map.values()
        if len(item["urls"]) > 1
    }

    results["pages_meta"] = pages_meta
    results["crawled_pages_count"] = len(pages_meta)
    results["duplicate_titles"] = duplicate_titles
    results["duplicate_descriptions"] = duplicate_descriptions

    if duplicate_titles:
        results["errors"].append(f"Найдены дубли Title: {len(duplicate_titles)}")
        results["recommendations"].append("Сделать уникальные Title для страниц с дублями.")

    if duplicate_descriptions:
        results["errors"].append(f"Найдены дубли Description: {len(duplicate_descriptions)}")
        results["recommendations"].append("Сделать уникальные Description для страниц с дублями.")


# ==================================================
# BROKEN LINKS
# ==================================================

def analyze_broken_links(base_url, page_links, headers, results, max_links=150):
    checked_links = set()

    for link_url in page_links:
        if not is_internal_link(base_url, link_url):
            continue

        if link_url in checked_links:
            continue

        checked_links.add(link_url)

        if len(checked_links) > max_links:
            add_warning(results, f"Broken links check limited to {max_links} internal links")
            break

        response, error = safe_get(link_url, headers=headers, timeout=10, allow_redirects=True)
        results["internal_links_total"] += 1

        if error:
            results["broken_links"].append({
                "url": link_url,
                "status_code": f"Ошибка проверки: {error}",
                "found_on": base_url
            })
            continue

        if response.status_code == 404:
            results["broken_links"].append({
                "url": link_url,
                "status_code": 404,
                "found_on": base_url
            })

    results["broken_links_total"] = len(results["broken_links"])

    if results["broken_links_total"] > 0:
        results["errors"].append(f"Битых ссылок найдено: {results['broken_links_total']}")
        results["recommendations"].append(
            "Исправить или удалить ссылки, которые ведут на 404/недоступные страницы."
        )


# ==================================================
# PAGINATION
# ==================================================

def analyze_pagination(sitemap_urls, base_url, headers, results, max_pages=80):
    pagination_pages = []
    markers = [
        "page=",
        "/page/",
        "pagen_",
        "PAGEN_",
        "nav-",
        "?PAGEN"
    ]

    for page_url in sitemap_urls[:max_pages]:
        if any(marker in page_url for marker in markers):
            response, error = safe_get(page_url, headers=headers, timeout=10)

            if error:
                add_warning(results, f"Pagination check skipped {page_url}: {error}")
                continue

            if response.status_code != 200:
                add_warning(results, f"Pagination check skipped {page_url}: {response_status_label(response)}")
                continue

            meta = parse_page_meta(page_url, response.text)

            pagination_pages.append({
                "url": page_url,
                "title": meta["title"],
                "description": meta["description"],
                "canonical": meta["canonical"],
                "canonical_status": "✅ Есть" if meta["canonical"] else "❌ Нет"
            })

    results["pagination_pages"] = pagination_pages
    results["pagination_pages_count"] = len(pagination_pages)

    missing_canonical = [
        page
        for page in pagination_pages
        if not page.get("canonical")
    ]

    if missing_canonical:
        results["pagination_errors"].append(
            f"На страницах пагинации отсутствует canonical: {len(missing_canonical)}"
        )
        results["errors"].append(
            f"Ошибки canonical на пагинации: {len(missing_canonical)}"
        )
        results["recommendations"].append("Проверить canonical на страницах пагинации.")

    if pagination_pages:
        results["pagination_status"] = "✅ Найдены страницы пагинации"
    else:
        results["pagination_status"] = "Страницы пагинации не найдены"


# ==================================================
# REDIRECTS / MAIN PAGE
# ==================================================

def get_redirect_chain(start_url, headers, max_hops=MAX_REDIRECT_HOPS):
    current_url = start_url
    visited = set()
    chain = []

    for _ in range(max_hops):
        if current_url in visited:
            chain.append({
                "url": current_url,
                "status": "redirect_loop",
                "location": ""
            })
            return chain, "redirect_loop"

        visited.add(current_url)
        response, error = safe_get(
            current_url,
            headers=headers,
            timeout=10,
            allow_redirects=False
        )

        if error:
            chain.append({
                "url": current_url,
                "status": f"Ошибка проверки: {error}",
                "location": ""
            })
            return chain, error

        location = response.headers.get("Location", "")
        chain.append({
            "url": current_url,
            "status": response.status_code,
            "location": location
        })

        if response.status_code not in [301, 302, 303, 307, 308] or not location:
            return chain, None

        current_url = urljoin(current_url, location)

    return chain, "too_many_redirects"


def analyze_homepage_redirects(base_url, headers, results):
    variants = [
        "/index.php",
        "/index.html",
        "///"
    ]

    redirect_results = []

    for variant in variants:
        test_url = urljoin(base_url, variant)
        chain, error = get_redirect_chain(test_url, headers)
        redirect_results.append({
            "url": test_url,
            "chain": chain,
            "status": chain[0]["status"] if chain else "Ошибка проверки",
            "location": chain[0]["location"] if chain else ""
        })

        if error == "redirect_loop":
            results["errors"].append(f"Обнаружен циклический редирект для {variant}")
        elif error == "too_many_redirects":
            results["errors"].append(f"Слишком длинная цепочка редиректов для {variant}")
        elif chain and chain[0]["status"] not in [301, 302, 303, 307, 308]:
            results["errors"].append(f"Нет редиректа для {variant}")

    parsed = urlparse(base_url)
    domain = parsed.netloc

    if domain.startswith("www."):
        alt_domain = domain.replace("www.", "")
    else:
        alt_domain = f"www.{domain}"

    alt_url = f"{parsed.scheme}://{alt_domain}"
    chain, error = get_redirect_chain(alt_url, headers)

    if chain:
        redirect_results.append({
            "url": alt_url,
            "chain": chain,
            "status": chain[0]["status"],
            "location": chain[0]["location"]
        })

    if error in ["redirect_loop", "too_many_redirects"]:
        results["errors"].append(f"Проблема редиректа www/non-www: {error}")

    results["homepage_redirects"] = redirect_results


# ==================================================
# MAIN
# ==================================================

def create_initial_results(url):
    return {
        "url": url,
        "title": "—",
        "description": "—",
        "canonical": "—",
        "h1": "—",
        "robots_txt": "Не проверено",
        "robots_url": "",
        "robots_status_code": "",
        "robots_content": "",
        "robots_errors": [],
        "robots_has_user_agent": False,
        "robots_has_sitemap": False,
        "robots_full_block": False,
        "robots_blocked_important_sections": [],
        "sitemap": "Не проверено",
        "sitemap_url": "",
        "sitemap_status_code": "",
        "sitemap_content": "",
        "sitemap_urls": [],
        "sitemap_sample_urls": [],
        "sitemap_valid": "—",
        "sitemap_type": "—",
        "sitemap_urls_count": 0,
        "sitemap_lastmod": "—",
        "sitemap_lastmod_values": [],
        "sitemap_empty": "—",
        "mobile_friendly": False,
        "title_length": 0,
        "description_length": 0,
        "h1_count": 0,
        "images_total": 0,
        "images_without_alt": 0,
        "images_without_alt_list": [],
        "links_total": 0,
        "internal_links_total": 0,
        "broken_links_total": 0,
        "broken_links": [],
        "pages_meta": [],
        "crawled_pages": [],
        "crawled_pages_count": 0,
        "canonical_report": [],
        "duplicate_titles": {},
        "duplicate_descriptions": {},
        "duplicate_h1": {},
        "meta_audit": {
            "summary": {
                "pages_total": 0,
                "pages_with_issues": 0,
                "critical": 0,
                "warning": 0,
                "recommendation": 0,
                "title_issues": 0,
                "description_issues": 0,
                "h1_issues": 0,
            },
            "rows": [],
            "duplicate_titles": {},
            "duplicate_descriptions": {},
            "duplicate_h1": {},
        },
        "pagination_status": "Не проверено",
        "pagination_pages_count": 0,
        "pagination_pages": [],
        "pagination_errors": [],
        "homepage_redirects": [],
        "redirect_chains": [],
        "redirect_analysis": {
            "summary": {
                "total": 0,
                "loops": 0,
                "temporary": 0,
                "mixed": 0,
                "long_chains": 0,
            },
            "rows": [],
        },
        "canonical_analysis": {
            "summary": {
                "total": 0,
                "missing": 0,
                "self": 0,
                "other_url": 0,
                "loops": 0,
                "broken": 0,
                "home": 0,
                "external": 0,
            },
            "rows": [],
        },
        "full_crawl": {
            "enabled": False,
            "start_url": url,
            "base_url": "",
            "max_pages": FULL_CRAWL_MAX_PAGES,
            "visited_urls_count": 0,
            "queued_urls_remaining": 0
        },
        "main_page_fetch_source": "not_started",
        "crawler_warnings": [],
        "seo_assistant_issues": [],
        "sitemap_analysis": {},
        "robots_analysis": {},
        "errors": [],
        "recommendations": []
    }


def check_technical_seo(url: str):
    url = normalize_url((url or "").strip())
    results = create_initial_results(url)
    base_url = get_base_url(url)

    if not base_url:
        results["errors"].append("Invalid website URL")
        results["recommendations"].append("Use a full URL with http:// or https://.")
        return results

    headers = {
        "User-Agent": "Mozilla/5.0 TechSEO Monitor Bot"
    }

    try:
        main_meta = analyze_main_page(
            url=url,
            headers=headers,
            results=results
        )
    except Exception as exc:
        main_meta = {"links": []}
        results["errors"].append(f"Ошибка анализа главной страницы: {exc}")
        add_warning(results, f"Main page analysis failed for {url}: {exc}")

    try:
        analyze_robots(
            base_url=base_url,
            headers=headers,
            results=results
        )
    except Exception as exc:
        results["errors"].append(f"Ошибка анализа robots.txt: {exc}")
        add_warning(results, f"Robots analysis failed for {base_url}: {exc}")

    sitemap_urls = []

    try:
        sitemap_urls = analyze_sitemap(
            base_url=base_url,
            headers=headers,
            results=results
        )
    except Exception as exc:
        results["errors"].append(f"Ошибка анализа sitemap.xml: {exc}")
        add_warning(results, f"Sitemap analysis failed for {base_url}: {exc}")

    full_crawl_pages = []

    try:
        full_crawl_pages = crawl_website(
            start_url=url,
            headers=headers,
            results=results,
            max_pages=FULL_CRAWL_MAX_PAGES
        )
    except Exception as exc:
        results["errors"].append(f"Full crawl failed: {exc}")
        add_warning(results, f"Full crawl failed for {base_url}: {exc}")

    if sitemap_urls:
        extra_urls = [
            base_url,
            urljoin(base_url, "/"),
            urljoin(base_url, "/index.php"),
            urljoin(base_url, "/index.html")
        ]

        sitemap_urls = list(dict.fromkeys(extra_urls + sitemap_urls))

        if not full_crawl_pages:
            try:
                analyze_duplicate_meta(
                    sitemap_urls,
                    headers,
                    results
                )
            except Exception as exc:
                results["errors"].append(f"Ошибка анализа дублей meta: {exc}")
                add_warning(results, f"Duplicate meta analysis failed for {base_url}: {exc}")

        try:
            analyze_pagination(
                sitemap_urls=sitemap_urls,
                base_url=base_url,
                headers=headers,
                results=results,
                max_pages=120
            )
        except Exception as exc:
            results["errors"].append(f"Ошибка анализа пагинации: {exc}")
            add_warning(results, f"Pagination analysis failed for {base_url}: {exc}")

    if not full_crawl_pages:
        try:
            analyze_broken_links(
                base_url=base_url,
                page_links=main_meta.get("links", []),
                headers=headers,
                results=results,
                max_links=150
            )
        except Exception as exc:
            results["errors"].append(f"Ошибка анализа битых ссылок: {exc}")
            add_warning(results, f"Broken links analysis failed for {base_url}: {exc}")

    try:
        analyze_homepage_redirects(
            base_url=base_url,
            headers=headers,
            results=results
        )
    except Exception as exc:
        results["errors"].append(f"Ошибка анализа редиректов: {exc}")
        add_warning(results, f"Redirect analysis failed for {base_url}: {exc}")

    try:
        build_seo_assistant_issues(results, base_url=base_url, headers=headers)
    except Exception as exc:
        results["errors"].append(f"Ошибка подготовки SEO-помощника: {exc}")
        add_warning(results, f"SEO assistant issue builder failed for {base_url}: {exc}")

    try:
        results["sitemap_analysis"] = build_sitemap_analysis(results)
        results["robots_analysis"] = build_robots_analysis(results)
        results["redirect_analysis"] = build_redirect_analysis(results)
        results["canonical_analysis"] = build_canonical_analysis(results, base_url=base_url, headers=headers)
    except Exception as exc:
        results["errors"].append(f"Ошибка подготовки technical analyzer: {exc}")
        add_warning(results, f"Technical analyzer failed for {base_url}: {exc}")

    if results["crawler_warnings"]:
        results["crawler_warnings"] = list(dict.fromkeys(results["crawler_warnings"]))

    return results
