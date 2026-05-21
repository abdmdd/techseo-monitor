from datetime import datetime
from html import escape

import streamlit as st

from components.ui_helpers import metric_card
from database.db import get_sites
from views.auth_page import require_user_id


CHECKLIST = {
    "Technical SEO": [
        {
            "id": "technical_full_crawl",
            "title": "Run full website crawl",
            "description": "Review crawl depth, broken links, redirects, canonical and meta coverage.",
            "tool": "Ежемесячный аудит",
            "url": "#",
        },
        {
            "id": "technical_performance",
            "title": "Check page speed and Core Web Vitals",
            "description": "Plan performance review for key landing pages and templates.",
            "tool": "PageSpeed Insights",
            "url": "https://pagespeed.web.dev/",
        },
        {
            "id": "technical_schema",
            "title": "Validate structured data",
            "description": "Check important pages for valid schema.org markup and rich result eligibility.",
            "tool": "Rich Results Test",
            "url": "https://search.google.com/test/rich-results",
        },
    ],
    "Indexing": [
        {
            "id": "indexing_sitemap",
            "title": "Review sitemap and robots directives",
            "description": "Confirm sitemap freshness, robots availability and indexable URL coverage.",
            "tool": "TechSEO Monitor",
            "url": "#",
        },
        {
            "id": "indexing_search_console",
            "title": "Check indexed pages and exclusions",
            "description": "Review indexed URLs, excluded URLs and important crawling warnings.",
            "tool": "Google Search Console",
            "url": "https://search.google.com/search-console",
        },
        {
            "id": "indexing_yandex",
            "title": "Check Yandex Webmaster diagnostics",
            "description": "Review host status, indexing signals and regional/search warnings.",
            "tool": "Yandex Webmaster",
            "url": "https://webmaster.yandex.ru/",
        },
    ],
    "Commercial Factors": [
        {
            "id": "commercial_contacts",
            "title": "Verify contacts and trust signals",
            "description": "Check phone, address, legal information, delivery, payment and guarantees.",
            "tool": "Manual review",
            "url": "#",
        },
        {
            "id": "commercial_reviews",
            "title": "Review reputation signals",
            "description": "Check reviews widgets, rating snippets and external map cards.",
            "tool": "Maps / Reviews",
            "url": "#",
        },
        {
            "id": "commercial_conversion",
            "title": "Review conversion paths",
            "description": "Check forms, CTAs, lead buttons and product/service page clarity.",
            "tool": "Analytics",
            "url": "#",
        },
    ],
    "Links": [
        {
            "id": "links_internal",
            "title": "Improve internal linking",
            "description": "Find orphan-like pages, weak clusters and opportunities for contextual links.",
            "tool": "Crawler report",
            "url": "#",
        },
        {
            "id": "links_broken",
            "title": "Fix broken internal links",
            "description": "Prioritize 404/internal link issues found during the full crawl.",
            "tool": "Ежемесячный аудит",
            "url": "#",
        },
        {
            "id": "links_backlinks",
            "title": "Review backlink quality",
            "description": "Check toxic links, strong referring domains and competitor link gaps.",
            "tool": "External SEO tool",
            "url": "#",
        },
    ],
    "Content": [
        {
            "id": "content_meta",
            "title": "Refresh title and description templates",
            "description": "Review duplicate, missing and weak meta tags across crawled pages.",
            "tool": "Генератор meta",
            "url": "#",
        },
        {
            "id": "content_intent",
            "title": "Check search intent alignment",
            "description": "Сравните важные посадочные страницы с целевыми запросами и ожиданиями поисковой выдачи.",
            "tool": "Обзор выдачи",
            "url": "#",
        },
        {
            "id": "content_updates",
            "title": "Plan content updates",
            "description": "Create quarterly notes for outdated pages, new sections and missing FAQs.",
            "tool": "SEO notebook",
            "url": "#",
        },
    ],
}


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
    manual_url = st.text_input("Введите URL сайта вручную", "https://example.ru")

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


def checklist_state_key(site_id, item_id, field):
    stable_site_id = site_id or "manual"
    return f"quarterly_checklist_{stable_site_id}_{item_id}_{field}"


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


def progress_bar(percent):
    st.markdown(
        f"""
        <div class="ts-progress-track">
            <div class="ts-progress-fill" style="width: {max(0, min(100, percent))}%;"></div>
        </div>
        """,
        unsafe_allow_html=True
    )


