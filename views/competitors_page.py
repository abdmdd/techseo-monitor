from html import escape
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from components.ui_helpers import compact_note, metric_card


DEFAULT_COMPETITORS = [
    {
        "domain": "auditlab.ru",
        "seo_score": 86,
        "visibility_score": 74,
        "top10_keywords": 128,
        "similarity_score": 82,
        "seo_overlap": 68,
        "top_pages": ["/seo-audit", "/technical-seo", "/pricing"],
        "title_preview": "SEO audit platform for growing teams",
        "description_preview": "Technical SEO checks, monitoring, reports, and recommendations for product teams.",
        "keyword_overlap": ["seo audit", "technical seo", "site monitoring", "meta tags"],
    },
    {
        "domain": "rankpilot.io",
        "seo_score": 78,
        "visibility_score": 61,
        "top10_keywords": 92,
        "similarity_score": 76,
        "seo_overlap": 55,
        "top_pages": ["/tools/site-audit", "/keywords", "/reports"],
        "title_preview": "Rank tracking and website audit suite",
        "description_preview": "Keyword visibility, site health tracking, and clean SEO reports in one workspace.",
        "keyword_overlap": ["rank tracking", "seo reports", "crawler", "broken links"],
    },
    {
        "domain": "webmasterpro.ru",
        "seo_score": 81,
        "visibility_score": 67,
        "top10_keywords": 104,
        "similarity_score": 71,
        "seo_overlap": 59,
        "top_pages": ["/audit", "/sitemap-checker", "/robots-txt"],
        "title_preview": "Инструменты для технического SEO",
        "description_preview": "Проверка sitemap, robots.txt, ошибок индексации и технических факторов сайта.",
        "keyword_overlap": ["sitemap", "robots txt", "technical audit", "canonical"],
    },
    {
        "domain": "serpmetrics.ai",
        "seo_score": 73,
        "visibility_score": 53,
        "top10_keywords": 74,
        "similarity_score": 64,
        "seo_overlap": 47,
        "top_pages": ["/ai-meta-generator", "/competitors", "/analytics"],
        "title_preview": "AI SEO intelligence and competitor research",
        "description_preview": "SERP insights, competitor discovery, AI metadata, and visibility analytics.",
        "keyword_overlap": ["ai seo", "competitor analysis", "meta generator", "serp api"],
    },
]


def _domain_from_url(url: str) -> str:
    value = (url or "").strip()
    if not value:
        return "your-site.ru"
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return parsed.netloc or parsed.path or "your-site.ru"


