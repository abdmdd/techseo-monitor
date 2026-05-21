import pandas as pd
import streamlit as st

from components.ui_helpers import page_header
from database.db import get_audit_history
from views.auth_page import require_user_id


def show_history_page():
    page_header(
        "История аудитов",
        "Здесь собраны последние проверки сайтов без лишних графиков и технического шума."
    )

    history = get_audit_history(user_id=require_user_id())

    if not history:
        st.info("История пока пустая. Запустите первый аудит, и здесь появятся результаты.")
        return

    df = pd.DataFrame(
        history,
        columns=[
            "ID",
            "URL",
            "Тип аудита",
            "SEO-оценка",
            "Ошибок",
            "Title",
            "Description",
            "Canonical",
            "H1",
            "Robots",
            "Sitemap",
            "Дата",
        ],
    )

    visible_df = df[["URL", "Тип аудита", "Ошибок", "Дата"]].copy()

    st.subheader("Последние проверки")
    st.dataframe(visible_df, width="stretch", hide_index=True, height=420)
