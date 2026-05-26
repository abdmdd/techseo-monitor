import os
import sys

import streamlit as st

# ==================================================
# PATH
# ==================================================

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ==================================================
# DATABASE / UI
# ==================================================

from components.ui_helpers import apply_global_styles
from database.db import init_db
from services.yandex_oauth_service import (
    exchange_code_for_token,
    parse_yandex_oauth_state,
    save_yandex_integration,
)

# ==================================================
# VIEWS
# ==================================================

from views.auth_page import get_current_user, init_auth_state, logout, show_auth_page
from views.dashboard_page import show_dashboard
from views.history_page import show_history_page
from views.meta_generator_page import show_meta_generator_page
from views.monthly_audit_page import show_monthly_audit_page
from views.quarterly_audit_page import show_quarterly_audit_page
from views.sites_page import show_sites_page

# ==================================================
# PAGE CONFIG
# ==================================================

st.set_page_config(
    page_title="TechSEO Monitor",
    page_icon="TS",
    layout="wide"
)

# ==================================================
# INIT
# ==================================================

@st.cache_resource(show_spinner=False)
def bootstrap_app():
    init_db()
    return True


bootstrap_app()

# ==================================================
# GLOBAL UI / AUTH GATE
# ==================================================

apply_global_styles()
init_auth_state()


def get_query_param(name):
    if hasattr(st, "query_params"):
        return st.query_params.get(name)

    values = st.experimental_get_query_params().get(name)
    return values[0] if values else None


def clear_query_params():
    if hasattr(st, "query_params"):
        st.query_params.clear()
    else:
        st.experimental_set_query_params()


def handle_yandex_oauth_callback():
    oauth_provider = get_query_param("oauth_provider")
    code = get_query_param("code")
    state = get_query_param("state")

    if oauth_provider != "yandex":
        return

    st.session_state["main_menu"] = "Мои сайты"
    payload = parse_yandex_oauth_state(state)

    if not code or not payload:
        st.session_state["yandex_oauth_error"] = "Не удалось проверить OAuth state Яндекса."
        clear_query_params()
        st.rerun()

    current_user = get_current_user()
    if current_user and current_user["id"] != payload["user_id"]:
        st.session_state["yandex_oauth_error"] = "OAuth callback не совпадает с текущим пользователем."
        clear_query_params()
        st.rerun()

    try:
        tokens = exchange_code_for_token(code)
        saved = save_yandex_integration(
            user_id=payload["user_id"],
            tokens=tokens,
        )
    except Exception as exc:
        saved = False
        st.session_state["yandex_oauth_error"] = f"Не удалось подключить Яндекс ({exc.__class__.__name__})."

    if saved:
        st.session_state["yandex_oauth_success"] = "Яндекс подключён"
    elif "yandex_oauth_error" not in st.session_state:
        st.session_state["yandex_oauth_error"] = "Не удалось сохранить подключение Яндекса."

    clear_query_params()
    st.rerun()


handle_yandex_oauth_callback()

if not get_current_user():
    show_auth_page()
    st.stop()

current_user = get_current_user()

# ==================================================
# HEADER
# ==================================================

st.markdown('<div class="ts-page-title">TechSEO Monitor</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="ts-page-subtitle">Понятный мониторинг технического SEO, индексации, ошибок и мета-тегов для владельца бизнеса</div>',
    unsafe_allow_html=True
)

# ==================================================
# SIDEBAR
# ==================================================

st.sidebar.markdown("## Навигация")
st.sidebar.caption(f"Вы вошли как {current_user.get('name') or current_user['email']}")

if st.sidebar.button("Выйти", use_container_width=True):
    logout()

st.sidebar.divider()
st.sidebar.caption("Основные разделы")

menu = st.sidebar.radio(
    "Раздел",
    [
        "Главная",
        "Мои сайты",
        "Ежемесячный аудит",
        "Ежеквартальный аудит",
        "AI помощник",
        "История проверок",
        "Настройки"
    ],
    label_visibility="collapsed",
    key="main_menu"
)

st.sidebar.divider()
st.sidebar.caption("TechSEO Monitor - спокойный SEO-контроль")

# ==================================================
# ROUTING
# ==================================================

if menu == "Главная":
    show_dashboard()
elif menu == "Мои сайты":
    show_sites_page()
elif menu == "Ежемесячный аудит":
    show_monthly_audit_page()
elif menu == "Ежеквартальный аудит":
    show_quarterly_audit_page()
elif menu == "AI помощник":
    show_meta_generator_page()
elif menu == "История проверок":
    show_history_page()
elif menu == "Настройки":
    st.header("Настройки")
    st.info("Раздел настроек будет стабилизирован на отдельном этапе.")
