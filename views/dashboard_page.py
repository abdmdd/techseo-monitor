import base64
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from assets.motivation_quotes import get_random_motivation
from components.ui_helpers import metric_card, risk_card
from database.db import get_audit_history, get_sites
from services.score_service import get_score_risk
from views.auth_page import get_current_user, require_user_id


def section_header(title, subtitle):
    st.markdown(
        f"""
        <div class="ts-dashboard-section">
            <div class="ts-section-title">{escape(title)}</div>
            <div class="ts-section-subtitle">{escape(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
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
        unsafe_allow_html=True,
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
        unsafe_allow_html=True,
    )


def step_card(number, title, text):
    st.markdown(
        f"""
        <div class="ts-step-card">
            <div class="ts-step-number">{escape(str(number))}</div>
            <div class="ts-card-title">{escape(title)}</div>
            <div class="ts-card-text">{escape(text)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def motivation_card(item):
    image_path = item.get("image_path", "")
    image_html = ""

    if image_path and Path(image_path).exists():
        encoded_image = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
        image_html = f'<img class="ts-motivation-image" src="data:image/jpeg;base64,{encoded_image}" alt="SEO напутствие">'

    st.markdown(
        f"""
        <div class="ts-motivation-shell">
            <div class="ts-motivation-card">
                {image_html}
        <div class="ts-motivation-emoji">{escape(item.get("emoji", "🌸"))}</div>
        <div class="ts-motivation-text">{escape(item.get("text", ""))}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def audit_card(audit):
    site_url = audit[1]
    audit_type = audit[2]
    score = audit[3]
    errors_count = audit[4]
    created_at = audit[11]
    score_risk = get_score_risk(score)
    score_color = score_risk["color"]
    audit_type_label = {
        "monthly": "Ежемесячный аудит",
        "quarterly": "Ежеквартальный аудит",
    }.get(str(audit_type).lower(), str(audit_type))

    st.markdown(
        f"""
        <div class="ts-audit-card">
            <div class="ts-card-title">{escape(site_url)}</div>
            <div class="ts-card-text">{escape(audit_type_label)}</div>
            <div class="ts-audit-meta">
                <span class="ts-score-chip" style="background: {escape(score_color)};">{escape(str(score))}/100</span>
                <span>{escape(str(errors_count))} ошибок</span>
            </div>
            <div class="ts-card-text" style="margin-top: 10px;">{escape(str(created_at))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_user_name():
    user = get_current_user() or {}
    email = user.get("email", "")
    return email.split("@")[0] if email else "друг"


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
    latest_audit_label = latest_audit[11] if latest_audit else "пока нет аудитов"
    score_risk = get_score_risk(latest_score)

    st.markdown(
        f"""
        <div class="ts-saas-hero">
            <div>
                <div class="ts-saas-hero-title">Привет, {escape(user_name)}. Это ваша главная SEO-панель.</div>
                <div class="ts-saas-hero-subtitle">
                    Здесь видно, что происходит с сайтами: последняя SEO-оценка, количество проверок,
                    найденные ошибки и быстрые действия для следующего шага.
                </div>
            </div>
            <div class="ts-saas-pill">Рабочее пространство MVP</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4, col5 = st.columns([1.2, 1, 1, 1, 1.2])
    with col1:
        metric_card("SEO-оценка", f"{latest_score}/100", "По последнему аудиту", "#2563eb")
    with col2:
        metric_card("Сайтов", sites_count, "Добавлено в мониторинг", "#0f766e")
    with col3:
        metric_card("Аудитов", audits_count, "Всего проверок", "#7c3aed")
    with col4:
        metric_card("Ошибок", latest_errors, "В последней проверке", "#dc2626")
    with col5:
        risk_card(latest_score, score_risk["risk"], score_risk["color"])

    st.caption(f"Последний аудит: {latest_audit_label}")

    section_header(
        "Быстрые действия",
        "Самые частые действия для спокойной ежедневной работы с SEO-мониторингом.",
    )

    action_cols = st.columns(4)
    actions = [
        ("▶", "Запустить аудит", "Проверьте сайт и получите понятный список ошибок."),
        ("+", "Добавить сайт", "Добавьте новый сайт, чтобы следить за его состоянием."),
        ("✎", "Генерация meta", "Подготовьте title и description для страницы."),
        ("✨", "Получить напутствие", "Короткая дружелюбная подсказка для следующего SEO-шага."),
    ]
    for column, action in zip(action_cols, actions):
        with column:
            action_card(*action)

    button_cols = st.columns(4)
    with button_cols[0]:
        if st.button("Запустить аудит", use_container_width=True):
            st.info("Откройте раздел «Ежемесячный аудит» и выберите сайт для проверки.")
    with button_cols[1]:
        if st.button("Добавить сайт", use_container_width=True):
            st.info("Откройте раздел «Мои сайты» и добавьте адрес сайта.")
    with button_cols[2]:
        if st.button("Генерация meta", use_container_width=True):
            st.info("Откройте раздел «Нейросети», чтобы подготовить заголовки и описания.")
    with button_cols[3]:
        if st.button("Получить напутствие 🌸", use_container_width=True):
            st.session_state["motivation_item"] = get_random_motivation()

    if st.session_state.get("motivation_item"):
        motivation_card(st.session_state["motivation_item"])

    section_header(
        "Что умеет платформа",
        "Ключевые возможности, которые помогают владельцу бизнеса видеть состояние сайта без лишней технической сложности.",
    )

    features = [
        ("🔎", "SEO-аудит", "Проверяет важные технические сигналы и помогает понять, что исправлять первым."),
        ("🗺", "Проверка sitemap.xml", "Показывает, есть ли карта сайта и доступна ли она поисковикам."),
        ("🤖", "Проверка robots.txt", "Помогает не закрыть важные страницы от индексации случайно."),
        ("🔗", "Битые ссылки", "Находит ссылки, которые ведут на недоступные страницы."),
        ("🎯", "Анализ конкурентов", "Готовит основу для сравнения сайта с конкурентами в поиске."),
        ("✨", "AI для SEO", "Помогает быстрее готовить meta-теги, тексты и идеи для страниц."),
        ("📊", "Яндекс.Метрика", "Подготовленный блок для будущего подключения аналитики."),
        ("📈", "Яндекс.Вебмастер", "Подготовленный блок для будущей поисковой интеграции."),
    ]
    for row_start in range(0, len(features), 4):
        cols = st.columns(4)
        for column, feature in zip(cols, features[row_start : row_start + 4]):
            with column:
                feature_card(*feature)

    section_header(
        "Как пользоваться",
        "Начните с трех простых шагов. Этого достаточно, чтобы запустить регулярный SEO-контроль.",
    )
    step_cols = st.columns(3)
    steps = [
        (1, "Добавьте сайт", "Укажите адрес сайта, который хотите контролировать."),
        (2, "Запустите аудит", "Получите SEO-оценку, ошибки и подсказки по исправлению."),
        (3, "Исправьте ошибки", "Двигайтесь от критичных проблем к рекомендациям."),
    ]
    for column, step in zip(step_cols, steps):
        with column:
            step_card(*step)

    section_header(
        "Последние аудиты",
        "Свежие проверки в виде карточек: оценка, ошибки и дата запуска.",
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
                "Тип аудита",
                "SEO-оценка",
                "Ошибки",
                "Title",
                "Description",
                "Canonical",
                "H1",
                "Robots",
                "Sitemap",
                "Дата",
            ],
        )

        st.divider()
        section_header("Динамика SEO-оценки", "Как менялась оценка сайта по сохраненным аудитам.")
        chart_df = df[["Дата", "SEO-оценка"]].copy().sort_values(by="Дата")
        st.line_chart(chart_df.set_index("Дата"), height=250)
    else:
        st.markdown(
            """
            <div class="ts-empty-state">
                🌸 Добавьте первый сайт для начала SEO-мониторинга. После первой проверки здесь появятся карточки аудитов,
                ошибки и динамика SEO-оценки.
            </div>
            """,
            unsafe_allow_html=True,
        )
