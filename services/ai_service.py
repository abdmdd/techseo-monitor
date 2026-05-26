import json

import requests

from config.settings import (
    YANDEX_GPT_API_KEY,
    YANDEX_GPT_FOLDER_ID,
    YANDEX_GPT_MODEL,
    YANDEX_GPT_TIMEOUT,
)
from services.score_service import build_score_summary


YANDEX_GPT_API_KEY = YANDEX_GPT_API_KEY.strip()
YANDEX_GPT_FOLDER_ID = YANDEX_GPT_FOLDER_ID.strip()
YANDEX_GPT_MODEL = YANDEX_GPT_MODEL.strip()
YANDEX_GPT_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


def yandex_gpt_available():
    return bool(YANDEX_GPT_API_KEY and YANDEX_GPT_FOLDER_ID)


def _model_uri():
    return f"gpt://{YANDEX_GPT_FOLDER_ID}/{YANDEX_GPT_MODEL}/latest"


def _fallback_response(text, error=None):
    return {
        "ok": False,
        "text": text,
        "error": error or "YandexGPT недоступен",
    }


def call_yandex_gpt(system_prompt, user_prompt, temperature=0.3, max_tokens=900):
    if not yandex_gpt_available():
        return _fallback_response(
            "YandexGPT пока не подключен. Добавьте YANDEX_GPT_API_KEY и YANDEX_GPT_FOLDER_ID в .env."
        )

    headers = {
        "Authorization": f"Api-Key {YANDEX_GPT_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "modelUri": _model_uri(),
        "completionOptions": {
            "stream": False,
            "temperature": temperature,
            "maxTokens": str(max_tokens),
        },
        "messages": [
            {"role": "system", "text": system_prompt},
            {"role": "user", "text": user_prompt},
        ],
    }

    try:
        response = requests.post(
            YANDEX_GPT_URL,
            headers=headers,
            json=payload,
            timeout=YANDEX_GPT_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        alternatives = data.get("result", {}).get("alternatives", [])

        if not alternatives:
            return _fallback_response("YandexGPT вернул пустой ответ.", error="empty_response")

        text = alternatives[0].get("message", {}).get("text", "").strip()
        if not text:
            return _fallback_response("YandexGPT вернул пустой текст.", error="empty_text")

        return {"ok": True, "text": text, "error": None}
    except requests.Timeout:
        return _fallback_response("YandexGPT не ответил вовремя. Попробуйте повторить позже.", error="timeout")
    except requests.RequestException as exc:
        return _fallback_response(
            "YandexGPT сейчас недоступен. Платформа продолжает работать в fallback-режиме.",
            error=exc.__class__.__name__,
        )
    except (ValueError, KeyError, IndexError) as exc:
        return _fallback_response("Не удалось разобрать ответ YandexGPT.", error=exc.__class__.__name__)


def _extract_json_object(text):
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json\n", "", 1).replace("JSON\n", "", 1).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start:end + 1]

    return json.loads(cleaned)


def fallback_meta_variants(topic, url, tone="Сбалансированный"):
    clean_topic = topic.strip() or "SEO аудит сайта"
    clean_url = url.strip() or "https://example.ru"

    return {
        "ok": False,
        "source": "fallback",
        "message": "YandexGPT недоступен, показаны локальные fallback-варианты.",
        "titles": [
            f"{clean_topic}: SEO-аудит и план улучшений",
            f"Проверка SEO для {clean_topic} - ошибки и рекомендации",
            f"{clean_topic} | Технический аудит сайта",
            f"Как улучшить {clean_topic}: SEO-проверка",
        ],
        "descriptions": [
            f"Проверьте {clean_topic.lower()} на ошибки индексации, meta-теги, sitemap, robots, редиректы и битые ссылки.",
            f"SEO-анализ страницы {clean_url}: понятные рекомендации, приоритеты исправлений и план роста видимости.",
            f"Найдите технические проблемы сайта и получите краткий список действий для улучшения органического трафика.",
            f"Быстрая SEO-проверка: title, description, H1, canonical, sitemap.xml, robots.txt и ссылки.",
        ],
    }


def generate_meta_variants(topic, url, tone="Сбалансированный"):
    fallback = fallback_meta_variants(topic, url, tone)
    prompt = f"""
Сгенерируй SEO meta variants на русском языке.
Тема страницы: {topic or "не указана"}
URL: {url or "не указан"}
Тип варианта: {tone}

Верни строго JSON без markdown:
{{
  "titles": ["4 SEO title, 45-70 символов"],
  "descriptions": ["4 meta description, 110-160 символов"]
}}

Обязательно включи:
- короткий вариант
- длинный вариант
- balanced вариант
- emoji variant, если он уместен
"""
    response = call_yandex_gpt(
        "Ты SEO-копирайтер. Пиши ясно, без воды, без обещаний невозможного.",
        prompt,
        temperature=0.55,
        max_tokens=900,
    )

    if not response["ok"]:
        fallback["message"] = response["text"]
        return fallback

    try:
        data = _extract_json_object(response["text"])
        titles = [str(item).strip() for item in data.get("titles", []) if str(item).strip()]
        descriptions = [str(item).strip() for item in data.get("descriptions", []) if str(item).strip()]

        if not titles or not descriptions:
            raise ValueError("empty_meta_json")

        return {
            "ok": True,
            "source": "yandexgpt",
            "message": "Сгенерировано через YandexGPT.",
            "titles": titles[:6],
            "descriptions": descriptions[:6],
        }
    except (ValueError, TypeError, json.JSONDecodeError):
        fallback["message"] = "YandexGPT ответил неструктурированно, показаны fallback-варианты."
        return fallback


def correct_text_with_yandexgpt(text):
    if not text.strip():
        return {
            "ok": False,
            "source": "fallback",
            "message": "Добавьте текст для проверки.",
            "corrected": "",
        }

    response = call_yandex_gpt(
        "Ты редактор русского SEO-текста. Исправляй орфографию, пунктуацию и явные опечатки. Смысл не меняй.",
        f"Исправь текст и верни только исправленную версию:\n\n{text}",
        temperature=0.1,
        max_tokens=900,
    )

    if response["ok"]:
        return {
            "ok": True,
            "source": "yandexgpt",
            "message": "Текст проверен через YandexGPT.",
            "corrected": response["text"],
        }

    corrected = text.strip().replace("  ", " ")
    if corrected and corrected[-1] not in ".!?":
        corrected += "."
    corrected = corrected[0].upper() + corrected[1:] if corrected else ""

    return {
        "ok": False,
        "source": "fallback",
        "message": response["text"],
        "corrected": corrected,
    }


def _local_recommendations(result):
    recommendations = []
    errors = result.get("errors", [])

    for error in errors:
        error_lower = str(error).lower()

        if "robots" in error_lower:
            recommendations.append({
                "title": "Проверьте robots.txt",
                "priority": "Высокий",
                "recommendation": "Убедитесь, что robots.txt доступен, содержит User-agent и не закрывает важные разделы.",
            })
        elif "sitemap" in error_lower:
            recommendations.append({
                "title": "Проверьте sitemap.xml",
                "priority": "Высокий",
                "recommendation": "Создайте корректный sitemap.xml и добавьте ссылку на него в robots.txt.",
            })
        elif "canonical" in error_lower:
            recommendations.append({
                "title": "Проверьте canonical",
                "priority": "Средний",
                "recommendation": "Добавьте self canonical на основные страницы и проверьте, что canonical не ведёт на ошибочные URL.",
            })
        elif "404" in error_lower or "broken" in error_lower:
            recommendations.append({
                "title": "Исправьте битые ссылки",
                "priority": "Высокий",
                "recommendation": "Обновите ссылки на рабочие URL или настройте корректные 301-редиректы.",
            })
        elif "duplicate" in error_lower or "дубли" in error_lower:
            recommendations.append({
                "title": "Уберите дубли meta-тегов",
                "priority": "Средний",
                "recommendation": "Сделайте уникальные title и description для важных страниц.",
            })

    if not recommendations and result.get("broken_links_total", 0):
        recommendations.append({
            "title": "Проверьте битые ссылки",
            "priority": "Высокий",
            "recommendation": "В аудите найдены недоступные ссылки. Начните с внутренних ссылок на важные страницы.",
        })

    return recommendations[:5]


def generate_ai_recommendations(result):
    fallback = _local_recommendations(result)
    compact_result = {
        "errors": result.get("errors", [])[:12],
        "crawler_warnings": result.get("crawler_warnings", [])[:8],
        "broken_links_total": result.get("broken_links_total", 0),
        "crawled_pages_count": result.get("crawled_pages_count", 0),
        "sitemap": result.get("sitemap"),
        "robots_txt": result.get("robots_txt"),
        "meta_summary": result.get("meta_audit", {}).get("summary", {}),
        "canonical_summary": result.get("canonical_analysis", {}).get("summary", {}),
    }

    response = call_yandex_gpt(
        "Ты SEO-консультант для владельца бизнеса. Дай краткие, понятные и практичные рекомендации.",
        f"""
По результатам аудита сформируй 3-5 кратких SEO рекомендаций на русском.
Верни строго JSON:
{{"recommendations": [{{"title": "...", "priority": "Высокий|Средний|Низкий", "recommendation": "..."}}]}}

Данные аудита:
{json.dumps(compact_result, ensure_ascii=False)}
""",
        temperature=0.35,
        max_tokens=900,
    )

    if not response["ok"]:
        return fallback

    try:
        data = _extract_json_object(response["text"])
        recommendations = data.get("recommendations", [])
        normalized = []

        for item in recommendations:
            normalized.append({
                "title": str(item.get("title", "SEO рекомендация")).strip(),
                "priority": str(item.get("priority", "Средний")).strip(),
                "recommendation": str(item.get("recommendation", "")).strip(),
            })

        return [item for item in normalized if item["recommendation"]][:5] or fallback
    except (ValueError, TypeError, json.JSONDecodeError, AttributeError):
        return fallback


def generate_ai_summary(score, errors_count):
    return build_score_summary(score, errors_count)


def generate_meta_tags(site_name, page_topic, keywords):
    result = generate_meta_variants(
        topic=f"{page_topic}. Ключевые слова: {keywords}",
        url=site_name,
        tone="Сбалансированный",
    )
    title = result["titles"][0]
    description = result["descriptions"][0]

    return {
        "title": title,
        "description": description,
        "og_title": title,
        "og_description": description,
    }


def _unwrap_audit_result(audit_result):
    if not isinstance(audit_result, dict):
        return {}

    result = audit_result.get("result")
    if isinstance(result, dict) and isinstance(result.get("result"), dict):
        return result["result"]
    if isinstance(result, dict):
        return result
    return audit_result


def _safe_list(value, limit=None):
    if isinstance(value, list):
        items = value
    elif value:
        items = [value]
    else:
        items = []
    return items[:limit] if limit else items


def _safe_int(value, default=0):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def _json_or_none(text):
    try:
        return _extract_json_object(text)
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def _meta_problem_pages(result, limit=10):
    meta_audit = result.get("meta_audit") or {}
    rows = meta_audit.get("rows") if isinstance(meta_audit, dict) else None
    rows = rows or result.get("pages_meta") or []
    problem_rows = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        issues = row.get("issues") or []
        has_issue = bool(issues) or _safe_int(row.get("issues_count")) > 0
        if not has_issue:
            continue
        problem_rows.append({
            "url": row.get("url", ""),
            "title": row.get("title", ""),
            "description": row.get("description", ""),
            "h1": row.get("h1", ""),
            "issues": [
                issue.get("title") if isinstance(issue, dict) else str(issue)
                for issue in issues
            ],
        })

    return problem_rows[:limit]


def _fallback_ai_audit_insight(audit_result, site_info, message=None):
    site_info = site_info or {}
    result = _unwrap_audit_result(audit_result)
    site_name = site_info.get("name") or site_info.get("url") or "сайт"
    crawled = _safe_int(result.get("crawled_pages_count") or len(result.get("crawled_pages") or []))
    broken_links_total = _safe_int(result.get("broken_links_total") or len(result.get("broken_links") or []))
    errors = _safe_list(result.get("errors"), 12)
    meta_audit = result.get("meta_audit") if isinstance(result.get("meta_audit"), dict) else {}
    meta_summary = meta_audit.get("summary", {})
    meta_issues = (
        _safe_int(meta_summary.get("title_issues"))
        + _safe_int(meta_summary.get("description_issues"))
        + _safe_int(meta_summary.get("h1_issues"))
    )
    robots_value = str(result.get("robots_txt") or "")
    sitemap_value = str(result.get("sitemap") or "")
    redirect_analysis = result.get("redirect_analysis") if isinstance(result.get("redirect_analysis"), dict) else {}
    redirects = _safe_list(result.get("redirect_chains") or redirect_analysis.get("rows"), 10)

    problems = []
    if errors:
        problems.append({
            "priority": "critical",
            "title": "В аудите есть критичные ошибки",
            "why_it_matters": "Критичные ошибки могут мешать индексации, обходу сайта и нормальной оценке страниц поисковыми системами.",
            "how_to_fix": "Начните с раздела центра ошибок, устраните причины и запустите повторный Monthly Audit.",
            "affected_urls": [],
        })
    if broken_links_total:
        problems.append({
            "priority": "high",
            "title": "Найдены битые ссылки",
            "why_it_matters": "404 и недоступные ссылки ухудшают пользовательский путь и расходуют краулинговый бюджет.",
            "how_to_fix": "Замените ссылки на рабочие URL или настройте корректные 301-редиректы.",
            "affected_urls": [
                item.get("url") or item.get("source_url") or item.get("target_url") or ""
                for item in _safe_list(result.get("broken_links"), 8)
                if isinstance(item, dict)
            ],
        })
    if meta_issues:
        problems.append({
            "priority": "high",
            "title": "Есть проблемы в title, description или H1",
            "why_it_matters": "Meta-теги и H1 влияют на релевантность, CTR и понятность страницы для пользователя.",
            "how_to_fix": "Исправьте пустые, дублирующиеся и слишком длинные теги на приоритетных страницах.",
            "affected_urls": [item.get("url", "") for item in _meta_problem_pages(result, 8)],
        })
    if "ok" not in robots_value.lower() and robots_value:
        problems.append({
            "priority": "medium",
            "title": "Проверьте robots.txt",
            "why_it_matters": "Ошибочные правила robots.txt могут закрывать важные страницы от обхода.",
            "how_to_fix": "Убедитесь, что robots.txt доступен, содержит нужный Sitemap и не блокирует коммерческие разделы.",
            "affected_urls": [],
        })
    if "ok" not in sitemap_value.lower() and sitemap_value:
        problems.append({
            "priority": "medium",
            "title": "Проверьте sitemap.xml",
            "why_it_matters": "Sitemap помогает поисковым системам быстрее находить важные страницы.",
            "how_to_fix": "Оставьте в sitemap только канонические 200-страницы и укажите файл в robots.txt.",
            "affected_urls": [],
        })
    if redirects:
        problems.append({
            "priority": "medium",
            "title": "Есть редиректы или цепочки редиректов",
            "why_it_matters": "Лишние переходы замедляют загрузку и усложняют обход сайта.",
            "how_to_fix": "Сведите редиректы к одному 301-переходу на финальный URL.",
            "affected_urls": [],
        })
    if not problems:
        problems.append({
            "priority": "low",
            "title": "Критичных проблем не найдено",
            "why_it_matters": "Сайт можно улучшать точечно: сниппеты, структура, контент и коммерческие факторы.",
            "how_to_fix": "Посмотрите страницы с низким CTR, обновите meta-теги и расширьте полезный контент.",
            "affected_urls": [],
        })

    pages = []
    for page in _meta_problem_pages(result, 10):
        title_base = page.get("h1") or site_name
        pages.append({
            "url": page.get("url", ""),
            "current_title": page.get("title", ""),
            "current_description": page.get("description", ""),
            "h1": page.get("h1", ""),
            "problems": [issue for issue in page.get("issues", []) if issue],
            "improved_title": f"{title_base}: услуги, цены и преимущества",
            "improved_description": f"Узнайте подробнее про {title_base}: условия, преимущества, ответы на вопросы и удобный способ связаться с компанией.",
            "intent_comment": "Уточните поисковый интент страницы и отразите его в title, H1 и первом экране.",
            "ctr_comment": "Добавьте конкретику, выгоду и понятный объект страницы, чтобы сниппет был заметнее в выдаче.",
        })

    tasks = [
        {
            "task": item["how_to_fix"],
            "priority": item["priority"],
            "source_section": item["title"],
            "expected_result": "Проблема исправлена и подтверждена повторной проверкой.",
        }
        for item in problems
    ]

    return {
        "ok": False,
        "source": "fallback",
        "message": message or "AI-анализ собран локально: YandexGPT недоступен или вернул неструктурированный ответ.",
        "ai_summary": {
            "summary": f"По сайту {site_name} проверено страниц: {crawled}. Главные сигналы аудита собраны в приоритетный список ниже.",
            "what_is_bad": f"Найдено проблем: meta/H1 - {meta_issues}, битые ссылки - {broken_links_total}, технические ошибки - {len(errors)}.",
            "critical": "В первую очередь проверьте критичные ошибки, битые ссылки, индексацию и страницы с проблемами meta-тегов.",
            "first_actions": "Начните с исправления ошибок обхода, затем обновите title/description/H1 на страницах с проблемами и повторите аудит.",
        },
        "priority_center": problems[:12],
        "tasks": tasks[:20],
        "page_analyzer": pages,
    }


def _normalize_ai_insight(data, fallback):
    if not isinstance(data, dict):
        return fallback

    summary = data.get("ai_summary") if isinstance(data.get("ai_summary"), dict) else {}
    problems = data.get("priority_center") if isinstance(data.get("priority_center"), list) else []
    tasks = data.get("tasks") if isinstance(data.get("tasks"), list) else []
    pages = data.get("page_analyzer") if isinstance(data.get("page_analyzer"), list) else []

    normalized = {
        "ok": True,
        "source": "yandexgpt",
        "message": data.get("message") or "AI-анализ сформирован через YandexGPT.",
        "ai_summary": {
            "summary": str(summary.get("summary") or fallback["ai_summary"]["summary"]).strip(),
            "what_is_bad": str(summary.get("what_is_bad") or fallback["ai_summary"]["what_is_bad"]).strip(),
            "critical": str(summary.get("critical") or fallback["ai_summary"]["critical"]).strip(),
            "first_actions": str(summary.get("first_actions") or fallback["ai_summary"]["first_actions"]).strip(),
        },
        "priority_center": [],
        "tasks": [],
        "page_analyzer": [],
    }

    allowed_priorities = {"critical", "high", "medium", "low"}
    for item in problems[:12]:
        if not isinstance(item, dict):
            continue
        priority = str(item.get("priority") or "medium").strip().lower()
        normalized["priority_center"].append({
            "priority": priority if priority in allowed_priorities else "medium",
            "title": str(item.get("title") or "SEO-проблема").strip(),
            "why_it_matters": str(item.get("why_it_matters") or "Может ухудшать индексацию, видимость или кликабельность.").strip(),
            "how_to_fix": str(item.get("how_to_fix") or "Проверьте раздел аудита и исправьте первопричину.").strip(),
            "affected_urls": [str(url).strip() for url in _safe_list(item.get("affected_urls"), 10) if str(url).strip()],
        })

    for item in tasks[:20]:
        if not isinstance(item, dict):
            continue
        normalized["tasks"].append({
            "task": str(item.get("task") or "Проверить SEO-проблему").strip(),
            "priority": str(item.get("priority") or "medium").strip().lower(),
            "source_section": str(item.get("source_section") or "Monthly Audit").strip(),
            "expected_result": str(item.get("expected_result") or "Проблема исправлена и подтверждена повторным аудитом.").strip(),
        })

    for item in pages[:10]:
        if not isinstance(item, dict):
            continue
        normalized["page_analyzer"].append({
            "url": str(item.get("url") or "").strip(),
            "current_title": str(item.get("current_title") or "").strip(),
            "current_description": str(item.get("current_description") or "").strip(),
            "h1": str(item.get("h1") or "").strip(),
            "problems": [str(problem).strip() for problem in _safe_list(item.get("problems"), 8) if str(problem).strip()],
            "improved_title": str(item.get("improved_title") or "").strip(),
            "improved_description": str(item.get("improved_description") or "").strip(),
            "intent_comment": str(item.get("intent_comment") or "").strip(),
            "ctr_comment": str(item.get("ctr_comment") or "").strip(),
        })

    normalized["priority_center"] = normalized["priority_center"] or fallback["priority_center"]
    normalized["tasks"] = normalized["tasks"] or fallback["tasks"]
    normalized["page_analyzer"] = normalized["page_analyzer"] or fallback["page_analyzer"]
    return normalized


def _compact_audit_context(audit_result, site_info):
    result = _unwrap_audit_result(audit_result)
    redirect_analysis = result.get("redirect_analysis") if isinstance(result.get("redirect_analysis"), dict) else {}
    meta_audit = result.get("meta_audit") if isinstance(result.get("meta_audit"), dict) else {}
    return {
        "site": {
            "name": site_info.get("name"),
            "url": site_info.get("url"),
            "yandex_webmaster_summary": site_info.get("yandex_webmaster_summary"),
            "yandex_metrika_summary": site_info.get("yandex_metrika_summary"),
        },
        "score": audit_result.get("score") or audit_result.get("seo_score"),
        "errors_count": audit_result.get("errors_count"),
        "crawl_result": {
            "crawled_pages_count": result.get("crawled_pages_count"),
            "broken_links_total": result.get("broken_links_total"),
            "errors": _safe_list(result.get("errors"), 12),
        },
        "meta_audit": {
            "summary": meta_audit.get("summary", {}),
            "problem_pages": _meta_problem_pages(result, 10),
        },
        "canonical": result.get("canonical_analysis") or result.get("canonical"),
        "robots": result.get("robots_txt"),
        "sitemap": result.get("sitemap"),
        "broken_links": _safe_list(result.get("broken_links"), 15),
        "redirects": _safe_list(result.get("redirect_chains") or redirect_analysis.get("rows"), 15),
        "reviews": result.get("reviews") or result.get("reviews_summary"),
    }


def generate_ai_audit_insight(audit_result, site_info):
    audit_result = audit_result or {}
    site_info = site_info or {}
    fallback = _fallback_ai_audit_insight(audit_result, site_info)
    compact_context = _compact_audit_context(audit_result, site_info)

    response = call_yandex_gpt(
        "Ты senior SEO-стратег. Верни только валидный JSON на русском языке. Не добавляй markdown и пояснения вне JSON.",
        f"""
Сформируй AI-анализ последнего Monthly Audit.
Не выдумывай данные Яндекс Вебмастера или Метрики: если данных нет, так и напиши.
Анализируй максимум 10 страниц из meta_audit.problem_pages.

Структура ответа:
{{
  "ai_summary": {{
    "summary": "краткий человеческий вывод",
    "what_is_bad": "что плохо",
    "critical": "что критично",
    "first_actions": "что делать первым"
  }},
  "priority_center": [
    {{
      "priority": "critical|high|medium|low",
      "title": "...",
      "why_it_matters": "...",
      "how_to_fix": "...",
      "affected_urls": ["..."]
    }}
  ],
  "tasks": [
    {{
      "task": "...",
      "priority": "critical|high|medium|low",
      "source_section": "crawl|meta|canonical|robots|sitemap|links|redirects|reviews|yandex_webmaster|yandex_metrika",
      "expected_result": "..."
    }}
  ],
  "page_analyzer": [
    {{
      "url": "...",
      "current_title": "...",
      "current_description": "...",
      "h1": "...",
      "problems": ["..."],
      "improved_title": "...",
      "improved_description": "...",
      "intent_comment": "...",
      "ctr_comment": "..."
    }}
  ]
}}

Данные аудита:
{json.dumps(compact_context, ensure_ascii=False, default=str)}
""",
        temperature=0.25,
        max_tokens=3500,
    )

    if not response["ok"]:
        fallback["message"] = response["text"]
        return fallback

    data = _json_or_none(response["text"])
    if data is None:
        fallback["message"] = "YandexGPT вернул невалидный JSON. Показан безопасный локальный анализ."
        return fallback

    return _normalize_ai_insight(data, fallback)


def generate_text_check_analysis(text, tone):
    source_text = (text or "").strip()
    normalized_tone = (tone or "деловой").strip()
    if not source_text:
        return {
            "ok": False,
            "source": "fallback",
            "message": "Добавьте текст для проверки.",
            "errors": [],
            "explanations": [],
            "corrected_text": "",
            "improved_text": "",
        }

    fallback_text = source_text.replace("  ", " ")
    if fallback_text and fallback_text[-1] not in ".!?":
        fallback_text += "."
    fallback_text = fallback_text[0].upper() + fallback_text[1:] if fallback_text else ""
    fallback = {
        "ok": False,
        "source": "fallback",
        "message": "YandexGPT недоступен или вернул неструктурированный ответ. Показана мягкая локальная правка.",
        "errors": [],
        "explanations": ["Локально исправлены лишние пробелы, первая буква и финальная пунктуация."],
        "corrected_text": fallback_text,
        "improved_text": fallback_text,
    }

    response = call_yandex_gpt(
        "Ты редактор русского SEO-текста. Верни только валидный JSON без markdown.",
        f"""
Проверь текст и адаптируй улучшенную версию под тон: {normalized_tone}.

Верни JSON:
{{
  "errors": ["кратко найденные ошибки"],
  "explanations": ["пояснения ошибок"],
  "corrected_text": "исправленный вариант без изменения смысла",
  "improved_text": "улучшенный вариант под выбранный тон"
}}

Текст:
{source_text}
""",
        temperature=0.2,
        max_tokens=2200,
    )

    if not response["ok"]:
        fallback["message"] = response["text"]
        return fallback

    data = _json_or_none(response["text"])
    if not isinstance(data, dict):
        return fallback

    return {
        "ok": True,
        "source": "yandexgpt",
        "message": "Текст проверен через YandexGPT.",
        "errors": [str(item).strip() for item in _safe_list(data.get("errors"), 20) if str(item).strip()],
        "explanations": [str(item).strip() for item in _safe_list(data.get("explanations"), 20) if str(item).strip()],
        "corrected_text": str(data.get("corrected_text") or fallback["corrected_text"]).strip(),
        "improved_text": str(data.get("improved_text") or fallback["improved_text"]).strip(),
    }


def generate_competitor_analysis(own_site, topic, competitors):
    clean_site = (own_site or "").strip()
    clean_topic = (topic or "").strip()
    clean_competitors = (competitors or "").strip()
    if not clean_competitors:
        return {
            "ok": False,
            "source": "fallback",
            "message": "Добавьте конкурентов вручную, чтобы сформировать MVP-анализ.",
            "competitor_strengths": [],
            "our_weaknesses": [],
            "recommendations": [],
            "conclusion": "",
        }

    fallback = {
        "ok": False,
        "source": "fallback",
        "message": "YandexGPT недоступен или вернул неструктурированный ответ. Показана базовая структура анализа.",
        "competitor_strengths": ["Проверьте title, H1, структуру первого экрана и полноту коммерческой информации у каждого конкурента."],
        "our_weaknesses": ["Сравните посадочные страницы по интенту, структуре, доказательствам доверия и ответам на частые вопросы."],
        "recommendations": [
            "Соберите лучшие формулировки title/H1 и адаптируйте их без копирования.",
            "Усилите структуру страницы блоками: преимущества, цены/условия, FAQ, отзывы, контакты.",
            "Добавьте контент под реальные запросы пользователя и коммерческие факторы доверия.",
        ],
        "conclusion": "SERP-парсер пока не используется, поэтому вывод основан на вручную введённых конкурентах.",
    }

    response = call_yandex_gpt(
        "Ты SEO-аналитик конкурентов. Верни только валидный JSON без markdown.",
        f"""
Сравни наш сайт с вручную указанными конкурентами.

Наш сайт: {clean_site or "не указан"}
Тематика / запросы: {clean_topic or "не указаны"}
Конкуренты:
{clean_competitors}

Верни JSON:
{{
  "competitor_strengths": ["сильные стороны конкурентов"],
  "our_weaknesses": ["слабые стороны нашего сайта"],
  "recommendations": ["рекомендации по title/H1/структуре/контенту"],
  "conclusion": "краткий вывод"
}}
""",
        temperature=0.3,
        max_tokens=2200,
    )

    if not response["ok"]:
        fallback["message"] = response["text"]
        return fallback

    data = _json_or_none(response["text"])
    if not isinstance(data, dict):
        return fallback

    return {
        "ok": True,
        "source": "yandexgpt",
        "message": "Анализ конкурентов сформирован через YandexGPT.",
        "competitor_strengths": [str(item).strip() for item in _safe_list(data.get("competitor_strengths"), 12) if str(item).strip()],
        "our_weaknesses": [str(item).strip() for item in _safe_list(data.get("our_weaknesses"), 12) if str(item).strip()],
        "recommendations": [str(item).strip() for item in _safe_list(data.get("recommendations"), 16) if str(item).strip()],
        "conclusion": str(data.get("conclusion") or fallback["conclusion"]).strip(),
    }
