from html import escape
from urllib.parse import urlparse

import streamlit as st

from components.ui_helpers import metric_card
from database.db import add_site
from services.yandex_oauth_service import (
    disconnect_yandex_integration,
    generate_yandex_auth_url,
    get_yandex_access_token,
    get_yandex_integration_status,
)
from services.yandex_metrika_service import find_matching_counter, friendly_metrika_error
from services.yandex_webmaster_service import find_matching_host, friendly_webmaster_error
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


def yandex_integrations_block(user_id, sites):
    status = get_yandex_integration_status(user_id)

    st.markdown("#### Интеграции Яндекса")

    if status["connected"]:
        st.success("Аккаунт Яндекса подключён")
        st.caption(f"Дата подключения: {status.get('connected_at') or '—'}")

        if st.button("Отключить Яндекс", key="disconnect_yandex", use_container_width=True):
            if disconnect_yandex_integration(user_id):
                st.success("Яндекс отключён.")
                st.rerun()
            else:
                st.warning("Не удалось отключить Яндекс.")
        render_yandex_site_matches(user_id, sites)
        return

    try:
        auth_url = generate_yandex_auth_url(user_id)
    except ValueError as exc:
        st.warning(str(exc))
        return

    st.link_button(
        "Подключить Яндекс",
        auth_url,
        use_container_width=True,
    )


def render_yandex_site_matches(user_id, sites):
    if not sites:
        st.info("Добавьте сайт, чтобы проверить его в Яндекс Вебмастере и Яндекс Метрике.")
        return

    access_token, token_error = get_yandex_access_token(user_id)
    if token_error == "reconnect_required":
        st.error("Нужно переподключить Яндекс.")
        return
    if token_error or not access_token:
        st.warning("Не удалось получить активный токен Яндекса.")
        return

    st.markdown("##### Статус по сайтам")

    for site in sites:
        site_name = site[1]
        site_url = site[2]
        webmaster_match = find_matching_host(access_token, site_url)
        if webmaster_match.get("status_code") == 401:
            access_token, token_error = get_yandex_access_token(user_id, force_refresh=True)
            if token_error or not access_token:
                st.error("Нужно переподключить Яндекс.")
                return
            webmaster_match = find_matching_host(access_token, site_url)

        metrika_match = find_matching_counter(access_token, site_url)
        if metrika_match.get("status_code") == 401:
            access_token, token_error = get_yandex_access_token(user_id, force_refresh=True)
            if token_error or not access_token:
                st.error("Нужно переподключить Яндекс.")
                return
            metrika_match = find_matching_counter(access_token, site_url)

        webmaster_found = webmaster_match.get("ok") and webmaster_match.get("found")
        metrika_found = metrika_match.get("ok") and metrika_match.get("found")
        webmaster_label = "подключён" if webmaster_found else ("не найден сайт" if webmaster_match.get("ok") else "нет доступа")
        metrika_label = "найден счётчик" if metrika_found else ("не найден счётчик" if metrika_match.get("ok") else "нет доступа")

        kv_card(
            site_name,
            [
                ("Сайт", site_url),
                ("Яндекс Вебмастер", webmaster_label),
                ("Яндекс Метрика", metrika_label),
            ],
        )

        cols = st.columns(2)
        host_id = webmaster_match.get("host_id")
        counter_id = metrika_match.get("counter_id")

        with cols[0]:
            if host_id:
                st.link_button(
                    "Открыть Вебмастер",
                    f"https://webmaster.yandex.ru/site/dashboard/?host={host_id}",
                    use_container_width=True,
                )
            elif not webmaster_match.get("ok"):
                st.warning(friendly_webmaster_error(webmaster_match))
        with cols[1]:
            if counter_id:
                st.link_button(
                    "Открыть Метрику",
                    f"https://metrika.yandex.ru/dashboard?id={counter_id}",
                    use_container_width=True,
                )
            elif not metrika_match.get("ok"):
                st.warning(friendly_metrika_error(metrika_match))
            elif metrika_match.get("ok"):
                st.info("Создайте счётчик Яндекс Метрики и привяжите его к сайту.")


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
        st.success("Яндекс подключён")

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

    section_header(
        "Интеграции Яндекса",
        "Общее подключение аккаунта Яндекса используется для Вебмастера и Метрики на всех сайтах пользователя."
    )

    yandex_integrations_block(user_id, sites)
