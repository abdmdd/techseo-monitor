import time
from html import escape

import pandas as pd
import streamlit as st

from components.ui_helpers import metric_card, recommendation_card, warnings_block
from services.ai_service import generate_ai_recommendations, generate_ai_summary
from services.audit_service import enqueue_monthly_audit, get_latest_monthly_audit_job
from views.auth_page import require_user_id
from views.cached_data import cached_get_sites, clear_cached_data


def select_site_from_db(label):
    sites = cached_get_sites(user_id=require_user_id())

    if sites:
        site_options = {"": None}
        site_options.update({
            f"{site[1]} - {site[2]}": site
            for site in sites
        })

        selected_site_label = st.selectbox(
            label,
            list(site_options.keys()),
            format_func=lambda option: "Выберите сайт" if not option else option,
        )
        return site_options[selected_site_label]

    st.warning("Сначала добавьте сайт во вкладке «Мои сайты».")

    manual_url = st.text_input(
        "Введите URL сайта вручную",
        "https://example.ru"
    )

    return (
        None,
        "Ручной сайт",
        manual_url,
        "",
        "",
        "",
        "",
        "",
        ""
    )


def section_header(title, subtitle):
    st.markdown(
        f"""
        <div class="ts-dashboard-section">
            <div class="ts-section-title">{escape(title)}</div>
            <div class="ts-section-subtitle">{escape(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def kv_card(title, rows):
    rows_html = "".join(
        f"""
        <div class="ts-audit-kv">
            <span>{escape(str(label))}</span>
            <strong>{escape(str(value))}</strong>
        </div>
        """
        for label, value in rows
    )

    st.markdown(
        f"""
        <div class="ts-audit-section-card">
            <div class="ts-audit-section-title">{escape(title)}</div>
            {rows_html}
        </div>
        """,
        unsafe_allow_html=True
    )


def empty_state(title, text):
    st.markdown(
        f"""
        <div class="ts-empty-state">
            <div class="ts-card-title">{escape(title)}</div>
            <div class="ts-card-text">{escape(text)}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_full_crawl_summary(result):
    full_crawl = result.get("full_crawl", {})
    crawled_pages = result.get("crawled_pages", [])
    redirects = result.get("redirect_chains", [])

    if not full_crawl.get("enabled") and not crawled_pages:
        empty_state(
            "Данные полного обхода пока недоступны",
            "Запустите новый ежемесячный аудит, чтобы собрать страницы, внутренние ссылки, редиректы и canonical."
        )
        return

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        metric_card("Страниц обойдено", result.get("crawled_pages_count", len(crawled_pages)), "Полный обход", "#2563eb")
    with col2:
        metric_card("Внутренних ссылок", result.get("internal_links_total", 0), "Найдено на страницах", "#0f766e")
    with col3:
        metric_card("Битых ссылок", result.get("broken_links_total", 0), "Недоступные адреса", "#dc2626")
    with col4:
        metric_card("Редиректов", len(redirects), "Найденные цепочки", "#f59e0b")
    kv_card(
        "Параметры полного обхода",
        [
            ("Стартовый URL", full_crawl.get("start_url", "—")),
            ("Базовый URL", full_crawl.get("base_url", "—")),
            ("Лимит страниц", full_crawl.get("max_pages", "—")),
            ("Посещено URL", full_crawl.get("visited_urls_count", "—")),
            ("Осталось в очереди", full_crawl.get("queued_urls_remaining", "—")),
        ]
    )


def error_intelligence(error):
    text = str(error).lower()

    rules = [
        {
            "markers": ["broken links", "битых ссыл", "404", "missing"],
            "category": "Битые ссылки",
            "severity": "критично",
            "class": "ts-severity-critical",
            "explanation": "Краулер нашел внутреннюю ссылку, которая ведет на ошибку или недоступную страницу.",
            "why": "Такие ссылки мешают пользователям и тратят внимание поисковых роботов.",
            "fix": "Исправьте адрес ссылки, восстановите страницу или добавьте подходящий 301-редирект.",
        },
        {
            "markers": ["missing title", "отсутствует title", "нет title"],
            "category": "Мета-теги",
            "severity": "критично",
            "class": "ts-severity-critical",
            "explanation": "На странице нет понятного title.",
            "why": "Title помогает поиску и пользователям быстро понять смысл страницы.",
            "fix": "Добавьте уникальный title на 50-70 символов с главным смыслом страницы.",
        },
        {
            "markers": ["missing description", "отсутствует description", "нет description"],
            "category": "Мета-теги",
            "severity": "важно",
            "class": "ts-severity-important",
            "explanation": "На странице нет понятного meta description.",
            "why": "Description часто помогает сделать сниппет в поиске более привлекательным.",
            "fix": "Добавьте уникальное описание на 120-160 символов с пользой страницы.",
        },
        {
            "markers": ["missing h1", "отсутствует h1", "нет h1"],
            "category": "Meta Tags",
            "severity": "important",
            "class": "ts-severity-important",
            "explanation": "The page has no primary H1 heading.",
            "why": "H1 helps users and crawlers understand the main topic of the page.",
            "fix": "Add one clear H1 that matches the page intent and does not duplicate navigation text.",
        },
        {
            "markers": ["missing canonical", "отсутствует canonical", "нет canonical", "canonical"],
            "category": "Canonical",
            "severity": "important",
            "class": "ts-severity-important",
            "explanation": "Canonical signal is missing or needs attention.",
            "why": "Canonical helps consolidate duplicate URLs and protect ranking signals from splitting.",
            "fix": "Add a self-referencing canonical or point duplicates to the preferred canonical URL.",
        },
        {
            "markers": ["redirect", "редирект"],
            "category": "Redirects",
            "severity": "recommendation",
            "class": "ts-severity-recommendation",
            "explanation": "Crawler detected a redirect chain or redirect configuration issue.",
            "why": "Long redirect chains slow down crawling and can dilute technical clarity.",
            "fix": "Keep redirects direct, avoid loops, and point old URLs to the final destination in one hop.",
        },
        {
            "markers": ["robots"],
            "category": "Robots.txt",
            "severity": "critical",
            "class": "ts-severity-critical",
            "explanation": "Robots.txt has a missing, unavailable or risky directive.",
            "why": "Robots rules can block crawling or hide important sections from search engines.",
            "fix": "Make robots.txt available, include User-agent rules, add Sitemap and review Disallow directives.",
        },
        {
            "markers": ["sitemap"],
            "category": "Sitemap.xml",
            "severity": "important",
            "class": "ts-severity-important",
            "explanation": "Sitemap.xml is missing, invalid, unavailable or incomplete.",
            "why": "Sitemap helps search engines discover important URLs and understand update signals.",
            "fix": "Generate a valid XML sitemap, keep it under size limits, add lastmod and reference it in robots.txt.",
        },
    ]

    for rule in rules:
        if any(marker in text for marker in rule["markers"]):
            return rule

    return {
        "category": "Technical",
        "severity": "recommendation",
        "class": "ts-severity-recommendation",
        "explanation": "Crawler found a technical issue that needs manual review.",
        "why": "Small technical issues can accumulate and reduce crawl quality or clarity.",
        "fix": "Review the affected URL, HTTP response and HTML output, then rerun the audit.",
    }


def severity_for_error(error):
    info = error_intelligence(error)
    return info["severity"].title(), info["class"]


def category_for_error(error):
    return error_intelligence(error)["category"]


def explanation_for_error(error):
    return error_intelligence(error)["explanation"]


def grouped_errors(errors):
    groups = {}

    for error in errors:
        groups.setdefault(category_for_error(error), []).append(error)

    return groups


def build_error_center_items(result):
    items = list(result.get("errors", []))

    for link in result.get("broken_links", []):
        items.append(
            f"Broken link: {link.get('url', '')} returned {link.get('status_code', '')} found on {link.get('found_on', '')}"
        )

    for redirect in result.get("redirect_chains", []):
        chain = redirect.get("chain", [])

        if len(chain) > 1:
            items.append(f"Redirect chain: {redirect.get('url', '')} has {len(chain)} hops")

    for item in result.get("canonical_report", []):
        if item.get("status") == "missing":
            items.append(f"Missing canonical: {item.get('url', '')}")

    for item in result.get("robots_errors", []):
        items.append(f"Robots problem: {item}")

    if "не найден" in str(result.get("sitemap", "")).lower() or "ошибка" in str(result.get("sitemap", "")).lower():
        items.append(f"Sitemap problem: {result.get('sitemap')}")

    return list(dict.fromkeys([item for item in items if str(item).strip()]))


def render_error_card(error, key):
    info = error_intelligence(error)

    st.markdown(
        f"""
        <div class="ts-error-intel-card">
            <div class="ts-error-intel-head">
                <div class="ts-error-intel-title">{escape(str(error))}</div>
                <span class="ts-severity {info["class"]}">{escape(info["severity"])}</span>
            </div>
            <div class="ts-error-grid">
                <div class="ts-error-mini">
                    <div class="ts-error-mini-label">Explanation</div>
                    <div class="ts-error-mini-text">{escape(info["explanation"])}</div>
                </div>
                <div class="ts-error-mini">
                    <div class="ts-error-mini-label">Why it matters</div>
                    <div class="ts-error-mini-text">{escape(info["why"])}</div>
                </div>
                <div class="ts-error-mini">
                    <div class="ts-error-mini-label">How to fix</div>
                    <div class="ts-error-mini-text">{escape(info["fix"])}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.code(
        f"Issue: {error}\nSeverity: {info['severity']}\nWhy it matters: {info['why']}\nHow to fix: {info['fix']}",
        language=None
    )

    if st.button("Copy-ready issue", key=key, use_container_width=False):
        st.toast("Copy-friendly block is ready above.")


def render_error_center(result):
    errors = build_error_center_items(result)

    if not errors:
        empty_state(
            "Центр ошибок чист",
            "No SEO errors were found in the current audit result."
        )
        return

    for category, category_errors in grouped_errors(errors).items():
        st.markdown(f'<div class="ts-error-category">{escape(category)}</div>', unsafe_allow_html=True)

        for index, error in enumerate(category_errors):
            render_error_card(error, key=f"copy_error_{category}_{index}")


def severity_rank(issue):
    return {
        "critical": 0,
        "important": 1,
        "recommendation": 2,
    }.get(issue.get("severity"), 3)


def grouped_assistant_issues(issues):
    groups = {}

    for issue in sorted(issues, key=severity_rank):
        groups.setdefault(issue.get("category", "SEO"), []).append(issue)

    return groups


def issue_copy_text(issue):
    urls = issue.get("affected_urls") or []
    urls_text = "\n".join(f"- {url}" for url in urls[:20]) or "- URL не указан"

    return (
        f"Проблема: {issue.get('title', '')}\n"
        f"Важность: {issue.get('severity_label', '')}\n"
        f"Почему важно: {issue.get('why', '')}\n"
        f"Как исправить: {issue.get('fix', '')}\n"
        f"Затронутые URL:\n{urls_text}"
    )


def render_assistant_issue_card(issue, key):
    urls = issue.get("affected_urls") or []
    urls_html = "".join(f"<li>{escape(str(url))}</li>" for url in urls[:8])
    extra_count = max(0, len(urls) - 8)

    if extra_count:
        urls_html += f"<li>Еще {extra_count} URL</li>"

    if not urls_html:
        urls_html = "<li>URL не указан</li>"

    st.markdown(
        f"""
        <div class="ts-error-intel-card ts-assistant-card">
            <div class="ts-error-intel-head">
                <div>
                    <div class="ts-assistant-eyebrow">SEO-помощник</div>
                    <div class="ts-error-intel-title">{escape(str(issue.get("title", "")))}</div>
                </div>
                <span class="ts-severity {escape(issue.get("severity_class", "ts-severity-recommendation"))}">
                    {escape(str(issue.get("severity_label", "Рекомендация")))}
                </span>
            </div>
            <div class="ts-error-grid">
                <div class="ts-error-mini">
                    <div class="ts-error-mini-label">Почему это важно</div>
                    <div class="ts-error-mini-text">{escape(str(issue.get("why", "")))}</div>
                </div>
                <div class="ts-error-mini">
                    <div class="ts-error-mini-label">Как исправить</div>
                    <div class="ts-error-mini-text">{escape(str(issue.get("fix", "")))}</div>
                </div>
                <div class="ts-error-mini">
                    <div class="ts-error-mini-label">Затронутые URL</div>
                    <ul class="ts-assistant-url-list">{urls_html}</ul>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    with st.expander("Текст для копирования", expanded=False):
        st.code(issue_copy_text(issue), language=None)

    if st.button("Скопировать формулировку", key=key, use_container_width=False):
        st.toast("Текст готов выше: выделите его и скопируйте.")


def render_error_center(result):
    issues = result.get("seo_assistant_issues") or []

    if not issues:
        empty_state(
            "SEO-помощник не нашел критичных проблем",
            "В текущем аудите нет структурированных SEO-ошибок. Можно проверить таблицы meta, canonical и ссылок ниже для ручного контроля."
        )
        return

    critical_count = len([issue for issue in issues if issue.get("severity") == "critical"])
    important_count = len([issue for issue in issues if issue.get("severity") == "important"])
    recommendation_count = len([issue for issue in issues if issue.get("severity") == "recommendation"])

    col1, col2, col3 = st.columns(3)
    with col1:
        metric_card("Критично", critical_count, "Исправить первым", "#dc2626")
    with col2:
        metric_card("Важно", important_count, "Влияет на SEO", "#f59e0b")
    with col3:
        metric_card("Рекомендации", recommendation_count, "Улучшения после основных ошибок", "#16a34a")

    for category, category_issues in grouped_assistant_issues(issues).items():
        st.markdown(f'<div class="ts-error-category">{escape(category)}</div>', unsafe_allow_html=True)

        for index, issue in enumerate(category_issues):
            safe_category = str(category).replace(" ", "_").replace(".", "_")
            render_assistant_issue_card(issue, key=f"copy_assistant_{safe_category}_{index}_{issue.get('id', '')}")


def render_technical_check_card(check):
    st.markdown(
        f"""
        <div class="ts-technical-pro-card">
            <div class="ts-technical-head">
                <div>
                    <div class="ts-card-title">{escape(str(check.get("title", "")))}</div>
                    <div class="ts-card-text">{escape(str(check.get("status", "")))}</div>
                </div>
                <span class="ts-severity {escape(str(check.get("severity_class", "ts-severity-recommendation")))}">
                    {escape(str(check.get("severity_label", "Рекомендация")))}
                </span>
            </div>
            <div class="ts-error-grid">
                <div class="ts-error-mini">
                    <div class="ts-error-mini-label">Что это значит</div>
                    <div class="ts-error-mini-text">{escape(str(check.get("explanation", "")))}</div>
                </div>
                <div class="ts-error-mini">
                    <div class="ts-error-mini-label">Подсказка</div>
                    <div class="ts-error-mini-text">{escape(str(check.get("helper", "")))}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_sitemap_pro(result):
    analysis = result.get("sitemap_analysis") or {}
    sitemap_url = analysis.get("url") or result.get("sitemap_url", "")
    broken_urls = analysis.get("broken_urls") or []
    lastmod_values = analysis.get("lastmod_values") or []

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Sitemap", "Найден" if analysis.get("found") else "Не найден", sitemap_url or "URL не указан", "#2563eb")
    with col2:
        metric_card("Status code", analysis.get("status_code", "—"), "Ответ сервера", "#0f766e")
    with col3:
        metric_card("XML valid", "Да" if analysis.get("xml_valid") else "Нет", "Можно читать поисковику", "#16a34a" if analysis.get("xml_valid") else "#dc2626")
    with col4:
        metric_card("URL в sitemap", analysis.get("urls_count", 0), "Найдено адресов", "#7c3aed")

    if sitemap_url:
        st.link_button("Открыть sitemap.xml", sitemap_url, use_container_width=True)

    for check in analysis.get("checks", []):
        render_technical_check_card(check)

    col_a, col_b = st.columns(2)
    with col_a:
        kv_card(
            "Lastmod",
            [
                ("Статус", analysis.get("lastmod", "—")),
                ("Примеры", ", ".join(lastmod_values[:3]) if lastmod_values else "Не найдено"),
                ("Тип sitemap", analysis.get("type", "—")),
            ]
        )
    with col_b:
        kv_card(
            "Broken URLs",
            [
                ("Количество", len(broken_urls)),
                ("Что делать", "Удалить из sitemap или восстановить страницы" if broken_urls else "Проблем не найдено"),
            ]
        )

    if broken_urls:
        st.dataframe(
            pd.DataFrame([
                {
                    "URL": item.get("url", ""),
                    "Status": item.get("status_code", ""),
                    "Found on": item.get("found_on", ""),
                }
                for item in broken_urls
            ]),
            width="stretch",
            hide_index=True,
            height=220
        )


def render_robots_pro(result):
    analysis = result.get("robots_analysis") or {}
    robots_url = analysis.get("url") or result.get("robots_url", "")
    blocked_sections = analysis.get("blocked_important_sections") or []

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Robots.txt", "Найден" if analysis.get("found") else "Не найден", robots_url or "URL не указан", "#2563eb")
    with col2:
        metric_card("Status code", analysis.get("status_code", "—"), "Ответ сервера", "#0f766e")
    with col3:
        metric_card("User-agent", "Есть" if analysis.get("has_user_agent") else "Нет", "Правила для роботов", "#16a34a" if analysis.get("has_user_agent") else "#f59e0b")
    with col4:
        metric_card("Sitemap directive", "Есть" if analysis.get("has_sitemap") else "Нет", "Ссылка на sitemap", "#16a34a" if analysis.get("has_sitemap") else "#f59e0b")

    if robots_url:
        st.link_button("Открыть robots.txt", robots_url, use_container_width=True)

    for check in analysis.get("checks", []):
        render_technical_check_card(check)

    if blocked_sections:
        st.warning("Найдены правила, которые могут закрывать важные разделы: " + ", ".join(blocked_sections))

    st.markdown('<div class="ts-section-subtitle">Содержимое robots.txt</div>', unsafe_allow_html=True)
    content = analysis.get("content") or result.get("robots_content") or "robots.txt не найден или пустой"
    st.markdown(
        f'<div class="ts-technical-content">{escape(content)}</div>',
        unsafe_allow_html=True
    )


def meta_table(result, url):
    meta_audit = result.get("meta_audit") or {}
    rows = meta_audit.get("rows") or []
    summary = meta_audit.get("summary") or {}

    if not rows:
        pages_meta = result.get("pages_meta", [])
        if pages_meta:
            rows = [
                {
                    "url": item.get("url", ""),
                    "title": item.get("title", ""),
                    "title_length": len(item.get("title", "") or ""),
                    "description": item.get("description", ""),
                    "description_length": len(item.get("description", "") or ""),
                    "h1": item.get("h1", item.get("h1_count", "")),
                    "h1_count": item.get("h1_count", 0),
                    "issues": [],
                    "issues_count": 0,
                    "max_severity": "ok",
                }
                for item in pages_meta
            ]

    if not rows:
        empty_state(
            "Meta Audit PRO пока без данных",
            "Запустите новый ежемесячный аудит с полным обходом, чтобы увидеть Title, Description, H1 и список проблем по каждой странице."
        )
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Страниц", summary.get("pages_total", len(rows)), "В meta-аудите", "#2563eb")
    with col2:
        metric_card("С проблемами", summary.get("pages_with_issues", 0), "Нужно проверить", "#f59e0b")
    with col3:
        metric_card("Критично", summary.get("critical", 0), "Исправить первым", "#dc2626")
    with col4:
        total_meta_issues = (
            int(summary.get("title_issues", 0) or 0)
            + int(summary.get("description_issues", 0) or 0)
            + int(summary.get("h1_issues", 0) or 0)
        )
        metric_card("Проблем meta", total_meta_issues, "Title, Description, H1", "#7c3aed")

    filter_col1, filter_col2, filter_col3 = st.columns([1.2, 1, 1])
    with filter_col1:
        query = st.text_input("Поиск по URL, Title, Description или H1", key="meta_audit_search")
    with filter_col2:
        severity_filter = st.selectbox(
            "Важность",
            ["Все", "Критично", "Предупреждение", "Рекомендация", "Без проблем"],
            key="meta_audit_severity"
        )
    with filter_col3:
        field_filter = st.selectbox(
            "Поле",
            ["Все", "Title", "Description", "H1"],
            key="meta_audit_field"
        )

    def row_matches(row):
        searchable = " ".join([
            str(row.get("url", "")),
            str(row.get("title", "")),
            str(row.get("description", "")),
            str(row.get("h1", "")),
        ]).lower()

        if query and query.lower() not in searchable:
            return False

        issues = row.get("issues") or []

        if severity_filter != "Все":
            severity_map = {
                "Критично": "critical",
                "Предупреждение": "warning",
                "Рекомендация": "recommendation",
                "Без проблем": "ok",
            }
            expected = severity_map[severity_filter]
            if expected == "ok" and issues:
                return False
            if expected != "ok" and not any(issue.get("severity") == expected for issue in issues):
                return False

        if field_filter != "Все" and not any(issue.get("field") == field_filter for issue in issues):
            return False

        return True

    filtered_rows = [row for row in rows if row_matches(row)]

    if not filtered_rows:
        empty_state(
            "По фильтрам ничего не найдено",
            "Попробуйте изменить поиск, важность или поле проверки."
        )
        return

    table_rows = []
    for row in filtered_rows:
        issue_titles = [issue.get("title", "") for issue in row.get("issues", [])]
        table_rows.append({
            "URL": row.get("url", ""),
            "Title": row.get("title", ""),
            "Title length": row.get("title_length", 0),
            "Description": row.get("description", ""),
            "Description length": row.get("description_length", 0),
            "H1": row.get("h1", ""),
            "H1 count": row.get("h1_count", 0),
            "Проблемы": ", ".join(issue_titles) if issue_titles else "Без проблем",
        })

    st.dataframe(pd.DataFrame(table_rows), width="stretch", hide_index=True, height=320)

    st.markdown('<div class="ts-section-subtitle">Карточки страниц с подсветкой проблем</div>', unsafe_allow_html=True)

    for index, row in enumerate(filtered_rows[:20]):
        issues = row.get("issues") or []
        chips = "".join(
            f'<span class="ts-severity {escape(issue.get("severity_class", "ts-severity-recommendation"))}">{escape(issue.get("title", ""))}</span>'
            for issue in issues
        ) or '<span class="ts-meta-issue-chip">Без проблем</span>'
        explanations = "".join(
            f'<div class="ts-card-text">• {escape(issue.get("explanation", ""))}</div>'
            for issue in issues[:4]
        )

        st.markdown(
            f"""
            <div class="ts-meta-pro-card">
                <div class="ts-meta-pro-url">{escape(row.get("url", ""))}</div>
                <div class="ts-meta-pro-grid">
                    <div class="ts-meta-pro-field">
                        <div class="ts-meta-pro-label">Title · {escape(str(row.get("title_length", 0)))} символов</div>
                        <div class="ts-meta-pro-text">{escape(row.get("title", "") or "Title отсутствует")}</div>
                    </div>
                    <div class="ts-meta-pro-field">
                        <div class="ts-meta-pro-label">Description · {escape(str(row.get("description_length", 0)))} символов</div>
                        <div class="ts-meta-pro-text">{escape(row.get("description", "") or "Description отсутствует")}</div>
                    </div>
                    <div class="ts-meta-pro-field">
                        <div class="ts-meta-pro-label">H1 · {escape(str(row.get("h1_count", 0)))} шт.</div>
                        <div class="ts-meta-pro-text">{escape(row.get("h1", "") or "H1 отсутствует")}</div>
                    </div>
                </div>
                <div class="ts-meta-issue-row">{chips}</div>
                <div style="margin-top:10px;">{explanations}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

        copy_text = (
            f"URL: {row.get('url', '')}\n"
            f"Title: {row.get('title', '')}\n"
            f"Description: {row.get('description', '')}\n"
            f"H1: {row.get('h1', '')}\n"
            f"Проблемы: {', '.join(issue.get('title', '') for issue in issues) if issues else 'Без проблем'}"
        )

        with st.expander(f"Текст для копирования · страница {index + 1}", expanded=False):
            st.code(copy_text, language=None)


def canonical_table(result):
    analysis = result.get("canonical_analysis") or {}
    rows = analysis.get("rows") or []
    summary = analysis.get("summary") or {}

    if not rows:
        empty_state(
            "Canonical Analyzer PRO пока без данных",
            "Запустите новый аудит с полным обходом, чтобы проверить canonical по страницам."
        )
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Страниц", summary.get("total", len(rows)), "Проверено canonical", "#2563eb")
    with col2:
        metric_card("Self canonical", summary.get("self", 0), "Корректный сигнал", "#16a34a")
    with col3:
        metric_card("Проблем", summary.get("missing", 0) + summary.get("broken", 0) + summary.get("loops", 0) + summary.get("external", 0), "Нужно проверить", "#dc2626")
    with col4:
        metric_card("На главную", summary.get("home", 0), "Проверьте логику", "#f59e0b")

    table_rows = [
        {
            "Source page": row.get("source_page", ""),
            "Canonical target": row.get("canonical_target", ""),
            "Status": row.get("status", ""),
            "Issues": ", ".join(issue.get("title", "") for issue in row.get("issues", [])) or "Без проблем",
        }
        for row in rows
    ]
    st.dataframe(pd.DataFrame(table_rows), width="stretch", hide_index=True, height=260)

    for index, row in enumerate(rows[:20]):
        issues = row.get("issues") or []
        chips = "".join(
            f'<span class="ts-severity {escape(issue.get("severity_class", "ts-severity-recommendation"))}">{escape(issue.get("title", ""))}</span>'
            for issue in issues
        ) or '<span class="ts-meta-issue-chip">Без проблем</span>'
        why = "".join(
            f'<div class="ts-card-text">• {escape(issue.get("why", ""))}</div>'
            for issue in issues[:3]
        )
        fix = "".join(
            f'<div class="ts-card-text">• {escape(issue.get("fix", ""))}</div>'
            for issue in issues[:3]
        )

        st.markdown(
            f"""
            <div class="ts-technical-pro-card">
                <div class="ts-technical-head">
                    <div>
                        <div class="ts-card-title">Canonical</div>
                        <div class="ts-card-text">Source: {escape(row.get("source_page", ""))}</div>
                        <div class="ts-card-text">Target: {escape(row.get("canonical_target", "") or "не найден")}</div>
                    </div>
                    <div class="ts-meta-issue-row">{chips}</div>
                </div>
                <div class="ts-error-grid">
                    <div class="ts-error-mini">
                        <div class="ts-error-mini-label">Почему это важно</div>
                        <div class="ts-error-mini-text">{why or "Canonical выглядит корректно для этой страницы."}</div>
                    </div>
                    <div class="ts-error-mini">
                        <div class="ts-error-mini-label">Как исправить</div>
                        <div class="ts-error-mini-text">{fix or "Дополнительных действий не требуется."}</div>
                    </div>
                    <div class="ts-error-mini">
                        <div class="ts-error-mini-label">Статус</div>
                        <div class="ts-error-mini-text">{escape(row.get("status", ""))}</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


def broken_links_table(result):
    broken_links = result.get("broken_links", [])

    if not broken_links:
        empty_state(
            "Битые ссылки не найдены",
            "Полный обход не нашел недоступных внутренних ссылок в текущем аудите."
        )
        return

    rows = [
        {
            "URL": item.get("url", ""),
            "Status": item.get("status_code", ""),
            "Found on": item.get("found_on", ""),
        }
        for item in broken_links
    ]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True, height=260)


def render_redirect_chains(result):
    analysis = result.get("redirect_analysis") or {}
    rows = analysis.get("rows") or []
    summary = analysis.get("summary") or {}

    if not rows:
        empty_state(
            "Redirect Analyzer PRO не нашел цепочек",
            "В текущем аудите нет заметных redirect chains. Это хороший знак для скорости и понятности обхода."
        )
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Цепочек", summary.get("total", len(rows)), "Найдено", "#2563eb")
    with col2:
        metric_card("Петли", summary.get("loops", 0), "Критично", "#dc2626")
    with col3:
        metric_card("302/временные", summary.get("temporary", 0), "Проверить", "#f59e0b")
    with col4:
        metric_card("Смешанные", summary.get("mixed", 0), "301 + 302", "#7c3aed")

    table_rows = [
        {
            "Source URL": row.get("source_url", ""),
            "Destination URL": row.get("destination_url", ""),
            "Redirect type": row.get("redirect_type", ""),
            "Chain length": row.get("chain_length", 0),
            "Issues": ", ".join(issue.get("title", "") for issue in row.get("issues", [])) or "Без проблем",
        }
        for row in rows
    ]
    st.dataframe(pd.DataFrame(table_rows), width="stretch", hide_index=True, height=260)

    for row in rows[:20]:
        issues = row.get("issues") or []
        chips = "".join(
            f'<span class="ts-severity {escape(issue.get("severity_class", "ts-severity-recommendation"))}">{escape(issue.get("title", ""))}</span>'
            for issue in issues
        ) or '<span class="ts-meta-issue-chip">Без проблем</span>'
        chain_rows = []

        for hop in row.get("chain", []):
            location = hop.get("location") or "финальный URL"
            chain_rows.append(
                f"""
                <div class="ts-chain-hop">
                    <span>{escape(str(hop.get("url", "")))}</span>
                    <span class="ts-chain-arrow">{escape(str(hop.get("status", "")))}</span>
                    <span>{escape(str(location))}</span>
                </div>
                """
            )

        explanations = "".join(
            f'<div class="ts-card-text">• {escape(issue.get("why", ""))} {escape(issue.get("helper", ""))}</div>'
            for issue in issues[:3]
        )

        st.markdown(
            f"""
            <div class="ts-technical-pro-card">
                <div class="ts-technical-head">
                    <div>
                        <div class="ts-card-title">Redirect chain · {escape(str(row.get("redirect_type", "")))}</div>
                        <div class="ts-card-text">Source: {escape(row.get("source_url", ""))}</div>
                        <div class="ts-card-text">Destination: {escape(row.get("destination_url", ""))}</div>
                    </div>
                    <div class="ts-meta-issue-row">{chips}</div>
                </div>
                <div class="ts-site-grid">
                    <div class="ts-site-stat">
                        <div class="ts-site-stat-label">Chain length</div>
                        <div class="ts-site-stat-value">{escape(str(row.get("chain_length", 0)))}</div>
                    </div>
                    <div class="ts-site-stat">
                        <div class="ts-site-stat-label">Temporary</div>
                        <div class="ts-site-stat-value">{escape("Да" if row.get("has_temporary") else "Нет")}</div>
                    </div>
                    <div class="ts-site-stat">
                        <div class="ts-site-stat-label">Mixed chain</div>
                        <div class="ts-site-stat-value">{escape("Да" if row.get("has_mixed") else "Нет")}</div>
                    </div>
                    <div class="ts-site-stat">
                        <div class="ts-site-stat-label">Loop</div>
                        <div class="ts-site-stat-value">{escape("Да" if row.get("has_loop") else "Нет")}</div>
                    </div>
                </div>
                <div class="ts-chain-list">{''.join(chain_rows)}</div>
                <div style="margin-top:10px;">{explanations}</div>
            </div>
            """,
            unsafe_allow_html=True
        )


def reviews_sources(yandex_reviews_url, google_reviews_url, twogis_reviews_url):
    rows = [
        ("Яндекс.Карты", yandex_reviews_url or "Не подключено"),
        ("Google Maps", google_reviews_url or "Не подключено"),
        ("2ГИС", twogis_reviews_url or "Не подключено"),
    ]
    kv_card("Источники отзывов", rows)


def render_audit_sections(url, result, score, errors_count, yandex_reviews_url, google_reviews_url, twogis_reviews_url):
    ai_summary = generate_ai_summary(score, errors_count)

    section_header("Сводка аудита", "Короткое объяснение результата и рекомендации по текущему аудиту.")
    col1, col2 = st.columns(2)

    with col1:
        metric_card("Ошибок", errors_count, "Найдено crawler", "#dc2626")
    with col2:
        metric_card("Статус", ai_summary["risk"], "Итоговая оценка", "#f59e0b")

    st.info(ai_summary["summary"])
    warnings_block(result.get("crawler_warnings", []))

    recommendations_key = f"monthly_ai_recommendations_{url}_{score}_{errors_count}"
    recommendations = st.session_state.get(recommendations_key)

    if st.button("Получить рекомендации YandexGPT", key=f"{recommendations_key}_button", use_container_width=True):
        with st.spinner("Готовим рекомендации через YandexGPT..."):
            recommendations = generate_ai_recommendations(result)
            st.session_state[recommendations_key] = recommendations

    if recommendations:
        with st.expander("Рекомендации нейросети", expanded=False):
            for recommendation in recommendations:
                recommendation_card(recommendation)

    section_header("Разделы аудита", "Детальные зоны проверки сгруппированы по SEO-модулям.")

    audit_sections = [
        "Обзор",
        "Sitemap / Robots",
        "Meta / Canonical",
        "Ссылки / Редиректы / Отзывы",
        "Центр ошибок",
    ]
    selected_section = st.radio(
        "Раздел аудита",
        audit_sections,
        horizontal=True,
        label_visibility="collapsed",
    )

    if selected_section == audit_sections[0]:
        section_header("Сводка полного обхода", "Метрики обхода сайта из последнего аудита.")
        render_full_crawl_summary(result)

        col_a, col_b = st.columns(2)

        with col_a:
            kv_card(
                "Sitemap.xml",
                [
                    ("Status", result.get("sitemap", "Не проверено")),
                    ("XML", result.get("sitemap_valid", "—")),
                    ("Type", result.get("sitemap_type", "—")),
                    ("URLs", result.get("sitemap_urls_count", 0)),
                ]
            )

        with col_b:
            kv_card(
                "Robots.txt",
                [
                    ("Status", result.get("robots_txt", "Не проверено")),
                    ("Errors", len(result.get("robots_errors", []))),
                    ("Sitemap directive", "Есть" if "sitemap:" in result.get("robots_content", "").lower() else "Не найдено"),
                    ("User-agent", "Есть" if "user-agent" in result.get("robots_content", "").lower() else "Не найдено"),
                ]
            )

        col_c, col_d = st.columns(2)

        with col_c:
            kv_card(
                "Pagination",
                [
                    ("Status", result.get("pagination_status", "Не проверено")),
                    ("Pages", result.get("pagination_pages_count", 0)),
                    ("Errors", len(result.get("pagination_errors", []))),
                ]
            )

        with col_d:
            kv_card(
                "Broken Links",
                [
                    ("Checked internal links", result.get("internal_links_total", 0)),
                    ("Битые ссылки", result.get("broken_links_total", 0)),
                    ("Links on page", result.get("links_total", 0)),
                ]
            )

    elif selected_section == audit_sections[1]:
        section_header("Sitemap.xml PRO", "Проверяем, доступна ли карта сайта, корректен ли XML и нет ли в ней проблемных URL.")
        render_sitemap_pro(result)

        section_header("Robots.txt PRO", "Проверяем правила обхода сайта: User-agent, Sitemap directive, полную блокировку и важные закрытые разделы.")
        render_robots_pro(result)

    elif selected_section == audit_sections[2]:
        section_header("SEO Meta Audit PRO", "Полная проверка Title, Description и H1 по каждой странице: длина, дубли, отсутствие и понятные рекомендации.")
        meta_table(result, url)

        col_a, col_b = st.columns(2)

        with col_a:
            section_header("Canonical Analyzer PRO", "Проверяем self canonical, canonical на другой URL, главную, внешний домен, петли и недоступные цели.")
            canonical_table(result)

        with col_b:
            kv_card(
                "Pagination",
                [
                    ("Status", result.get("pagination_status", "Не проверено")),
                    ("Pages", result.get("pagination_pages_count", 0)),
                    ("Errors", len(result.get("pagination_errors", []))),
                ]
            )

    elif selected_section == audit_sections[3]:
        section_header("Broken Links", "Таблица URL, HTTP status и страница-источник.")
        broken_links_table(result)

        section_header("Redirect Analyzer PRO", "Проверяем source, destination, тип редиректа, длину цепочки, петли, временные и смешанные редиректы.")
        render_redirect_chains(result)

        section_header("Reviews", "Подготовка к review monitoring без изменения crawler logic.")
        reviews_sources(yandex_reviews_url, google_reviews_url, twogis_reviews_url)

    elif selected_section == audit_sections[4]:
        section_header("SEO-помощник", "Понятные рекомендации для владельца бизнеса: что случилось, почему это важно и как исправить.")
        render_error_center(result)


def monthly_status_label(status):
    return {
        "queued": "В очереди",
        "running": "Выполняется",
        "completed": "Завершён",
        "error": "Ошибка",
    }.get(status or "", "Готов к запуску")


def render_monthly_job_status(job):
    if not job:
        st.progress(0)
        st.caption("Аудит еще не запускался.")
        return

    progress = int(job.get("progress") or 0)
    status_label = monthly_status_label(job.get("status"))

    st.progress(progress)

    cols = st.columns(3)
    with cols[0]:
        metric_card("Статус", status_label, "Фоновый аудит", "#f59e0b")
    with cols[1]:
        metric_card("Прогресс", f"{progress}%", "Можно уйти со страницы", "#2563eb")
    with cols[2]:
        metric_card("Время запуска", job.get("created_at") or "—", "Сохранено в sqlite", "#7c3aed")

    if job.get("status") == "error":
        st.error(job.get("error_message") or "Аудит завершился с ошибкой.")
    elif job.get("status") in ("queued", "running"):
        st.info("Аудит выполняется в фоне. Можно открыть другой раздел и вернуться позже: статус сохранится.")


def show_monthly_audit_page():
    user_id = require_user_id()
    selected_site = select_site_from_db("Выберите сайт для аудита")

    if not selected_site:
        st.info("Выберите сайт, чтобы загрузить последний аудит и тяжелые таблицы результатов.")
        return

    site_id = selected_site[0]
    url = selected_site[2]
    site_name = selected_site[1]
    yandex_reviews_url = selected_site[5]
    google_reviews_url = selected_site[6]
    twogis_reviews_url = selected_site[7]

    latest_job = get_latest_monthly_audit_job(user_id=user_id, site_url=url)
    audit_data = latest_job.get("result") if latest_job else None
    score = latest_job.get("seo_score") if latest_job and latest_job.get("seo_score") is not None else 0
    audit_date = latest_job.get("created_at") if latest_job else "Аудит еще не запускался"
    audit_status = monthly_status_label(latest_job.get("status") if latest_job else None)

    st.markdown(
        f"""
        <div class="ts-audit-header">
            <div>
                <div class="ts-saas-hero-title">Ежемесячный аудит</div>
                <div class="ts-saas-hero-subtitle">
                    Выбранный сайт: <strong>{escape(site_name)}</strong><br>
                    {escape(url)}
                </div>
            </div>
            <div class="ts-saas-pill">{escape(audit_status)}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    date_part, time_part = (str(audit_date).split(" ", 1) + ["—"])[:2] if audit_date != "Аудит еще не запускался" else ("—", "—")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        metric_card("Сайт", site_name, url, "#0f766e")
    with col2:
        metric_card("Дата", date_part, "Последний запуск", "#2563eb")
    with col3:
        metric_card("Время", time_part, "Последний запуск", "#7c3aed")
    with col4:
        metric_card("Статус", audit_status, "Фоновый аудит", "#f59e0b")

    st.markdown(
        """
        <div class="ts-audit-launch">
            <div class="ts-audit-section-title">Запуск аудита</div>
            <div class="ts-card-text">
                Аудит запускается в фоне через Celery. Страницу можно закрыть или открыть другой раздел:
                прогресс и результат сохраняются в sqlite.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    is_running = latest_job and latest_job.get("status") in ("queued", "running")
    button_label = "Аудит уже выполняется" if is_running else "Запустить аудит"

    if st.button(button_label, type="primary", use_container_width=True, disabled=bool(is_running)):
        try:
            latest_job = enqueue_monthly_audit(url=url, user_id=user_id, site_id=site_id)
            clear_cached_data()
            st.success("Аудит поставлен в очередь. Можно продолжать работать с платформой.")
            st.rerun()
        except Exception as exc:
            st.error(f"Не удалось поставить аудит в очередь Celery: {exc}")

    render_monthly_job_status(latest_job)

    if latest_job and latest_job.get("status") in ("queued", "running"):
        time.sleep(15)
        st.rerun()

    if not audit_data:
        st.markdown(
            """
            <div class="ts-empty-state">
                <div class="ts-card-title">🌸 Аудит пока не запускался</div>
                <div class="ts-card-text">
                    Нажмите «Запустить аудит», и проверка уйдет в фон. Когда задача завершится,
                    здесь появятся SEO-сводка, sitemap.xml, robots.txt, meta-теги, битые ссылки,
                    редиректы и центр ошибок.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        return

    result = audit_data["result"]

    render_audit_sections(
        url=url,
        result=result,
        score=audit_data["score"],
        errors_count=audit_data["errors_count"],
        yandex_reviews_url=yandex_reviews_url,
        google_reviews_url=google_reviews_url,
        twogis_reviews_url=twogis_reviews_url
    )
