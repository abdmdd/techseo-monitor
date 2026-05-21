from html import escape

import pandas as pd
import streamlit as st

from components.ui_helpers import compact_note, metric_card
from services.competitor_service import discover_competitors


def section_header(title, subtitle=""):
    st.markdown(
        f"""
        <div class="ts-dashboard-section">
            <div class="ts-section-title">{escape(title)}</div>
            <div class="ts-section-subtitle">{escape(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def keyword_chips(keywords):
    if not keywords:
        return '<span class="ts-meta-issue-chip">Ключевые слова пока не выделены</span>'

    return "".join(
        f'<span class="ts-keyword-chip">{escape(str(keyword))}</span>'
        for keyword in keywords[:12]
    )


def competitor_card(competitor):
    chips = keyword_chips(competitor.get("overlap_keywords", []))

    st.markdown(
        f"""
        <div class="ts-competitor-card">
            <div class="ts-competitor-head">
                <div>
                    <div class="ts-site-domain">{escape(competitor.get("domain", ""))}</div>
                    <div class="ts-card-text">{escape(competitor.get("theme", ""))}</div>
                </div>
                <span class="ts-score-chip" style="background:#2563eb;">Пересечение {escape(str(competitor.get("overlap_score", 0)))}%</span>
            </div>
            <div class="ts-card-title">Title</div>
            <div class="ts-card-text">{escape(competitor.get("title", ""))}</div>
            <div class="ts-card-title" style="margin-top:10px;">Description</div>
            <div class="ts-card-text">{escape(competitor.get("description", ""))}</div>
            <div class="ts-card-title" style="margin-top:12px;">Общие ключевые слова</div>
            <div class="ts-keyword-row">{chips}</div>
            <div class="ts-card-text" style="margin-top:12px;">Источник: {escape(competitor.get("discovery_source", ""))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def profile_card(profile):
    st.markdown(
        f"""
        <div class="ts-audit-section-card">
            <div class="ts-card-title">Анализ вашего сайта</div>
            <div class="ts-audit-kv"><span>Домен</span><strong>{escape(profile.get("domain", ""))}</strong></div>
            <div class="ts-audit-kv"><span>Статус загрузки</span><strong>{escape(profile.get("fetch_status", ""))}</strong></div>
            <div class="ts-audit-kv"><span>Title</span><strong>{escape(profile.get("title", "") or "не найден")}</strong></div>
            <div class="ts-audit-kv"><span>Description</span><strong>{escape(profile.get("description", "") or "не найден")}</strong></div>
            <div class="ts-audit-kv"><span>H1</span><strong>{escape(profile.get("h1", "") or "не найден")}</strong></div>
            <div class="ts-keyword-row">{keyword_chips(profile.get("keywords", []))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if profile.get("fetch_error"):
        st.warning(profile["fetch_error"])


def comparison_dataframe(competitors):
    return pd.DataFrame(
        [
            {
                "Конкурент": item.get("domain", ""),
                "Тематика": item.get("theme", ""),
                "Пересечение": f"{item.get('overlap_score', 0)}%",
                "Общие ключи": ", ".join(item.get("overlap_keywords", [])) or "нет",
                "Title": item.get("title", ""),
            }
            for item in competitors
        ]
    )


def show_competitors_page():
    st.markdown(
        """
        <div class="ts-competitors-hero">
            <div>
                <div class="ts-saas-hero-title">Конкуренты</div>
                <div class="ts-saas-hero-subtitle">
                    MVP-анализ конкурентов: анализируем главную страницу, выделяем тематику и показываем
                    предполагаемых конкурентов по пересечению ключевых слов.
                </div>
            </div>
            <div class="ts-saas-pill">Готово к парсеру выдачи</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_site, col_keywords, col_button = st.columns([1.15, 1.45, 0.5])
    with col_site:
        site_url = st.text_input("Ваш сайт", placeholder="https://example.ru", key="competitor_site_url")
    with col_keywords:
        keywords = st.text_input(
            "Ниша / ключевые слова",
            placeholder="seo аудит, техническое seo, интернет-магазин",
            key="competitor_keywords",
        )
    with col_button:
        st.write("")
        st.write("")
        run_analysis = st.button("Анализировать", type="primary", use_container_width=True)

    if run_analysis:
        with st.spinner("Анализируем главную страницу и подбираем предполагаемых конкурентов..."):
            st.session_state["competitor_intelligence"] = discover_competitors(site_url, keywords)

    data = st.session_state.get("competitor_intelligence")

    if not data:
        st.markdown(
            """
            <div class="ts-empty-state">
                🌸 Введите сайт и несколько слов о нише. Раздел проанализирует title, description, H1,
                выделит ключевые слова и покажет предполагаемых конкурентов.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    profile = data["site_profile"]
    competitors = data["competitors"]
    summary = data["summary"]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Конкурентов", summary["competitors_found"], "Предполагаемый подбор", "#2563eb")
    with col2:
        metric_card("Ключей сайта", summary["site_keywords_count"], "Из title, description, H1", "#0f766e")
    with col3:
        metric_card("Общих ключей", summary["overlap_keywords_count"], "Пересечение тематики", "#7c3aed")
    with col4:
        metric_card("Лучшее совпадение", f"{summary['best_overlap']}%", "Оценка пересечения", "#f59e0b")

    section_header(
        "Профиль сайта",
        "SEO-помощник смотрит на главную страницу и выделяет смысловые сигналы для подбора конкурентов.",
    )
    profile_card(profile)

    section_header(
        "Предполагаемые конкуренты",
        "Это MVP-подбор без внешней выдачи: он показывает близкие тематические профили и готов к подключению парсера выдачи.",
    )
    rows = [competitors[index:index + 2] for index in range(0, len(competitors), 2)]
    for row in rows:
        cols = st.columns(2)
        for col, competitor in zip(cols, row):
            with col:
                competitor_card(competitor)

    section_header("Анализ пересечений", "Сводная таблица пересечений по ключевым словам и тематике.")
    st.dataframe(comparison_dataframe(competitors), width="stretch", hide_index=True, height=280)

    section_header("Пересечение ключевых слов", "Общие темы, по которым конкуренты похожи на ваш сайт.")
    overlap_keywords = data.get("overlap_keywords", [])
    st.markdown(
        f"""
        <div class="ts-audit-section-card">
            <div class="ts-card-title">Общие ключевые слова</div>
            <div class="ts-card-text">Эти слова помогут позже построить запросы к поисковой выдаче, анализ видимости и реальные конкурентные кластеры.</div>
            <div class="ts-keyword-row">{keyword_chips(overlap_keywords)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    section_header("Архитектура будущего анализа", "Слой уже разделен так, чтобы позже подключить реальные данные.")
    arch_col1, arch_col2, arch_col3 = st.columns(3)
    architecture = [
        ("Парсер выдачи", "Будущий модуль получит реальные домены из поисковой выдачи по ключевым словам."),
        ("Анализ видимости", "Будущий расчет видимости покажет, кто чаще встречается в TOP10."),
        ("Кластеры ключей", "Будущая кластеризация сгруппирует запросы по темам и намерению пользователя."),
    ]
    for column, (title, text) in zip([arch_col1, arch_col2, arch_col3], architecture):
        with column:
            st.markdown(
                f"""
                <div class="ts-feature-card">
                    <div class="ts-feature-icon">CI</div>
                    <div class="ts-card-title">{escape(title)}</div>
                    <div class="ts-card-text">{escape(text)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    compact_note("Раздел не меняет crawler, Celery, sqlite, auth и FastAPI. Это отдельный MVP-слой конкурентного анализа для будущей выдачи и видимости.")
