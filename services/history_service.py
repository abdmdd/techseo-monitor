from database.db import save_audit_result


def save_audit_history(url, audit_type, result, score, errors_count):
    save_audit_result(
        site_url=url,
        audit_type=audit_type,
        seo_score=score,
        errors_count=errors_count,
        title=result.get("title", "—"),
        description=result.get("description", "—"),
        canonical=result.get("canonical", "—"),
        h1=result.get("h1", "—"),
        robots_txt=result.get("robots_txt", "—"),
        sitemap=result.get("sitemap", "—")
    )
