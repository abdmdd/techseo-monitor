import streamlit as st

from components.broken_links_block import show_broken_links_block
from components.canonical_block import show_canonical_block
from components.errors_block import show_detailed_errors
from components.meta_block import show_meta_block
from components.pagination_block import show_pagination_block
from components.redirects_block import show_redirects_block
from components.reviews_block import show_reviews_block
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
from services.ai_service import generate_ai_recommendations, generate_ai_summary
from services.audit_service import run_monthly_audit
from services.history_service import save_audit_history
from services.score_service import get_score_risk


def select_site_from_db(label):
    sites = get_sites()

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


def show_monthly_audit_page():
    page_header(
        "Ежемесячный аудит",
        "Быстрая техническая проверка сайта с сохранением результата в историю."
    )

    selected_site = select_site_from_db("Выберите сайт для аудита")

    url = selected_site[2]
    yandex_reviews_url = selected_site[5]
    google_reviews_url = selected_site[6]
    twogis_reviews_url = selected_site[7]

    if st.button("Запустить ежемесячный аудит", type="primary"):
        with st.status("Подготовка аудита", expanded=True) as status:
            st.write("Запускаем crawler и собираем технические сигналы.")
            audit_data = run_monthly_audit(url)
            status.update(label="Аудит завершен", state="complete")

        result = audit_data["result"]
        score = audit_data["score"]
        errors_count = audit_data["errors_count"]

        save_audit_history(
            url=url,
            audit_type="Ежемесячный аудит",
            result=result,
            score=score,
            errors_count=errors_count
        )

        ai_summary = generate_ai_summary(score, errors_count)
        score_risk = get_score_risk(score)

        st.success("Аудит завершен и сохранен в историю")

        st.subheader("AI SEO-анализ")
        st.caption(ai_summary["summary"])

        col1, col2, col3 = st.columns(3)

        with col1:
            metric_card("SEO Score", f"{score}/100", "Единая оценка аудита", "#2563eb")
        with col2:
            metric_card("Ошибок", errors_count, "Найдено crawler", "#dc2626")
        with col3:
            risk_card(score, ai_summary["risk"], score_risk["color"])

        warnings_block(result.get("crawler_warnings", []))

        st.divider()

        recommendations = generate_ai_recommendations(result)

        if recommendations:
            st.subheader("AI-рекомендации")

            for rec in recommendations:
                recommendation_card(rec)

        st.divider()

        with st.expander("Индексация и поисковые интеграции", expanded=True):
            show_yandex_webmaster_block(url)
            show_sitemap_block(url, result)
            show_robots_block(url, result)

        with st.expander("Meta, canonical и структура страницы", expanded=True):
            show_meta_block(result)
            show_canonical_block(result)
            show_pagination_block(result)

        with st.expander("Ссылки, редиректы и отзывы", expanded=False):
            show_broken_links_block(result)
            show_redirects_block(result)
            show_reviews_block(
                yandex_reviews_url=yandex_reviews_url,
                google_reviews_url=google_reviews_url,
                twogis_reviews_url=twogis_reviews_url
            )

        with st.expander("Ошибки и технические детали", expanded=True):
            show_detailed_errors(result)
