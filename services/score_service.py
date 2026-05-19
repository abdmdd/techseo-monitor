# ==================================================
# SEO SCORE
# ==================================================

def get_errors_count(result):
    return len(result.get("errors", []))


def calculate_seo_score(result):
    errors_count = get_errors_count(result)
    return max(0, 100 - errors_count * 10)


def get_score_risk(score):
    if score >= 90:
        return {
            "risk": "Низкий",
            "color": "#16a34a",
            "summary": "Сайт находится в хорошем техническом SEO-состоянии.",
            "report_status": "Отличное состояние SEO."
        }

    if score >= 70:
        return {
            "risk": "Средний",
            "color": "#f59e0b",
            "summary": "Обнаружены SEO-проблемы, которые рекомендуется исправить.",
            "report_status": "Хорошее состояние SEO, но есть проблемы."
        }

    if score >= 50:
        return {
            "risk": "Высокий",
            "color": "#dc2626",
            "summary": "Техническое состояние сайта требует заметной оптимизации.",
            "report_status": "Среднее состояние SEO. Требуются исправления."
        }

    return {
        "risk": "Критический",
        "color": "#991b1b",
        "summary": "Сайт имеет серьезные SEO-проблемы, которые могут влиять на индексацию.",
        "report_status": "Критическое состояние SEO."
    }


def build_score_summary(score, errors_count):
    score_risk = get_score_risk(score)

    return {
        "risk": score_risk["risk"],
        "summary": score_risk["summary"],
        "score": score,
        "errors_count": errors_count
    }
