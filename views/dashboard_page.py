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
    user = get_current_user() or {}
    user_name = user.get("name") or get_user_name()

    st.markdown(
        f"""
        <div class="ts-saas-hero">
            <div>
                <div class="ts-saas-hero-title">Привет, {escape(user_name)} 🌸</div>
                <div class="ts-saas-hero-subtitle">
                    Это спокойная главная страница TechSEO Monitor: возможности платформы, быстрый старт и маленькое SEO-напутствие.
                </div>
            </div>
            <div class="ts-saas-pill">SEO-блокнот MVP</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    section_header(
        "Что умеет платформа",
        "Основные возможности, которые помогают владельцу бизнеса видеть состояние сайта без лишней технической сложности.",
    )

    features = [
        ("🔎", "SEO-аудит", "Проверяет важные технические сигналы и помогает понять, что исправлять первым."),
        ("🗺", "Проверка sitemap.xml", "Показывает, есть ли карта сайта и доступна ли она поисковикам."),
        ("🤖", "Проверка robots.txt", "Помогает не закрыть важные страницы от индексации случайно."),
        ("🔗", "Битые ссылки", "Находит ссылки, которые ведут на недоступные страницы."),
        ("🎯", "Анализ конкурентов", "Помогает увидеть близкие темы и будущие зоны роста в поиске."),
        ("✨", "AI для SEO", "Помогает быстрее готовить meta-теги, тексты и идеи для страниц."),
        ("📊", "Яндекс.Метрика", "Подготовленный блок для будущего подключения аналитики."),
        ("📈", "Яндекс.Вебмастер", "Подготовленный блок для будущей поисковой интеграции."),
    ]
    for row_start in range(0, len(features), 4):
        cols = st.columns(4)
        for column, feature in zip(cols, features[row_start:row_start + 4]):
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

    section_header("Напутствие", "Маленькая дружелюбная карточка для спокойной работы.")
    if st.button("Получить напутствие 🌸", use_container_width=True):
        st.session_state["motivation_item"] = get_random_motivation()

    if st.session_state.get("motivation_item"):
        motivation_card(st.session_state["motivation_item"])
