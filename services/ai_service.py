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