def _section_header(title: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div class="ts-dashboard-section">
            <div class="ts-section-title">{escape(title)}</div>
            <div class="ts-section-subtitle">{escape(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def generate_mock_competitors(site_url: str, keywords: str):
    """Temporary discovery layer for future SERP/API integrations."""
    own_domain = _domain_from_url(site_url)
    terms = [term.strip().lower() for term in (keywords or "").replace("\n", ",").split(",") if term.strip()]
    competitors = []

    for index, item in enumerate(DEFAULT_COMPETITORS):
        competitor = dict(item)
        boost = min(8, len(terms) * 2)
        competitor["visibility_score"] = min(99, competitor["visibility_score"] + boost - index)
        competitor["similarity_score"] = min(99, competitor["similarity_score"] + max(0, boost - 2))
        competitor["seo_overlap"] = min(99, competitor["seo_overlap"] + max(0, len(terms)))
        competitor["discovery_source"] = "Mock SERP layer"
        competitor["target_domain"] = own_domain
        competitor["seed_keywords"] = terms[:6]
        competitors.append(competitor)

    return competitors


def _score_color(score: int) -> str:
    if score >= 80:
        return "#16a34a"
    if score >= 60:
        return "#f59e0b"
    return "#dc2626"


def _competitor_card(competitor: dict):
    domain = competitor.get("domain", "")
    score = int(competitor.get("seo_score", 0))
    top_pages = competitor.get("top_pages", [])
    keyword_overlap = competitor.get("keyword_overlap", [])
    top_pages_html = "".join(f"<li>{escape(page)}</li>" for page in top_pages[:3])
    keywords_html = "".join(f'<span class="ts-keyword-chip">{escape(keyword)}</span>' for keyword in keyword_overlap[:5])

    st.markdown(
        f"""
        <div class="ts-competitor-card">
            <div class="ts-competitor-head">
                <div>
                    <div class="ts-site-domain">{escape(domain)}</div>
                    <div class="ts-card-text">Источник: {escape(competitor.get("discovery_source", "Mock"))}</div>
                </div>
                <span class="ts-score-chip" style="background:{_score_color(score)};">SEO {score}</span>
            </div>
            <div class="ts-site-grid">
                <div class="ts-site-stat">
                    <div class="ts-site-stat-label">Visibility</div>
                    <div class="ts-site-stat-value">{escape(str(competitor.get("visibility_score", 0)))}%</div>
                </div>
                <div class="ts-site-stat">
                    <div class="ts-site-stat-label">TOP10</div>
                    <div class="ts-site-stat-value">{escape(str(competitor.get("top10_keywords", 0)))}</div>
                </div>
                <div class="ts-site-stat">
                    <div class="ts-site-stat-label">Similarity</div>
                    <div class="ts-site-stat-value">{escape(str(competitor.get("similarity_score", 0)))}%</div>
                </div>
                <div class="ts-site-stat">
                    <div class="ts-site-stat-label">SEO overlap</div>
                    <div class="ts-site-stat-value">{escape(str(competitor.get("seo_overlap", 0)))}%</div>
                </div>
            </div>
            <div class="ts-card-title">Title preview</div>
            <div class="ts-card-text">{escape(competitor.get("title_preview", ""))}</div>
            <div class="ts-card-title" style="margin-top:10px;">Description preview</div>
            <div class="ts-card-text">{escape(competitor.get("description_preview", ""))}</div>
            <div class="ts-card-title" style="margin-top:12px;">Top pages</div>
            <ul class="ts-compact-list">{top_pages_html}</ul>
            <div class="ts-keyword-row">{keywords_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _comparison_dataframe(competitors):
    return pd.DataFrame(
        [
            {
                "Competitor": item["domain"],
                "SEO score": item["seo_score"],
                "Visibility": f"{item['visibility_score']}%",
                "TOP10 keywords": item["top10_keywords"],
                "Similarity": f"{item['similarity_score']}%",
                "SEO overlap": f"{item['seo_overlap']}%",
            }
            for item in competitors
        ]
    )


def _chart_placeholder(title: str, body: str):
    st.markdown(
        f"""
        <div class="ts-chart-placeholder">
            <div class="ts-card-title">{escape(title)}</div>
            <div class="ts-card-text">{escape(body)}</div>
            <div class="ts-placeholder-bars">
                <span style="height: 54%;"></span>
                <span style="height: 78%;"></span>
                <span style="height: 42%;"></span>
                <span style="height: 66%;"></span>
                <span style="height: 88%;"></span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_competitors_page():
    st.markdown(
        """
        <div class="ts-competitors-hero">
            <div>
                <div class="ts-saas-hero-title">Конкуренты</div>
                <div class="ts-saas-hero-subtitle">
                    Центр конкурентного SEO-анализа: discovery, visibility, keyword overlap и подготовка к будущим SERP/API интеграциям.
                </div>
            </div>
            <div class="ts-saas-pill">SERP architecture ready</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container():
        col_site, col_keywords, col_button = st.columns([1.1, 1.4, 0.55])
        with col_site:
            site_url = st.text_input("Ваш сайт", placeholder="https://example.ru", key="competitor_site_url")
        with col_keywords:
            keywords = st.text_input("Ниша / ключевые слова", placeholder="seo аудит, техническое seo, sitemap", key="competitor_keywords")
        with col_button:
            st.write("")
            st.write("")
            discover = st.button("Найти", use_container_width=True, type="primary")

    if discover or "competitors_result" not in st.session_state:
        st.session_state["competitors_result"] = generate_mock_competitors(site_url, keywords)

    competitors = st.session_state.get("competitors_result", [])

    if not competitors:
        st.markdown(
            """
            <div class="ts-empty-state">
                Укажите сайт и нишу, чтобы подготовить конкурентный срез. Сейчас используется mock discovery layer, позже сюда подключится SERP/API источник.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    avg_visibility = round(sum(item["visibility_score"] for item in competitors) / len(competitors))
    avg_score = round(sum(item["seo_score"] for item in competitors) / len(competitors))
    avg_overlap = round(sum(item["seo_overlap"] for item in competitors) / len(competitors))

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Конкурентов", len(competitors), "Mock discovery", "#2563eb")
    with col2:
        metric_card("Avg visibility", f"{avg_visibility}%", "Оценка видимости", "#0f766e")
    with col3:
        metric_card("Avg SEO score", avg_score, "Среднее качество", _score_color(avg_score))
    with col4:
        metric_card("Avg overlap", f"{avg_overlap}%", "Пересечение семантики", "#7c3aed")

    _section_header("Competitor cards", "Карточки конкурентов с ключевыми метриками, превью сниппетов и top pages.")
    rows = [competitors[index : index + 2] for index in range(0, len(competitors), 2)]
    for row in rows:
        cols = st.columns(2)
        for col, competitor in zip(cols, row):
            with col:
                _competitor_card(competitor)

    _section_header("Comparison table", "Единая таблица для будущего SERP/API слоя и экспорта в отчеты.")
    st.dataframe(_comparison_dataframe(competitors), use_container_width=True, hide_index=True)

    _section_header("Visibility & keyword overlap", "Плейсхолдеры графиков: структура готова для подключения реальных данных.")
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        _chart_placeholder("Visibility dynamics", "Будущий график изменения видимости конкурентов по неделям.")
    with chart_col2:
        _chart_placeholder("Keyword overlap", "Будущая визуализация пересечения TOP10 ключей и страниц.")

    _section_header("Keyword overlap blocks", "Семантические кластеры, где конкуренты пересекаются с вашим сайтом.")
    keyword_cols = st.columns(2)
    for index, competitor in enumerate(competitors):
        chips = "".join(
            f'<span class="ts-keyword-chip">{escape(keyword)}</span>'
            for keyword in competitor.get("keyword_overlap", [])
        )
        with keyword_cols[index % 2]:
            st.markdown(
                f"""
                <div class="ts-audit-section-card">
                    <div class="ts-card-title">{escape(competitor["domain"])}</div>
                    <div class="ts-card-text">Пересечение по ключам и intent-блокам.</div>
                    <div class="ts-keyword-row">{chips}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    _section_header("SERP/API architecture", "Пока без внешнего API: только подготовленные контуры будущей интеграции.")
    arch_col1, arch_col2, arch_col3 = st.columns(3)
    with arch_col1:
        st.markdown(
            """
            <div class="ts-feature-card">
                <div class="ts-feature-icon">S</div>
                <div class="ts-card-title">SERP Provider</div>
                <div class="ts-card-text">Будущий адаптер для поисковой выдачи, регионов, устройств и частоты обновления.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with arch_col2:
        st.markdown(
            """
            <div class="ts-feature-card">
                <div class="ts-feature-icon">K</div>
                <div class="ts-card-title">Keyword Clusters</div>
                <div class="ts-card-text">Слой кластеризации ключей, intent-групп и пересечений с конкурентами.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with arch_col3:
        st.markdown(
            """
            <div class="ts-feature-card">
                <div class="ts-feature-icon">A</div>
                <div class="ts-card-title">API Tokens</div>
                <div class="ts-card-text">Подготовка к безопасному хранению токенов и статусам синхронизации.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    compact_note("Данные на странице сейчас mock-based: backend crawler, sqlite, auth, FastAPI и текущий audit flow не затрагиваются.")
