from html import escape

import streamlit as st

from config.settings import YANDEX_GPT_API_KEY, YANDEX_GPT_FOLDER_ID, YANDEX_SEARCH_API_KEY, YANDEX_SEARCH_FOLDER_ID
from database.db import (
    disconnect_telegram,
    get_seo_monitoring_settings,
    get_telegram_integration,
    get_today_ai_assistant_usage_count,
    get_today_ai_feature_usage_count,
    get_today_competitor_analysis_count,
    get_user_notification_settings,
    upsert_seo_monitoring_settings,
    upsert_user_notification_settings,
)
from services.ai_service import yandex_gpt_available
from services.yandex_oauth_service import get_yandex_integration_status
from views.auth_page import require_user_id


AI_LIMITS = {
    "competitor_analysis": 3,
    "ai_assistant": 10,
    "text_check": 20,
}


def _inject_settings_styles():
    st.markdown(
        """
        <style>
            .ts-settings-hero {
                display:flex;
                justify-content:space-between;
                gap:18px;
                align-items:flex-end;
                padding:22px 0 10px;
            }
            .ts-settings-title {
                font-size:30px;
                font-weight:800;
                color:#111827;
                letter-spacing:0;
            }
            .ts-settings-subtitle {
                max-width:760px;
                color:#6b7280;
                font-size:15px;
                line-height:1.55;
                margin-top:6px;
            }
            .ts-settings-section {
                margin-top:22px;
                padding:18px;
                border:1px solid #e5e7eb;
                border-radius:8px;
                background:#fff;
                box-shadow:0 1px 2px rgba(15,23,42,.04);
            }
            .ts-settings-section h3 {
                margin:0 0 4px;
                font-size:18px;
                color:#111827;
            }
            .ts-settings-muted {
                color:#6b7280;
                font-size:13px;
                line-height:1.45;
            }
            .ts-status-row {
                display:flex;
                align-items:center;
                justify-content:space-between;
                gap:12px;
                padding:12px 0;
                border-bottom:1px solid #f1f5f9;
            }
            .ts-status-row:last-child { border-bottom:0; }
            .ts-status-name {
                font-weight:700;
                color:#1f2937;
            }
            .ts-status-note {
                color:#6b7280;
                font-size:13px;
                margin-top:2px;
            }
            .ts-pill {
                display:inline-flex;
                align-items:center;
                gap:7px;
                padding:5px 10px;
                border-radius:999px;
                font-weight:700;
                font-size:12px;
                white-space:nowrap;
            }
            .ts-pill-ok {
                background:#dcfce7;
                color:#166534;
            }
            .ts-pill-bad {
                background:#fee2e2;
                color:#991b1b;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _mask_chat_id(chat_id):
    value = str(chat_id or "")
    if not value:
        return "не указан"
    if len(value) <= 4:
        return "****"
    return f"{value[:2]}***{value[-2:]}"


def _status_pill(ok):
    label = "Подключено" if ok else "Не настроено"
    css = "ts-pill-ok" if ok else "ts-pill-bad"
    return f'<span class="ts-pill {css}">{escape(label)}</span>'


def _integration_row(name, ok, note):
    st.markdown(
        f"""
        <div class="ts-status-row">
            <div>
                <div class="ts-status-name">{escape(name)}</div>
                <div class="ts-status-note">{escape(note)}</div>
            </div>
            {_status_pill(ok)}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_telegram_section(user_id):
    telegram = get_telegram_integration(user_id)
    monitoring = get_seo_monitoring_settings(user_id)
    connected = bool(telegram)

    st.markdown('<div class="ts-settings-section">', unsafe_allow_html=True)
    st.markdown("### Telegram")
    col1, col2, col3 = st.columns([1.2, 1.2, 1])
    with col1:
        st.metric("Статус", "Подключён" if connected else "Не подключён")
    with col2:
        if connected:
            username = telegram.get("telegram_username")
            account = f"@{username}" if username else _mask_chat_id(telegram.get("telegram_chat_id"))
            st.metric("Аккаунт", account)
            st.caption(f"chat_id: {_mask_chat_id(telegram.get('telegram_chat_id'))}")
        else:
            st.metric("Аккаунт", "нет")
    with col3:
        st.metric("Автосводки", "Включены" if monitoring.get("enabled") else "Выключены")

    if connected and st.button("Отвязать Telegram", use_container_width=True):
        disconnect_telegram(user_id)
        upsert_seo_monitoring_settings(
            user_id=user_id,
            enabled=False,
            frequency=monitoring.get("frequency") or "every_3_days",
            next_run_at=None,
        )
        st.success("Telegram отвязан, автосводки выключены.")
        st.rerun()
    elif not connected:
        st.info("Telegram можно подключить в разделе «Мои сайты» в блоке автоматического мониторинга.")
    st.markdown("</div>", unsafe_allow_html=True)


def _render_notifications_section(user_id):
    settings = get_user_notification_settings(user_id)
    fields = [
        ("daily_summary", "Ежедневная сводка"),
        ("weekly_summary", "Еженедельная сводка"),
        ("critical_only", "Только критичные события"),
        ("notify_index_drop", "Падение индексации"),
        ("notify_404_spike", "Рост 404 ошибок"),
        ("notify_robots_change", "Изменение robots.txt"),
        ("notify_site_down", "Сайт недоступен"),
    ]

    st.markdown('<div class="ts-settings-section">', unsafe_allow_html=True)
    st.markdown("### Уведомления")
    st.markdown('<div class="ts-settings-muted">Настройки сохраняются сразу после переключения.</div>', unsafe_allow_html=True)

    updated = {key: bool(settings.get(key)) for key, _ in fields}
    for index in range(0, len(fields), 2):
        cols = st.columns(2)
        for col, item in zip(cols, fields[index:index + 2]):
            key, label = item
            with col:
                updated[key] = st.toggle(label, value=bool(settings.get(key)), key=f"notification_{key}_{user_id}")

    changed = any(updated[key] != bool(settings.get(key)) for key, _ in fields)
    if changed:
        upsert_user_notification_settings(user_id, **updated)
        st.toast("Настройки уведомлений сохранены")
    st.markdown("</div>", unsafe_allow_html=True)


def _usage_line(label, value, limit):
    st.metric(label, f"{value} / {limit} today")


def _render_ai_limits_section(user_id):
    competitor_count = get_today_competitor_analysis_count(user_id)
    assistant_count = get_today_ai_assistant_usage_count(user_id)
    text_count = get_today_ai_feature_usage_count(user_id, "text_check")

    st.markdown('<div class="ts-settings-section">', unsafe_allow_html=True)
    st.markdown("### AI лимиты")
    col1, col2, col3 = st.columns(3)
    with col1:
        _usage_line("Competitor analysis", competitor_count, AI_LIMITS["competitor_analysis"])
    with col2:
        _usage_line("AI assistant", assistant_count, AI_LIMITS["ai_assistant"])
    with col3:
        _usage_line("Text check", text_count, AI_LIMITS["text_check"])
    st.markdown("</div>", unsafe_allow_html=True)


def _render_integrations_section(user_id):
    yandex_connected = bool(get_yandex_integration_status(user_id).get("connected"))
    telegram_connected = bool(get_telegram_integration(user_id))
    yandex_gpt_connected = yandex_gpt_available() or bool(YANDEX_GPT_API_KEY and YANDEX_GPT_FOLDER_ID)
    search_api_connected = bool(YANDEX_SEARCH_API_KEY and YANDEX_SEARCH_FOLDER_ID)

    st.markdown('<div class="ts-settings-section">', unsafe_allow_html=True)
    st.markdown("### Интеграции")
    _integration_row("Yandex Webmaster", yandex_connected, "Использует общий OAuth Яндекса")
    _integration_row("Yandex Metrika", yandex_connected, "Использует тот же OAuth токен")
    _integration_row("Telegram", telegram_connected, "Персональное подключение пользователя")
    _integration_row("YandexGPT", yandex_gpt_connected, "Генерация AI анализа и проверки текста")
    _integration_row("Search API", search_api_connected, "Поиск конкурентов через Yandex Search API")
    st.markdown("</div>", unsafe_allow_html=True)


def show_settings_page():
    user_id = require_user_id()
    _inject_settings_styles()
    st.markdown(
        """
        <div class="ts-settings-hero">
            <div>
                <div class="ts-settings-title">Настройки</div>
                <div class="ts-settings-subtitle">
                    Центр пользовательских настроек: Telegram, уведомления, AI лимиты и статусы интеграций.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _render_telegram_section(user_id)
    _render_notifications_section(user_id)
    _render_ai_limits_section(user_id)
    _render_integrations_section(user_id)
