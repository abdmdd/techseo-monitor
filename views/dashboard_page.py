import random
from html import escape

import pandas as pd
import streamlit as st

from components.ui_helpers import metric_card, risk_card
from database.db import get_audit_history, get_sites
from services.score_service import get_score_risk
from views.auth_page import get_current_user, require_user_id


MOTIVATION_PHRASES = [
    "🚀 Сильное SEO начинается с чистой технической базы.",
    "🧭 Один исправленный редирект сегодня может спасти десятки переходов завтра.",
    "🔎 Проверяй индексацию спокойно: поисковые роботы любят порядок.",
    "⚡ Быстрый сайт, чистые meta и понятная структура - уже половина роста.",
    "🛠️ Маленькие SEO-правки складываются в большой органический результат.",
    "📈 Сегодня убираем ошибки, завтра видим рост в поиске.",
]


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


def action_card(icon, title, text):
    st.markdown(
        f"""
        <div class="ts-action-card">
            <div class="ts-action-icon">{escape(icon)}</div>
            <div class="ts-card-title">{escape(title)}</div>
            <div class="ts-card-text">{escape(text)}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def feature_card(icon, title, text):
    st.markdown(
        f"""
        <div class="ts-feature-card">
            <div class="ts-feature-icon">{escape(icon)}</div>
            <div class="ts-card-title">{escape(title)}</div>
            <div class="ts-card-text">{escape(text)}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def audit_card(audit):
    site_url = audit[1]
    audit_type = audit[2]
    score = audit[3]
    errors_count = audit[4]
    created_at = audit[11]
    score_risk = get_score_risk(score)
    score_color = score_risk["color"]

    st.markdown(
        f"""
        <div class="ts-audit-card">
            <div class="ts-card-title">{escape(site_url)}</div>
            <div class="ts-card-text">{escape(audit_type)}</div>
            <div class="ts-audit-meta">
                <span class="ts-score-chip" style="background: {escape(score_color)};">{escape(str(score))}/100</span>
                <span>{escape(str(errors_count))} ошибок</span>
            </div>
            <div class="ts-card-text" style="margin-top: 10px;">{escape(str(created_at))}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def get_user_name():
    user = get_current_user() or {}
    email = user.get("email", "")
    return email.split("@")[0] if email else "SEO specialist"


def show_dashboard():
    user_id = require_user_id()
    user_name = get_user_name()
    sites = get_sites(user_id=user_id)
    history = get_audit_history(user_id=user_id)

    sites_count = len(sites)
    audits_count = len(history)
    latest_audit = history[0] if history else None
    latest_score = latest_audit[3] if latest_audit else 0
    latest_errors = latest_audit[4] if latest_audit else 0
    latest_audit_label = latest_audit[11] if latest_audit else "Пока нет аудитов"

    score_risk = get_score_risk(latest_score)

    st.markdown(
        f"""
        <div class="ts-saas-hero">
            <div>
                <div class="ts-saas-hero-title">Привет, {escape(user_name)}. SEO-панель готова к работе.</div>
                <div class="ts-saas-hero-subtitle">
                    Следите за техническим здоровьем сайтов, последними аудитами, ошибками crawler и ключевыми зонами роста в одном рабочем пространстве.
                </div>
            </div>
            <div class="ts-saas-pill">MVP workspace</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    col1, col2, col3, col4, col5 = st.columns([1.2, 1, 1, 1, 1.2])

    with col1:
        metric_card("SEO Score", f"{latest_score}/100", "Последний аудит", "#2563eb")
    with col2:
        metric_card("Сайтов", sites_count, "В мониторинге", "#0f766e")
    with col3:
        metric_card("Аудитов", audits_count, "Всего проверок", "#7c3aed")
    with col4:
        metric_card("Ошибок", latest_errors, "В последнем аудите", "#dc2626")
    with col5:
        risk_card(latest_score, score_risk["risk"], score_risk["color"])

    st.caption(f"Последний аудит: {latest_audit_label}")

    section_header(
        "Быстрые действия",
        "Короткие сценарии для ежедневной работы с SEO-мониторингом."
    )

    action_cols = st.columns(4)
    actions = [
        ("▶", "Запустить аудит", "Перейдите в monthly или quarterly audit и проверьте выбранный сайт."),
        ("＋", "Добавить сайт", "Создайте новый сайт в мониторинге и привяжите источники данных."),
        ("✎", "Генерация meta", "Подготовьте title и description для страницы."),
        ("✨", "Получить напутствие", "Быстрая SEO-мотивация для следующего шага."),
    ]

    for column, action in zip(action_cols, actions):
        with column:
            action_card(*action)

    button_cols = st.columns(4)
    with button_cols[0]:
        if st.button("Запустить аудит", use_container_width=True):
            st.info("Откройте раздел «Ежемесячный аудит» или «Ежеквартальный аудит» в боковом меню.")
    with button_cols[1]:
        if st.button("Добавить сайт", use_container_width=True):
            st.info("Откройте раздел «Мои сайты» и добавьте URL в мониторинг.")
    with button_cols[2]:
        if st.button("Генерация meta", use_container_width=True):
            st.info("Откройте раздел «Генерация мета-тегов» для создания title и description.")
    with button_cols[3]:
        if st.button("Получить напутствие", use_container_width=True):
            st.success(random.choice(MOTIVATION_PHRASES))

    section_header(
        "Последние аудиты",
        "Свежие проверки в виде компактных карточек: score, ошибки и дата запуска."
    )

    if history:
        latest_cards = st.columns(3)

        for index, audit in enumerate(history[:6]):
            with latest_cards[index % 3]:
                audit_card(audit)

        df = pd.DataFrame(
            history,
            columns=[
                "ID",
                "URL",
                "Audit Type",
                "SEO Score",
                "Errors",
                "Title",
                "Description",
                "Canonical",
                "H1",
                "Robots",
                "Sitemap",
                "Date"
            ]
        )

        st.divider()
        section_header("Динамика SEO Score", "Изменение health score по сохраненным аудитам.")
        chart_df = df[["Date", "SEO Score"]].copy().sort_values(by="Date")
        st.line_chart(chart_df.set_index("Date"), height=250)
    else:
        st.markdown(
            '<div class="ts-empty-state">Аудитов пока нет. Добавьте сайт и запустите первую проверку, чтобы здесь появились карточки.</div>',
            unsafe_allow_html=True
        )

    section_header(
        "Возможности платформы",
        "Основные модули MVP, которые помогают держать техническое SEO под контролем."
    )

    features = [
        ("🔍", "SEO аудит", "Базовая техническая проверка страниц и ключевых сигналов."),
        ("🗺️", "Sitemap/Robots", "Контроль sitemap.xml, robots.txt и доступности для crawler."),
        ("🔗", "Broken links", "Поиск битых внутренних ссылок и проблемных ответов."),
        ("🏷️", "Canonical", "Проверка canonical и дублей важных meta-сигналов."),
        ("↪", "Redirects", "Контроль цепочек редиректов и homepage-вариантов."),
        ("✍️", "AI Meta Generator", "Генерация title и description для SEO-страниц."),
        ("📊", "Yandex Webmaster", "Интеграционные блоки для поисковой аналитики."),
        ("🎯", "Competitor Analysis", "Зона будущего анализа конкурентов и SERP-сигналов."),
    ]

    for row_start in range(0, len(features), 4):
        cols = st.columns(4)

        for column, feature in zip(cols, features[row_start:row_start + 4]):
            with column:
                feature_card(*feature)
