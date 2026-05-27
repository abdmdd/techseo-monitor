import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from services.serp_crawler_service import normalize_domain


PAGE_TIMEOUT = 10
COMMERCIAL_WORDS = {
    "цена",
    "стоимость",
    "купить",
    "заказать",
    "услуга",
    "услуги",
    "консультация",
    "доставка",
    "гарантия",
    "акция",
    "скидка",
    "тариф",
    "прайс",
}
CONTACT_WORDS = {"контакты", "адрес", "телефон", "позвонить", "whatsapp", "telegram", "email", "почта", "офис"}
FAQ_WORDS = {"faq", "вопросы", "ответы", "частые вопросы", "как", "почему", "сколько", "когда"}
PRICE_WORDS = {"цена", "стоимость", "прайс", "тариф", "руб", "₽", "оплата"}


def _normalize_url(url):
    value = (url or "").strip()
    if not value:
        return ""
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlparse(value)
    if not parsed.netloc:
        return ""
    return value


def _text_contains(text, words):
    lowered = (text or "").lower()
    return any(word in lowered for word in words)


def _found_words(text, words):
    lowered = (text or "").lower()
    return sorted(word for word in words if word in lowered)


def extract_basic_seo(html, url):
    soup = BeautifulSoup(html or "", "lxml")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    description_tag = soup.select_one('meta[name="description"], meta[property="og:description"]')
    description = description_tag.get("content", "").strip() if description_tag else ""
    h1 = soup.find("h1")
    h2_count = len(soup.find_all("h2"))

    for element in soup(["script", "style", "noscript"]):
        element.decompose()

    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    commercial_words_found = _found_words(text, COMMERCIAL_WORDS)

    return {
        "url": url,
        "domain": normalize_domain(url),
        "title": title,
        "description": description,
        "h1": h1.get_text(" ", strip=True) if h1 else "",
        "h2_count": h2_count,
        "has_price_words": _text_contains(text, PRICE_WORDS),
        "has_contact_words": _text_contains(text, CONTACT_WORDS),
        "has_faq_words": _text_contains(text, FAQ_WORDS),
        "content_length": len(text),
        "commercial_words_found": commercial_words_found,
        "fetch_status": "ok",
        "error": "",
    }


def crawl_competitor_page(url):
    normalized_url = _normalize_url(url)
    if not normalized_url:
        return {
            "url": url,
            "domain": normalize_domain(url),
            "title": "",
            "description": "",
            "h1": "",
            "h2_count": 0,
            "has_price_words": False,
            "has_contact_words": False,
            "has_faq_words": False,
            "content_length": 0,
            "commercial_words_found": [],
            "fetch_status": "invalid_url",
            "error": "Некорректный URL конкурента.",
        }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }

    try:
        response = requests.get(normalized_url, headers=headers, timeout=PAGE_TIMEOUT)
    except requests.RequestException:
        data = extract_basic_seo("", normalized_url)
        data["fetch_status"] = "network_error"
        data["error"] = "Не удалось загрузить страницу конкурента."
        return data

    data = extract_basic_seo(response.text if response.status_code < 500 else "", normalized_url)
    data["fetch_status"] = f"HTTP {response.status_code}"
    if response.status_code >= 400:
        data["error"] = f"Страница ответила HTTP {response.status_code}."
    return data
