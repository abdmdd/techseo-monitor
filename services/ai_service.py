from services.score_service import build_score_summary


# ==================================================
# AI RECOMMENDATIONS
# ==================================================

def generate_ai_recommendations(result):
    recommendations = []
    errors = result.get("errors", [])

    for error in errors:
        error_lower = error.lower()

        if "robots" in error_lower:
            recommendations.append({
                "title": "Проблема с robots.txt",
                "priority": "Высокий",
                "recommendation": "Добавьте корректный robots.txt для управления индексацией."
            })
        elif "sitemap" in error_lower:
            recommendations.append({
                "title": "Проблема с sitemap.xml",
                "priority": "Высокий",
                "recommendation": "Создайте sitemap.xml и добавьте ссылку на него в robots.txt."
            })
        elif "canonical" in error_lower:
            recommendations.append({
                "title": "Проблема с canonical",
                "priority": "Средний",
                "recommendation": "Добавьте canonical для предотвращения дублей страниц."
            })
        elif "404" in error_lower:
            recommendations.append({
                "title": "Обнаружены 404 ошибки",
                "priority": "Высокий",
                "recommendation": "Исправьте битые ссылки или настройте корректные редиректы."
            })
        elif "duplicate" in error_lower or "дубли" in error_lower:
            recommendations.append({
                "title": "Дубли мета-тегов",
                "priority": "Средний",
                "recommendation": "Сделайте уникальные title и description для страниц с дублями."
            })
        elif "alt" in error_lower:
            recommendations.append({
                "title": "Изображения без alt",
                "priority": "Низкий",
                "recommendation": "Добавьте alt-атрибуты ко всем важным изображениям."
            })

    return recommendations


# ==================================================
# AI SEO SUMMARY
# ==================================================

def generate_ai_summary(score, errors_count):
    return build_score_summary(score, errors_count)


# ==================================================
# META GENERATOR
# ==================================================

def generate_meta_tags(site_name, page_topic, keywords):
    title = f"{page_topic} — {site_name}"
    description = (
        f"{page_topic}. Полезная информация по теме: {keywords}. "
        f"Узнайте подробнее на сайте {site_name}."
    )

    return {
        "title": title,
        "description": description,
        "og_title": title,
        "og_description": description
    }
