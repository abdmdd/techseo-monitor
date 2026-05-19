from crawlers.seo_crawler import check_technical_seo

from services.score_service import (
    calculate_seo_score,
    get_errors_count
)


# ==================================================
# MONTHLY AUDIT
# ==================================================

def run_monthly_audit(url):

    result = check_technical_seo(url)

    errors_count = get_errors_count(result)
    score = calculate_seo_score(result)

    return {
        "result": result,
        "errors_count": errors_count,
        "score": score
    }


# ==================================================
# QUARTERLY AUDIT
# ==================================================

def run_quarterly_audit(url):

    result = check_technical_seo(url)

    errors_count = get_errors_count(result)
    score = calculate_seo_score(result)

    advanced_checks = {

        "pagespeed": "Не подключено",
        "core_web_vitals": "Не подключено",
        "google_indexing": "Не подключено",
        "safe_browsing": "Не подключено",
        "mobile_usability": "Не подключено",
        "structured_data": "Не подключено"
    }

    return {
        "result": result,
        "errors_count": errors_count,
        "score": score,
        "advanced_checks": advanced_checks
    }
