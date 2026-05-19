import re

from playwright.sync_api import sync_playwright


def normalize_text(text):
    return " ".join(text.replace("\n", " ").split())


def extract_rating(text):
    patterns = [
        r"([1-5][,.]\d)",
        r"рейтинг[:\s]+([1-5][,.]\d)",
        r"rating[:\s]+([1-5][,.]\d)"
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).replace(",", ".")

    return "не найдено"


def extract_reviews_count(text):
    patterns = [
        r"(\d[\d\s]*)\s+отзыв",
        r"(\d[\d\s]*)\s+reviews",
        r"(\d[\d\s]*)\s+оцен"
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).replace(" ", "")

    return "не найдено"


def parse_reviews_page(url, platform):
    if not url:
        return {
            "platform": platform,
            "rating": "не подключено",
            "reviews_count": "не подключено",
            "status": "ссылка не указана",
            "url": ""
        }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(5000)
            text = normalize_text(page.inner_text("body"))
            browser.close()

        rating = extract_rating(text)
        reviews_count = extract_reviews_count(text)
        status = "OK"

        if rating == "не найдено" and reviews_count == "не найдено":
            status = "данные не найдены"

        return {
            "platform": platform,
            "rating": rating,
            "reviews_count": reviews_count,
            "status": status,
            "url": url
        }

    except Exception as e:
        return {
            "platform": platform,
            "rating": "ошибка",
            "reviews_count": "ошибка",
            "status": str(e),
            "url": url
        }


def check_reviews(yandex_url="", google_url="", twogis_url=""):
    return [
        parse_reviews_page(yandex_url, "Яндекс.Карты"),
        parse_reviews_page(google_url, "Google Maps"),
        parse_reviews_page(twogis_url, "2ГИС")
    ]
