import streamlit as st

from components.broken_links_block import show_broken_links_block
from components.canonical_block import show_canonical_block
from components.errors_block import show_detailed_errors
from components.meta_block import show_meta_block
from components.pagination_block import show_pagination_block
from components.redirects_block import show_redirects_block
from components.robots_block import show_robots_block
from components.sitemap_block import show_sitemap_block
from components.ui_helpers import (
    metric_card,
    page_header,
    recommendation_card,
    risk_card,
    warnings_block,
)
from components.yandex_block import show_yandex_webmaster_block
from database.db import get_sites
from services.ai_service import generate_ai_recommendations
from services.audit_service import run_quarterly_audit
from services.history_service import save_audit_history
from services.report_service import generate_report_summary
from services.score_service import get_score_risk
from views.auth_page import require_user_id


def select_site_from_db(label):
    sites = get_sites(user_id=require_user_id())

    if sites:
        site_options = {
            f"{site[1]} — {site[2]}": site
            for site in sites
        }

        selected_site_label = st.selectbox(label, list(site_options.keys()))
        return site_options[selected_site_label]

    st.warning("Сначала добавьте сайт во вкладке 'Мои сайты'.")

    manual_url = st.text_input(
        "Введите URL сайта вручную",
        "https://example.ru"
    )

    return (
        None,
        "Ручной сайт",
        manual_url,
        "",
        "",
        "",
        "",
        "",
        ""
    )


def show_quarterly_audit_page():
    page_header(
        "Ежеквартальный аудит",
        "Расширенный технический срез с тем же стабильным crawler и score layer."
    )

    selected_site = select_site_from_db("Выберите сайт для квартального аудита")
    url = selected_site[2]

    if st.button("Запустить ежеквартальный аудит", type="primary"):
        with st.status("Подготовка квартального аудита", expanded=True) as status:
            st.write("Запускаем crawler и расширенный набор проверок.")
            audit_data = run_quarterly_audit(url)
            status.update(label="Квартальный аудит завершен", state="complete")

        result = audit_data["result"]
        score = audit_data["score"]
        errors_count = audit_data["errors_count"]
        advanced_checks = audit_data["advanced_checks"]

        save_audit_history(
            url=url,
            audit_type="Ежеквартальный аудит",
            result=result,
            score=score,
            errors_count=errors_count,
            user_id=require_user_id()
        )

        st.success("Ежеквартальный аудит завершен и сохранен в историю")

        st.subheader("Общая оценка сайта")
        score_risk = get_score_risk(score)

        col1, col2, col3 = st.columns(3)

        with col1:
            metric_card("SEO Health Score", f"{score}/100", "Единая оценка аудита", "#2563eb")
        with col2:
            metric_card("Ошибок найдено", errors_count, "По результатам crawler", "#dc2626")
        with col3:
            risk_card(score, score_risk["risk"], score_risk["color"])

        warnings_block(result.get("crawler_warnings", []))

        st.divider()

        st.subheader("AI-анализ")
        summary = generate_report_summary(score, errors_count)
        st.info(summary)

        recommendations = generate_ai_recommendations(result)

        if recommendations:
            st.subheader("AI-рекомендации")

            for recommendation in recommendations:
                recommendation_card(recommendation)

        st.divider()

        st.subheader("Расширенные проверки")

        for check_name, check_value in advanced_checks.items():
            st.markdown(f"**{check_name}:** {check_value}")

        st.divider()

        with st.expander("Индексация и поисковые интеграции", expanded=True):
            show_yandex_webmaster_block(url)
            show_sitemap_block(url, result)
            show_robots_block(url, result)

        with st.expander("Meta, canonical и структура страницы", expanded=True):
            show_meta_block(result)
            show_canonical_block(result)
            show_pagination_block(result)

        with st.expander("Ссылки и редиректы", expanded=False):
            show_broken_links_block(result)
            show_redirects_block(result)

        with st.expander("Ошибки и технические детали", expanded=True):
            show_detailed_errors(result)
