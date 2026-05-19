import streamlit as st

from services.ai_service import generate_meta_tags


def show_meta_generator_page():
    st.header("AI-генерация SEO мета-тегов")
    st.write("Автоматическая генерация SEO Title и Description.")

    site_name = st.text_input(
        "Название сайта",
        placeholder="TechSEO Monitor"
    )

    page_topic = st.text_input(
        "Тема страницы",
        placeholder="SEO аудит сайтов"
    )

    keywords = st.text_area(
        "Ключевые слова",
        placeholder="seo аудит, технический аудит сайта, seo мониторинг"
    )

    if st.button("Сгенерировать мета-теги", type="primary"):
        result = generate_meta_tags(site_name, page_topic, keywords)

        st.success("Мета-теги успешно сгенерированы")
        st.divider()

        st.subheader("SEO Title")
        st.code(result["title"], language="text")
        st.caption(f"Длина: {len(result['title'])} символов")

        st.subheader("Meta Description")
        st.code(result["description"], language="text")
        st.caption(f"Длина: {len(result['description'])} символов")

        st.subheader("OpenGraph Title")
        st.code(result["og_title"], language="text")

        st.subheader("OpenGraph Description")
        st.code(result["og_description"], language="text")
