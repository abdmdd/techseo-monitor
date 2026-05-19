import pandas as pd
import streamlit as st

from components.ui_helpers import compact_note, metric_card, page_header, risk_card
from database.db import get_audit_history, get_sites
from services.score_service import get_score_risk


def show_dashboard():
    page_header(
        "SEO Dashboard",
        "Общий мониторинг технического SEO: динамика, последние аудиты и текущий риск."
    )

    sites = get_sites()
    history = get_audit_history()

    sites_count = len(sites)
    audits_count = len(history)

    if history:
        latest_score = history[0][3]
        latest_errors = history[0][4]
    else:
        latest_score = 0
        latest_errors = 0

    score_risk = get_score_risk(latest_score)
    risk = score_risk["risk"]
    risk_color = score_risk["color"]

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        metric_card("SEO Score", f"{latest_score}/100", "Последний аудит", "#2563eb")
    with col2:
        metric_card("Сайтов", sites_count, "В мониторинге", "#0f766e")
    with col3:
        metric_card("Аудитов", audits_count, f"Ошибок в последнем: {latest_errors}", "#7c3aed")
    with col4:
        risk_card(latest_score, risk, risk_color)

    st.divider()
    st.subheader("AI SEO Assistant")
    compact_note(
        "Модуль собирает технические ошибки, sitemap.xml, robots.txt, canonical, "
        "редиректы, meta tags, пагинацию и базовые признаки индексации."
    )

    if history:
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
        st.subheader("Динамика SEO Score")
        chart_df = df[["Date", "SEO Score"]].copy().sort_values(by="Date")
        st.line_chart(chart_df.set_index("Date"), height=260)

        st.divider()
        st.subheader("Последние аудиты")
        latest_df = df[["URL", "Audit Type", "SEO Score", "Errors", "Date"]]
        st.dataframe(latest_df, width="stretch", height=320, hide_index=True)
    else:
        st.divider()
        st.subheader("Последние аудиты")
        st.info("Аудитов пока нет.")
