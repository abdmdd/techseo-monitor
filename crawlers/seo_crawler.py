import logging
import os
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse

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
    response, error = safe_get(sitemap_url, headers=headers, timeout=15)

    if error:
        results["sitemap"] = "❌ Ошибка"
        results["errors"].append(f"Ошибка проверки sitemap.xml: {error}")
        add_warning(results, f"Sitemap request failed for {sitemap_url}: {error}")
        return []

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

    if "<lastmod>" in sitemap_lower:
        results["sitemap_lastmod"] = "✅ Используется"
    else:
        results["sitemap_lastmod"] = "❌ Не используется"

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
    response, error = safe_get(robots_url, headers=headers, timeout=10)

    if error:
        results["robots_txt"] = "Ошибка проверки"
        message = f"Не удалось получить robots.txt: {error}"
        results["robots_errors"].append(message)
        results["errors"].append("Ошибка проверки robots.txt")
        add_warning(results, f"Robots request failed for {robots_url}: {error}")
        return

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
        "h1_list": h1_list,
        "h1_count": len(h1_list),
        "mobile_friendly": viewport is not None,
        "body_empty": body is None or not body.get_text(strip=True),
        "images_total": len(images),
        "images_without_alt_list": images_without_alt_list,
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
        "robots_content": "",
        "robots_errors": [],
        "sitemap": "Не проверено",
        "sitemap_valid": "—",
        "sitemap_type": "—",
        "sitemap_urls_count": 0,
        "sitemap_lastmod": "—",
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
        "crawled_pages_count": 0,
        "duplicate_titles": {},
        "duplicate_descriptions": {},
        "pagination_status": "Не проверено",
        "pagination_pages_count": 0,
        "pagination_pages": [],
        "pagination_errors": [],
        "homepage_redirects": [],
        "main_page_fetch_source": "not_started",
        "crawler_warnings": [],
        "errors": [],
        "recommendations": []
    }


def check_technical_seo(url: str):
    url = (url or "").strip()
    results = create_initial_results(url)
    base_url = get_base_url(url)

    if not base_url:
        results["errors"].append("Некорректный URL сайта")
        results["recommendations"].append("Укажите полный URL с http:// или https://.")
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

    if sitemap_urls:
        extra_urls = [
            base_url,
            urljoin(base_url, "/"),
            urljoin(base_url, "/index.php"),
            urljoin(base_url, "/index.html")
        ]

        sitemap_urls = list(dict.fromkeys(extra_urls + sitemap_urls))

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

    if results["crawler_warnings"]:
        results["crawler_warnings"] = list(dict.fromkeys(results["crawler_warnings"]))

    return results
