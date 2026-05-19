import pandas as pd
import streamlit as st

from database.db import add_site, get_sites
from views.auth_page import require_user_id


def show_sites_page():
    user_id = require_user_id()

    st.header("Мои сайты")

    st.write("Добавление и хранение сайтов для мониторинга.")

    with st.form("add_site_form"):
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

        google_property = st.text_input(
            "Google Search Console Property",
            placeholder="https://example.ru/"
        )

        st.markdown("### Ссылки на карточки отзывов")

        yandex_reviews_url = st.text_input(
            "Ссылка на Яндекс.Карты",
            placeholder="https://yandex.ru/maps/org/..."
        )

        google_reviews_url = st.text_input(
            "Ссылка на Google Maps",
            placeholder="https://www.google.com/maps/place/..."
        )

        twogis_reviews_url = st.text_input(
            "Ссылка на 2ГИС",
            placeholder="https://2gis.ru/..."
        )

        submitted = st.form_submit_button("Добавить сайт")

        if submitted:
            if not site_name or not site_url:
                st.warning("Заполните название сайта и URL.")
            elif not site_url.startswith("http"):
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
                st.success(f"Сайт добавлен: {site_name}")

    st.divider()
    st.subheader("Список сайтов")

    sites = get_sites(user_id=user_id)

    if sites:
        df = pd.DataFrame(
            sites,
            columns=[
                "ID",
                "Название",
                "URL",
                "Yandex Host",
                "Google Property",
                "Яндекс.Карты",
                "Google Maps",
                "2ГИС",
                "Дата добавления"
            ]
        )

        st.dataframe(df, width="stretch")
    else:
        st.info("Сайтов пока нет.")
