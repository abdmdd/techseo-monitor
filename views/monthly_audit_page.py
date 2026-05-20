from datetime import datetime
from html import escape

import pandas as pd
import streamlit as st

from components.ui_helpers import metric_card, recommendation_card, risk_card, warnings_block
from database.db import get_sites
from services.ai_service import generate_ai_recommendations, generate_ai_summary
from services.audit_service import run_monthly_audit
from services.history_service import save_audit_history
from services.score_service import get_score_risk
from views.auth_page import require_user_id


def select_site_from_db(label):
    sites = get_sites(user_id=require_user_id())

    if sites:
        site_options = {
            f"{site[1]} - {site[2]}": site
            for site in sites
        }

        selected_site_label = st.selectbox(label, list(site_options.keys()))
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


def average_image_alt_coverage(crawled_pages):
    if not crawled_pages:
        return "—"

    values = [
        float(page.get("image_alt_coverage", 100))
        for page in crawled_pages
        if page.get("image_alt_coverage") is not None
    ]

    if not values:
        return "—"

    return f"{round(sum(values) / len(values), 1)}%"


def render_full_crawl_summary(result):
    full_crawl = result.get("full_crawl", {})
    crawled_pages = result.get("crawled_pages", [])
    redirects = result.get("redirect_chains", [])

    if not full_crawl.get("enabled") and not crawled_pages:
        empty_state(
            "Full crawl data is not available",
            "Run a new monthly audit to collect crawled pages, internal links, redirects and canonical reports."
        )
        return

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        metric_card("Pages crawled", result.get("crawled_pages_count", len(crawled_pages)), "Full crawl", "#2563eb")
    with col2:
        metric_card("Internal links", result.get("internal_links_total", 0), "Found across pages", "#0f766e")
    with col3:
        metric_card("Broken links", result.get("broken_links_total", 0), "HTTP/errors", "#dc2626")
    with col4:
        metric_card("Redirects", len(redirects), "Chains found", "#f59e0b")
    with col5:
        metric_card("Alt coverage", average_image_alt_coverage(crawled_pages), "Images", "#7c3aed")

    kv_card(
        "Full crawl runtime",
        [
            ("Start URL", full_crawl.get("start_url", "—")),
            ("Base URL", full_crawl.get("base_url", "—")),
            ("Max pages", full_crawl.get("max_pages", "—")),
            ("Visited URLs", full_crawl.get("visited_urls_count", "—")),
            ("Queue remaining", full_crawl.get("queued_urls_remaining", "—")),
        ]
    )


def error_intelligence(error):
    text = str(error).lower()

    rules = [
        {
            "markers": ["broken links", "битых ссыл", "404", "missing"],
            "category": "Broken Links",
            "severity": "critical",
            "class": "ts-severity-critical",
            "explanation": "Crawler found an internal URL that returns an error or cannot be reached.",
            "why": "Broken links waste crawl budget, create poor user paths and can weaken internal linking signals.",
            "fix": "Update the link target, restore the missing page, or add a relevant 301 redirect.",
        },
        {
            "markers": ["missing title", "отсутствует title", "нет title"],
            "category": "Meta Tags",
            "severity": "critical",
            "class": "ts-severity-critical",
            "explanation": "The page does not expose a usable title tag.",
            "why": "Title is one of the strongest page-level relevance and SERP snippet signals.",
            "fix": "Add a unique 50-70 character title that describes the page intent.",
        },
        {
            "markers": ["missing description", "отсутствует description", "нет description"],
            "category": "Meta Tags",
            "severity": "important",
            "class": "ts-severity-important",
            "explanation": "The page does not expose a usable meta description.",
            "why": "Description helps shape the search snippet and improves scanability in audit workflows.",
            "fix": "Add a unique 120-160 character description with the main value of the page.",
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
            "markers": ["images without alt", "изображений без alt", "alt"],
            "category": "Images",
            "severity": "recommendation",
            "class": "ts-severity-recommendation",
            "explanation": "Some images do not have alternative text.",
            "why": "Alt text improves accessibility and gives crawlers additional context for visual content.",
            "fix": "Add concise, descriptive alt text to meaningful images; leave decorative images empty intentionally.",
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

    for page in result.get("crawled_pages", []):
        coverage = page.get("image_alt_coverage")

        if coverage is not None and coverage < 100:
            items.append(f"Low image alt coverage: {page.get('url', '')} has {coverage}% alt coverage")

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
            "Error Center is clean",
            "No SEO errors were found in the current audit result."
        )
        return

    for category, category_errors in grouped_errors(errors).items():
        st.markdown(f'<div class="ts-error-category">{escape(category)}</div>', unsafe_allow_html=True)

        for index, error in enumerate(category_errors):
            render_error_card(error, key=f"copy_error_{category}_{index}")


def meta_table(result, url):
    pages_meta = result.get("pages_meta", [])

    if not pages_meta:
        empty_state(
            "Meta Tags data is not available",
            "Run a new monthly audit to fill the full crawl meta table."
        )
        return

    rows = [
        {
            "URL": item.get("url", ""),
            "Title": item.get("title", ""),
            "Description": item.get("description", ""),
            "H1": item.get("h1", item.get("h1_count", "")),
        }
        for item in pages_meta
    ]

    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True, height=220)


