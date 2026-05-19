import os

import streamlit as st
from dotenv import load_dotenv

from integrations.yandex_webmaster import get_yandex_webmaster_data


load_dotenv()
YANDEX_WEBMASTER_TOKEN = os.getenv("YANDEX_WEBMASTER_TOKEN")


def get_host_id_from_url(url):
    return (
        url.replace("https://", "")
        .replace("http://", "")
        .replace("www.", "")
        .replace("/", "")
    )


def show_yandex_webmaster_block(url):
    st.subheader("1. Яндекс Вебмастер и Google Search Console")

    host_id = get_host_id_from_url(url)

    if not YANDEX_WEBMASTER_TOKEN:
        st.warning("OAuth-токен Яндекс Вебмастера не найден в .env")
    else:
        yandex_data = get_yandex_webmaster_data(
            oauth_token=YANDEX_WEBMASTER_TOKEN,
            host_id=host_id
        )

        if yandex_data["success"]:
            st.success("Подключение к Яндекс Вебмастеру выполнено")

            summary_data = yandex_data.get("summary")

            if summary_data and summary_data.get("success"):
                summary = summary_data["data"]

                sqi = summary.get("sqi", "-")
                pages_count = summary.get("searchable_pages_count", "-")
                excluded_pages = summary.get("excluded_pages_count", "-")
                site_problems = summary.get("site_problems", {})
                problems_count = len(site_problems) if isinstance(site_problems, dict) else 0

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric("ИКС", sqi)
                with col2:
                    st.metric("Страниц в поиске", pages_count)
                with col3:
                    st.metric("Исключено страниц", excluded_pages)
                with col4:
                    st.metric("Проблем", problems_count)

                with st.expander("Полный ответ Вебмастера"):
                    st.json(summary)
            else:
                st.error("Не удалось получить сводку Яндекс Вебмастера")

            diagnostics_data = yandex_data.get("diagnostics")

            st.divider()
            st.subheader("Диагностика сайта")

            if diagnostics_data and diagnostics_data.get("success"):
                diagnostics = diagnostics_data.get("data", {})
                problems = diagnostics.get("problems", {}) if isinstance(diagnostics, dict) else {}
                active_problems = {
                    key: value for key, value in problems.items()
                    if isinstance(value, dict) and value.get("state") != "ABSENT"
                }

                if active_problems:
                    st.warning(f"Активных проблем: {len(active_problems)}")

                    with st.expander("Активные проблемы Вебмастера"):
                        st.json(active_problems)
                else:
                    st.success("Активных проблем в диагностике не найдено")
            else:
                st.error("Не удалось получить диагностику сайта")

        else:
            st.error("Ошибка подключения к Яндекс Вебмастеру")
            st.code(yandex_data.get("error"))

    st.divider()
    st.subheader("Google Search Console")
    st.info("Google Search Console пока не подключен.")
    st.divider()
