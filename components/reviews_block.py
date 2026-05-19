import streamlit as st

from crawlers.reviews_crawler import check_reviews


def show_reviews_block(yandex_reviews_url="", google_reviews_url="", twogis_reviews_url=""):
    st.subheader("10. Отзывы на картах")

    if not any([yandex_reviews_url, google_reviews_url, twogis_reviews_url]):
        st.info("Ссылки на карточки отзывов не указаны.")
        st.divider()
        return

    with st.spinner("Проверяем карточки отзывов..."):
        reviews = check_reviews(
            yandex_url=yandex_reviews_url,
            google_url=google_reviews_url,
            twogis_url=twogis_reviews_url
        )

    for item in reviews:
        st.markdown(f"### {item.get('platform')}")
        st.write("**Рейтинг:**", item.get("rating"))
        st.write("**Количество отзывов:**", item.get("reviews_count"))
        st.write("**Статус:**", item.get("status"))

        if item.get("url"):
            st.caption(item.get("url"))

    st.divider()