def canonical_table(result):
    canonical_report = result.get("canonical_report", [])

    if not canonical_report:
        empty_state(
            "Canonical report is not available",
            "Run a new monthly audit to collect canonical status for crawled pages."
        )
        return

    rows = [
        {
            "URL": item.get("url", ""),
            "Canonical": item.get("canonical", ""),
            "Status": item.get("status", ""),
        }
        for item in canonical_report
    ]

    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True, height=260)


def broken_links_table(result):
    broken_links = result.get("broken_links", [])

    if not broken_links:
        empty_state(
            "Broken links are not found",
            "Full crawl did not find unavailable internal URLs in the current audit."
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
    redirects = result.get("redirect_chains") or result.get("homepage_redirects", [])

    if not redirects:
        empty_state(
            "Redirect chains are not available",
            "Full crawl did not detect redirect chains in the current audit."
        )
        return

    for item in redirects:
        chain = item.get("chain", [])
        chain_rows = []

        for hop in chain:
            location = hop.get("location") or "final"
            chain_rows.append(
                f"""
                <div class="ts-chain-row">
                    <span>{escape(str(hop.get("url", "")))}</span>
                    <span class="ts-chain-arrow">→ {escape(str(hop.get("status", "")))}</span>
                    <span>{escape(str(location))}</span>
                </div>
                """
            )

        st.markdown(
            f"""
            <div class="ts-redirect-chain">
                <div class="ts-audit-section-title">{escape(str(item.get("url", "")))}</div>
                {''.join(chain_rows)}
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
    kv_card("Reviews sources", rows)


def render_audit_sections(url, result, score, errors_count, yandex_reviews_url, google_reviews_url, twogis_reviews_url):
    ai_summary = generate_ai_summary(score, errors_count)
    score_risk = get_score_risk(score)

    section_header("SEO Summary", "Общая оценка, риск и AI-рекомендации по текущему аудиту.")
    col1, col2, col3 = st.columns(3)

    with col1:
        metric_card("SEO Score", f"{score}/100", "Единая оценка аудита", "#2563eb")
    with col2:
        metric_card("Ошибок", errors_count, "Найдено crawler", "#dc2626")
    with col3:
        risk_card(score, ai_summary["risk"], score_risk["color"])

    st.info(ai_summary["summary"])
    warnings_block(result.get("crawler_warnings", []))

    recommendations = generate_ai_recommendations(result)

    if recommendations:
        with st.expander("AI recommendations", expanded=False):
            for recommendation in recommendations:
                recommendation_card(recommendation)

    section_header("Audit Sections", "Детальные зоны аудита сгруппированы по SEO-модулям.")

    tab_summary, tab_index, tab_meta, tab_links, tab_errors = st.tabs([
        "Overview",
        "Sitemap / Robots",
        "Meta / Canonical",
        "Links / Redirects / Reviews",
        "Error Center",
    ])

    with tab_summary:
        section_header("Full crawl summary", "Real recursive crawl metrics from the latest audit result.")
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
                    ("Broken links", result.get("broken_links_total", 0)),
                    ("Links on page", result.get("links_total", 0)),
                ]
            )

    with tab_index:
        col_a, col_b = st.columns(2)

        with col_a:
            kv_card(
                "Sitemap.xml",
                [
                    ("Status", result.get("sitemap", "Не проверено")),
                    ("Valid XML", result.get("sitemap_valid", "—")),
                    ("Type", result.get("sitemap_type", "—")),
                    ("Lastmod", result.get("sitemap_lastmod", "—")),
                    ("Empty", result.get("sitemap_empty", "—")),
                    ("URLs", result.get("sitemap_urls_count", 0)),
                ]
            )

        with col_b:
            kv_card(
                "Robots.txt",
                [
                    ("Status", result.get("robots_txt", "Не проверено")),
                    ("Errors", len(result.get("robots_errors", []))),
                    ("Content length", len(result.get("robots_content", ""))),
                ]
            )

            if result.get("robots_errors"):
                st.warning("Robots issues")
                for error in result.get("robots_errors", []):
                    st.write(f"- {error}")

    with tab_meta:
        section_header("Meta Tags", "Красивая таблица URL, Title, Description и H1.")
        meta_table(result, url)

        col_a, col_b = st.columns(2)

        with col_a:
            section_header("Canonical report", "Canonical status for every crawled page.")
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

    with tab_links:
        section_header("Broken Links", "Таблица URL, HTTP status и страница-источник.")
        broken_links_table(result)

        section_header("Redirects", "Наглядные redirect chains для homepage-вариантов.")
        render_redirect_chains(result)

        section_header("Reviews", "Подготовка к review monitoring без изменения crawler logic.")
        reviews_sources(yandex_reviews_url, google_reviews_url, twogis_reviews_url)

    with tab_errors:
        section_header("Error Center", "Ошибки сгруппированы по категориям и severity.")
        render_error_center(result)


def show_monthly_audit_page():
    if "monthly_audit_data" not in st.session_state:
        st.session_state.monthly_audit_data = None

    if "monthly_audit_date" not in st.session_state:
        st.session_state.monthly_audit_date = None

    if "monthly_audit_status" not in st.session_state:
        st.session_state.monthly_audit_status = "Готов к запуску"

    selected_site = select_site_from_db("Выберите сайт для аудита")

    url = selected_site[2]
    site_name = selected_site[1]
    yandex_reviews_url = selected_site[5]
    google_reviews_url = selected_site[6]
    twogis_reviews_url = selected_site[7]

    audit_data = st.session_state.monthly_audit_data
    score = audit_data.get("score", 0) if audit_data else 0
    audit_date = st.session_state.monthly_audit_date or "Аудит еще не запускался"
    audit_status = st.session_state.monthly_audit_status

    st.markdown(
        f"""
        <div class="ts-audit-header">
            <div>
                <div class="ts-saas-hero-title">Monthly SEO Audit Center</div>
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

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        metric_card("Выбранный сайт", site_name, url, "#0f766e")
    with col2:
        metric_card("SEO Score", f"{score}/100", "Текущий результат", "#2563eb")
    with col3:
        metric_card("Дата аудита", audit_date, "Последний запуск", "#7c3aed")
    with col4:
        metric_card("Статус", audit_status, "Monthly audit", "#f59e0b")

    st.markdown(
        """
        <div class="ts-audit-launch">
            <div class="ts-audit-section-title">Запуск аудита</div>
            <div class="ts-card-text">Crawler проверит технические SEO-сигналы и сохранит результат в историю.</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if st.button("Запустить ежемесячный SEO audit", type="primary", use_container_width=True):
        progress = st.progress(0)

        with st.status("Подготовка audit center", expanded=True) as status:
            st.session_state.monthly_audit_status = "Выполняется"
            st.write("Готовим crawler и проверяем выбранный сайт.")
            progress.progress(15)
            st.write("Собираем Sitemap.xml, Robots.txt, Meta Tags, Canonical, Links и Redirects.")
            progress.progress(35)

            audit_data = run_monthly_audit(url)
            progress.progress(85)

            result = audit_data["result"]
            score = audit_data["score"]
            errors_count = audit_data["errors_count"]

            save_audit_history(
                url=url,
                audit_type="Ежемесячный аудит",
                result=result,
                score=score,
                errors_count=errors_count,
                user_id=require_user_id()
            )

            audit_date = datetime.now().strftime("%Y-%m-%d %H:%M")
            st.session_state.monthly_audit_data = audit_data
            st.session_state.monthly_audit_date = audit_date
            st.session_state.monthly_audit_status = "Завершен"
            progress.progress(100)
            status.update(label="Аудит завершен и сохранен", state="complete")

        st.success("Ежемесячный аудит завершен.")
        st.rerun()

    if not st.session_state.monthly_audit_data:
        st.markdown(
            """
            <div class="ts-empty-state">
                <div class="ts-card-title">Audit center ожидает запуск</div>
                <div class="ts-card-text">
                    Нажмите большую кнопку выше, чтобы собрать SEO Summary, Sitemap.xml, Robots.txt, Meta Tags,
                    Canonical, Pagination, Broken Links, Redirects, Reviews и Error Center.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        return

    audit_data = st.session_state.monthly_audit_data
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
