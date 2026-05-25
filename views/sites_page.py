from html import escape
from urllib.parse import urlparse

import streamlit as st

from components.ui_helpers import metric_card
from database.db import add_site
from services.yandex_oauth_service import (
    disconnect_yandex_integration,
    generate_yandex_auth_url,
    get_yandex_integration_status,
)
from views.auth_page import require_user_id
from views.cached_data import cached_get_audit_history, cached_get_sites, clear_cached_data


def get_domain(url):
    parsed = urlparse(url or "")
    return parsed.netloc or url


def latest_audit_by_url(history):
    latest = {}

    for audit in history:
        site_url = audit[1]

        if site_url not in latest:
            latest[site_url] = audit

    return latest


def site_status(score):
    if score is None:
        return "Новый", "ts-status-neutral"

    if score >= 80:
        return "Здоровый", "ts-status-good"

    if score >= 50:
        return "Требует внимания", "ts-status-warn"

    return "Критичный", "ts-status-bad"


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


def site_card(site, audit):
    name = site[1]
    url = site[2]
    domain = get_domain(url)
    score = audit[3] if audit else None
    errors_count = audit[4] if audit else 0
    last_audit_date = audit[11] if audit else "Нет аудитов"
    status, status_class = site_status(score)
    score_label = f"{score}/100" if score is not None else "—"

    st.markdown(
        f"""
        <div class="ts-site-card">
            <div class="ts-site-domain">{escape(domain)}</div>
            <div class="ts-site-url">{escape(name)} · {escape(url)}</div>
            <span class="ts-status-chip {status_class}">{escape(status)}</span>
            <div class="ts-site-grid">
                <div class="ts-site-stat">
                    <div class="ts-site-stat-label">SEO-оценка</div>
                    <div class="ts-site-stat-value">{escape(score_label)}</div>
                </div>
                <div class="ts-site-stat">
                    <div class="ts-site-stat-label">Ошибки</div>
                    <div class="ts-site-stat-value">{escape(str(errors_count))}</div>
                </div>
            </div>
            <div class="ts-card-text">Последний аудит: {escape(str(last_audit_date))}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def yandex_webmaster_oauth_card(user_id, site):
    site_id = site[0]
    status = get_yandex_integration_status(user_id, site_id)

    st.markdown("##### Яндекс Вебмастер")

    if status["connected"]:
        st.success("Подключено")
        st.caption(f"Дата подключения: {status.get('connected_at') or '—'}")

        if st.button("Отключить Яндекс Вебмастер", key=f"disconnect_yandex_webmaster_{site_id}", use_container_width=True):
            if disconnect_yandex_integration(user_id, site_id):
                st.success("Яндекс Вебмастер отключён.")
                st.rerun()
            else:
                st.warning("Не удалось отключить Яндекс Вебмастер.")
        return

    try:
        auth_url = generate_yandex_auth_url(user_id, site_id)
    except ValueError as exc:
        st.warning(str(exc))
        return

    st.link_button(
        "Подключить Яндекс Вебмастер",
        auth_url,
        use_container_width=True,
    )


def integration_card(icon, title, status, text):
    st.markdown(
        f"""
        <div class="ts-integration-card">
            <div class="ts-integration-icon">{escape(icon)}</div>
            <div class="ts-card-title">{escape(title)}</div>
            <span class="ts-status-chip ts-status-neutral">{escape(status)}</span>
            <div class="ts-card-text" style="margin-top: 10px;">{escape(text)}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def integration_center_card(integration):
    status_class = integration.get("status_class", "ts-status-disconnected")

    st.markdown(
        f"""
        <div class="ts-integration-center-card">
            <div class="ts-integration-header">
                <div class="ts-integration-title-wrap">
                    <div class="ts-integration-icon">{escape(integration["icon"])}</div>
                    <div>
                        <div class="ts-card-title">{escape(integration["title"])}</div>
                        <div class="ts-card-text">{escape(integration["description"])}</div>
                    </div>
                </div>
                <span class="ts-status-chip {status_class}">{escape(integration["connection_status"])}</span>
            </div>
            <div class="ts-integration-meta-grid">
                <div class="ts-integration-meta">
                    <div class="ts-integration-label">Sync status</div>
                    <div class="ts-integration-value">{escape(integration["sync_status"])}</div>
                </div>
                <div class="ts-integration-meta">
                    <div class="ts-integration-label">Connected date</div>
                    <div class="ts-integration-value">{escape(integration["connected_date"])}</div>
                </div>
                <div class="ts-integration-meta">
                    <div class="ts-integration-label">Account</div>
                    <div class="ts-integration-value">{escape(integration["account"])}</div>
                </div>
                <div class="ts-integration-meta">
                    <div class="ts-integration-label">Token status</div>
                    <div class="ts-integration-value">{escape(integration["token_status"])}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def integration_actions(integration_key):
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Подключить", key=f"connect_{integration_key}", use_container_width=True):
            st.info("OAuth backend пока не подключен. UI готов к будущему connect flow.")

    with col2:
        if st.button("Обновить", key=f"sync_{integration_key}", use_container_width=True):
            st.info("Sync placeholder готов. Фоновую синхронизацию подключим отдельным backend-шагом.")

    with col3:
        if st.button("Отключить", key=f"disconnect_{integration_key}", use_container_width=True):
            st.warning("Disconnect placeholder готов. Реальное удаление токена появится вместе с OAuth-хранилищем.")


def show_integration_center():
    integrations = [
        {
            "key": "yandex_webmaster",
            "icon": "Я",
            "title": "Яндекс Вебмастер",
            "description": "Индексация, crawl signals, host status и поисковые диагностические данные.",
            "connection_status": "Не подключено",
            "status_class": "ts-status-disconnected",
            "sync_status": "Ожидает OAuth",
            "connected_date": "—",
            "account": "account@yandex.ru",
            "token_status": "Нет токена",
        },
        {
            "key": "yandex_metrika",
            "icon": "M",
            "title": "Яндекс Метрика",
            "description": "Трафик, цели, поведение пользователей и органическая аналитика.",
            "connection_status": "Запланировано",
            "status_class": "ts-status-pending",
            "sync_status": "Не синхронизируется",
            "connected_date": "—",
            "account": "counter placeholder",
            "token_status": "Нет токена",
        },
    ]

    for row_start in range(0, len(integrations), 2):
        cols = st.columns(2)

        for column, integration in zip(cols, integrations[row_start:row_start + 2]):
            with column:
                integration_center_card(integration)
                integration_actions(integration["key"])


def show_add_site_form(user_id):
    with st.form("add_site_form"):
        st.markdown("#### Новый сайт")

        col1, col2 = st.columns(2)

        with col1:
            site_name = st.text_input(
                "Название сайта",
                placeholder="Например: Основной сайт"
            )
            site_url = st.text_input(
                "URL сайта",
                placeholder="https://example.ru"
            )
            yandex_host_id = st.text_input(
                "Yandex Webmaster Host ID",
                placeholder="example.ru"
            )

        with col2:
            google_property = ""
            yandex_reviews_url = st.text_input(
                "Яндекс.Карты",
                placeholder="https://yandex.ru/maps/org/..."
            )
            google_reviews_url = st.text_input(
                "Google Maps",
                placeholder="https://www.google.com/maps/place/..."
            )
            twogis_reviews_url = st.text_input(
                "2ГИС",
                placeholder="https://2gis.ru/..."
            )

        submitted = st.form_submit_button("Добавить сайт", type="primary", use_container_width=True)

        if submitted:
            if not site_name or not site_url:
                st.warning("Заполните название сайта и URL.")
            elif not site_url.startswith(("http://", "https://")):
                st.warning("URL должен начинаться с http:// или https://")
            else:
                add_site(
                    site_name,
                    site_url,
                    yandex_host_id,
                    google_property,
                    yandex_reviews_url,
                    google_reviews_url,
                    twogis_reviews_url,
                    user_id=user_id
                )
                clear_cached_data()
                st.session_state.show_add_site_form = False
                st.success(f"Сайт добавлен: {site_name}")
                st.rerun()


def show_empty_state():
    st.markdown(
        """
        <div class="ts-empty-state">
            <div class="ts-card-title">Сайтов пока нет</div>
            <div class="ts-card-text">
                🌸 Добавьте первый сайт, чтобы запускать аудиты, отслеживать SEO-оценку и подключать поисковые интеграции.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def show_sites_page():
    user_id = require_user_id()
    sites = cached_get_sites(user_id=user_id)
    history = cached_get_audit_history(user_id=user_id)
    audits_by_url = latest_audit_by_url(history)

    if st.session_state.pop("yandex_oauth_success", None):
        st.success("Яндекс Вебмастер подключён")

    oauth_error = st.session_state.pop("yandex_oauth_error", None)
    if oauth_error:
        st.error(oauth_error)

    sites_count = len(sites)
    latest_audit = history[0] if history else None
    latest_audit_label = latest_audit[11] if latest_audit else "Нет аудитов"
    scores = [audit[3] for audit in history if audit[3] is not None]
    average_score = round(sum(scores) / len(scores), 1) if scores else "—"
    total_errors = sum(audit[4] for audit in history[:5]) if history else 0
    summary = (
        f"Средняя SEO-оценка: {average_score}. Ошибок в последних аудитах: {total_errors}."
        if history
        else "Добавьте сайт и запустите первый аудит, чтобы увидеть SEO summary."
    )

    st.markdown(
        f"""
        <div class="ts-sites-header">
            <div>
                <div class="ts-saas-hero-title">Мои сайты</div>
                <div class="ts-saas-hero-subtitle">{escape(summary)}</div>
            </div>
            <div class="ts-saas-pill">Последний аудит: {escape(str(latest_audit_label))}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        metric_card("Сайтов", sites_count, "В мониторинге", "#0f766e")
    with col2:
        metric_card("Последний аудит", latest_audit_label, "Свежая проверка", "#2563eb")
    with col3:
        metric_card("SEO summary", average_score, "Средний score", "#7c3aed")

    if "show_add_site_form" not in st.session_state:
        st.session_state.show_add_site_form = False

    if st.button("➕ Добавить сайт", type="primary", use_container_width=True):
        st.session_state.show_add_site_form = not st.session_state.show_add_site_form

    if st.session_state.show_add_site_form:
        show_add_site_form(user_id)

    section_header(
        "Карточки сайтов",
        "Домены, последние аудиты, ошибки и быстрые действия по каждому проекту."
    )

    if not sites:
        show_empty_state()
    else:
        for row_start in range(0, len(sites), 2):
            cols = st.columns(2)

            for column, site in zip(cols, sites[row_start:row_start + 2]):
                with column:
                    site_card(site, audits_by_url.get(site[2]))

                    st.link_button("Открыть сайт", site[2], use_container_width=True)
                    yandex_webmaster_oauth_card(user_id, site)

    section_header(
        "Интеграции",
        "Архитектурные блоки для подключения данных без OAuth backend на этом этапе."
    )

    show_integration_center()
