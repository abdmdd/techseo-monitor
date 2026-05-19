import pandas as pd
import streamlit as st

from components.ui_helpers import metric_card, page_header
from database.db import get_audit_history
from views.auth_page import require_user_id


def show_history_page():
    page_header(
        "История SEO-аудитов",
        "Сохраненные проверки, динамика score и количество найденных ошибок."
    )

    history = get_audit_history(user_id=require_user_id())

    if not history:
        st.info("История аудитов пока пуста.")
        return

    df = pd.DataFrame(
        history,
        columns=[
            "ID",
            "URL",
            "Тип аудита",
            "SEO Score",
            "Ошибок",
            "Title",
            "Description",
            "Canonical",
            "H1",
            "Robots",
            "Sitemap",
            "Дата"
        ]
    )

    latest_score = df.iloc[0]["SEO Score"]
    average_score = round(df["SEO Score"].mean(), 1)
    max_score = df["SEO Score"].max()

    col1, col2, col3 = st.columns(3)

    with col1:
        metric_card("Последний SEO Score", latest_score, "Свежий аудит", "#2563eb")
    with col2:
        metric_card("Средний SEO Score", average_score, "По всей истории", "#0f766e")
    with col3:
        metric_card("Лучший SEO Score", max_score, "Максимальное значение", "#16a34a")

    st.divider()
    st.subheader("Последние аудиты")
    st.dataframe(df, width="stretch", height=360, hide_index=True)

    st.divider()
    st.subheader("Динамика SEO Health Score")
    score_chart = df[["Дата", "SEO Score"]].copy().sort_values(by="Дата")
    st.line_chart(score_chart.set_index("Дата"), height=260)

    st.divider()
    st.subheader("Динамика ошибок")
    error_chart = df[["Дата", "Ошибок"]].copy().sort_values(by="Дата")
    st.line_chart(error_chart.set_index("Дата"), height=240)
