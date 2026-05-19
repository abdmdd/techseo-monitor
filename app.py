import os
import sys

import streamlit as st
from dotenv import load_dotenv

# ==================================================
# PATH
# ==================================================

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ==================================================
# DATABASE / UI
# ==================================================

from components.ui_helpers import apply_global_styles
from database.db import init_db

# ==================================================
# VIEWS
# ==================================================

from views.auth_page import get_current_user, init_auth_state, logout, show_auth_page
from views.dashboard_page import show_dashboard
from views.history_page import show_history_page
from views.meta_generator_page import show_meta_generator_page
from views.monthly_audit_page import show_monthly_audit_page
from views.quarterly_audit_page import show_quarterly_audit_page
from views.reports_page import show_reports_page
from views.sites_page import show_sites_page

# ==================================================
# INIT
# ==================================================

init_db()
load_dotenv()

# ==================================================
# PAGE CONFIG
# ==================================================

st.set_page_config(
    page_title="TechSEO Monitor",
    page_icon="TS",
    layout="wide"
)

# ==================================================
# GLOBAL UI / AUTH GATE
# ==================================================

apply_global_styles()
init_auth_state()

if not get_current_user():
    show_auth_page()
    st.stop()

current_user = get_current_user()

# ==================================================
# HEADER
# ==================================================

st.markdown('<div class="ts-page-title">TechSEO Monitor</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="ts-page-subtitle">Автоматический мониторинг технического SEO, индексации, отзывов и мета-тегов</div>',
    unsafe_allow_html=True
)

# ==================================================
# SIDEBAR
# ==================================================

st.sidebar.markdown("## Навигация")
st.sidebar.caption(f"Вы вошли как {current_user['email']}")

if st.sidebar.button("Выйти", use_container_width=True):
    logout()

st.sidebar.divider()
st.sidebar.caption("Основные рабочие разделы MVP")

menu = st.sidebar.radio(
    "Раздел",
    [
        "Дашборд",
        "Мои сайты",
        "Ежемесячный аудит",
        "Ежеквартальный аудит",
        "Генерация мета-тегов",
        "История проверок",
        "PDF-отчеты",
        "Настройки"
    ],
    label_visibility="collapsed"
)

st.sidebar.divider()
st.sidebar.caption("TechSEO Monitor - версия для диплома")

# ==================================================
# ROUTING
# ==================================================

if menu == "Дашборд":
    show_dashboard()
elif menu == "Мои сайты":
    show_sites_page()
elif menu == "Ежемесячный аудит":
    show_monthly_audit_page()
elif menu == "Ежеквартальный аудит":
    show_quarterly_audit_page()
elif menu == "Генерация мета-тегов":
    show_meta_generator_page()
elif menu == "История проверок":
    show_history_page()
elif menu == "PDF-отчеты":
    show_reports_page()
elif menu == "Настройки":
    st.header("Настройки")
    st.info("Раздел настроек будет стабилизирован на отдельном этапе.")