def get_checklist_stats(site_id):
    total = 0
    completed = 0
    category_stats = {}

    for category, items in CHECKLIST.items():
        category_total = len(items)
        category_completed = 0

        for item in items:
            total += 1
            checked = st.session_state.get(checklist_state_key(site_id, item["id"], "checked"), False)

            if checked:
                completed += 1
                category_completed += 1

        category_stats[category] = {
            "completed": category_completed,
            "total": category_total,
            "percent": round((category_completed / category_total) * 100) if category_total else 0,
        }

    percent = round((completed / total) * 100) if total else 0

    return completed, total, percent, category_stats


def checklist_card(site_id, category, item):
    checked_key = checklist_state_key(site_id, item["id"], "checked")
    date_key = checklist_state_key(site_id, item["id"], "checked_date")
    notes_key = checklist_state_key(site_id, item["id"], "notes")

    previous_checked = st.session_state.get(checked_key, False)
    checked = st.checkbox(item["title"], value=previous_checked, key=checked_key)

    if checked and not previous_checked:
        st.session_state[date_key] = datetime.now().strftime("%Y-%m-%d")
    elif not checked:
        st.session_state[date_key] = "—"

    checked_date = st.session_state.get(date_key, "—")

    st.markdown(
        f"""
        <div class="ts-checklist-card">
            <div class="ts-checklist-title">{escape(item["title"])}</div>
            <div class="ts-card-text">{escape(item["description"])}</div>
            <div class="ts-checklist-meta-grid">
                <div class="ts-checklist-meta">
                    <div class="ts-integration-label">Category</div>
                    <div class="ts-integration-value">{escape(category)}</div>
                </div>
                <div class="ts-checklist-meta">
                    <div class="ts-integration-label">Checked date</div>
                    <div class="ts-integration-value">{escape(checked_date)}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.text_area(
        "Notes",
        key=notes_key,
        placeholder="Add quarterly SEO notes, decisions or follow-up tasks...",
        height=86,
        label_visibility="collapsed"
    )

    if item["url"] == "#":
        st.caption(f"External tool: {item['tool']} · placeholder")
    else:
        st.link_button(item["tool"], item["url"], use_container_width=True)


def show_empty_state():
    st.markdown(
        """
        <div class="ts-empty-state">
            <div class="ts-card-title">SEO notebook is ready</div>
            <div class="ts-card-text">
                Select a site, mark checklist items as completed, add notes and use external tool links.
                Current state is temporary and prepared for future sqlite persistence.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def show_quarterly_audit_page():
    selected_site = select_site_from_db("Выберите сайт для quarterly checklist")
    site_id = selected_site[0]
    site_name = selected_site[1]
    url = selected_site[2]

    completed, total, percent, category_stats = get_checklist_stats(site_id)

    st.markdown(
        f"""
        <div class="ts-audit-header">
            <div>
                <div class="ts-saas-hero-title">SEO Checklist Center</div>
                <div class="ts-saas-hero-subtitle">
                    Planning center and SEO notebook for <strong>{escape(site_name)}</strong><br>
                    {escape(url)}
                </div>
            </div>
            <div class="ts-saas-pill">Temporary in-memory state</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        metric_card("Completed", f"{completed}/{total}", "Checklist items", "#2563eb")
    with col2:
        metric_card("Progress", f"{percent}%", "Overall completion", "#0f766e")
    with col3:
        metric_card("Categories", len(CHECKLIST), "SEO planning groups", "#7c3aed")
    with col4:
        metric_card("Notebook", "Active", "Session state", "#f59e0b")

    progress_bar(percent)

    section_header(
        "Category progress",
        "Track quarterly progress across technical, indexing, commercial, links and content work."
    )

    category_cols = st.columns(len(CHECKLIST))

    for column, (category, stats) in zip(category_cols, category_stats.items()):
        with column:
            metric_card(
                category,
                f"{stats['percent']}%",
                f"{stats['completed']}/{stats['total']} completed",
                "#2563eb"
            )

    show_empty_state()

    section_header(
        "Quarterly SEO checklist",
        "Use checkboxes, checked dates, notes and external tools to plan quarterly SEO work."
    )

    tabs = st.tabs(list(CHECKLIST.keys()))

    for tab, (category, items) in zip(tabs, CHECKLIST.items()):
        with tab:
            for row_start in range(0, len(items), 2):
                cols = st.columns(2)

                for column, item in zip(cols, items[row_start:row_start + 2]):
                    with column:
                        checklist_card(site_id, category, item)
