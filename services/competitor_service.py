import re
from collections import Counter
from urllib.parse import urlparse

from crawlers.seo_crawler import normalize_url, parse_page_meta, safe_get


STOPWORDS = {
    "для", "или", "как", "что", "это", "все", "при", "под", "над", "без", "про", "ваш", "ваша",
    "сайт", "сайта", "сайты", "страница", "страницы", "главная", "услуги", "купить", "цена",
    "the", "and", "for", "with", "from", "your", "you", "site", "page", "home",
}


COMPETITOR_CATALOG = [
    {
        "domain": "auditlab.ru",
        "title": "Платформа для технического SEO-аудита сайта",
        "description": "Мониторинг ошибок, sitemap, robots.txt, canonical, meta-теги и понятные SEO-рекомендации.",
        "theme": "Технический SEO-аудит и мониторинг сайта",
        "keywords": ["seo", "аудит", "технический", "мониторинг", "sitemap", "robots", "canonical", "meta"],
    },
    {
        "domain": "rankpilot.io",
        "title": "Мониторинг позиций и SEO-аналитика",
        "description": "Проверка видимости, ключевых слов, конкурентов и динамики поискового роста.",
        "theme": "Позиции, видимость и поисковая аналитика",
        "keywords": ["позиции", "видимость", "ключевые", "аналитика", "seo", "конкуренты", "поиск"],
    },
    {
        "domain": "webmasterpro.ru",
        "title": "Инструменты для вебмастера и индексации",
        "description": "Проверка sitemap.xml, robots.txt, индексации, редиректов и технических ошибок сайта.",
        "theme": "Вебмастер-инструменты и индексация",
        "keywords": ["webmaster", "вебмастер", "индексация", "robots", "sitemap", "редиректы", "ошибки"],
    },
    {
        "domain": "metagen.ai",
        "title": "AI для SEO-текстов и meta-тегов",
        "description": "Генерация title, description, подсказок для контента и улучшения сниппетов.",
        "theme": "Нейросети для SEO и контента",
        "keywords": ["ai", "нейросети", "meta", "title", "description", "контент", "сниппет"],
    },
    {
        "domain": "serpmetrics.ai",
        "title": "Анализ конкурентов и поисковой выдачи",
        "description": "Анализ поисковой выдачи, пересечение ключевых слов, поиск конкурентов и оценка видимости.",
        "theme": "Конкурентная разведка и поисковая выдача",
        "keywords": ["serp", "конкуренты", "overlap", "keywords", "видимость", "поисковая", "анализ"],
    },
    {
        "domain": "linkwatch.ru",
        "title": "Проверка битых ссылок и редиректов",
        "description": "Поиск broken links, redirect chains, 404, 500 и проблем внутренней перелинковки.",
        "theme": "Битые ссылки и редиректы",
        "keywords": ["битые", "ссылки", "broken", "redirect", "404", "500", "перелинковка"],
    },
]


def domain_from_url(url):
    normalized = normalize_url(url)
    parsed = urlparse(normalized or url)
    return parsed.netloc or (url or "").strip() or "ваш-сайт.ru"


def extract_keywords(*texts, limit=14):
    words = []

    for text in texts:
        for word in re.findall(r"[A-Za-zА-Яа-яЁё0-9-]{3,}", str(text or "").lower()):
            cleaned = word.strip("-")
            if cleaned and cleaned not in STOPWORDS:
                words.append(cleaned)

    counter = Counter(words)
    return [word for word, _ in counter.most_common(limit)]


def fetch_site_profile(site_url, manual_keywords=""):
    url = normalize_url(site_url)
    profile = {
        "url": url or site_url,
        "domain": domain_from_url(site_url),
        "title": "",
        "description": "",
        "h1": "",
        "keywords": extract_keywords(manual_keywords),
        "fetch_status": "not_started",
        "fetch_error": "",
    }

    if not url:
        profile["fetch_status"] = "invalid_url"
        profile["fetch_error"] = "Введите полный URL сайта, например https://example.ru"
        return profile

    response, error = safe_get(url, headers={"User-Agent": "Mozilla/5.0 TechSEO Monitor Bot"}, timeout=12)

    if error:
        profile["fetch_status"] = "error"
        profile["fetch_error"] = f"Не удалось получить главную страницу: {error}"
        return profile

    profile["fetch_status"] = f"HTTP {response.status_code}"

    if response.status_code >= 400:
        profile["fetch_error"] = f"Главная страница ответила статусом HTTP {response.status_code}"

    meta = parse_page_meta(url, response.text or "")
    profile["title"] = meta.get("title", "")
    profile["description"] = meta.get("description", "")
    profile["h1"] = meta.get("h1_list", [""])[0] if meta.get("h1_list") else ""
    profile["keywords"] = extract_keywords(
        manual_keywords,
        profile["title"],
        profile["description"],
        profile["h1"],
        limit=18,
    )
    return profile


def discover_competitors(site_url, manual_keywords=""):
    profile = fetch_site_profile(site_url, manual_keywords)
    site_keywords = set(profile.get("keywords", []))
    competitors = []

    for candidate in COMPETITOR_CATALOG:
        candidate_keywords = set(candidate["keywords"])
        overlap = sorted(site_keywords & candidate_keywords)
        soft_overlap = [
            keyword
            for keyword in candidate["keywords"]
            if any(keyword in source or source in keyword for source in site_keywords)
        ]
        overlap_keywords = sorted(set(overlap + soft_overlap))
        overlap_score = min(100, round((len(overlap_keywords) / max(1, len(candidate_keywords))) * 100))

        if overlap_score == 0 and manual_keywords:
            overlap_score = 12

        competitors.append({
            "domain": candidate["domain"],
            "title": candidate["title"],
            "description": candidate["description"],
            "theme": candidate["theme"],
            "keywords": candidate["keywords"],
            "overlap_keywords": overlap_keywords[:8],
            "overlap_score": overlap_score,
            "discovery_source": "Локальный MVP-каталог тематик",
        })

    competitors = sorted(competitors, key=lambda item: item["overlap_score"], reverse=True)
    competitors = [item for item in competitors if item["overlap_score"] > 0][:5]

    if not competitors:
        competitors = [
            {
                **candidate,
                "overlap_keywords": candidate["keywords"][:3],
                "overlap_score": 10,
                "discovery_source": "Базовая тематическая заготовка",
            }
            for candidate in COMPETITOR_CATALOG[:3]
        ]

    all_overlap = sorted({keyword for item in competitors for keyword in item["overlap_keywords"]})

    return {
        "site_profile": profile,
        "competitors": competitors,
        "summary": {
            "competitors_found": len(competitors),
            "site_keywords_count": len(profile.get("keywords", [])),
            "overlap_keywords_count": len(all_overlap),
            "best_overlap": competitors[0]["overlap_score"] if competitors else 0,
        },
        "overlap_keywords": all_overlap,
        "future_architecture": {
            "serp_parser": "prepared",
            "visibility_analysis": "prepared",
            "keyword_clustering": "prepared",
        },
    }
