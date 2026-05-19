import streamlit as st


def show_meta_block(result):
    st.subheader("4. Мета-теги на странице")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Основные параметры")

        st.write("**Title:**")
        st.code(result.get("title", "—"))

        st.write("**Длина Title:**", result.get("title_length", 0))

        st.write("**Description:**")
        st.code(result.get("description", "—"))

        st.write("**Длина Description:**", result.get("description_length", 0))

        st.write("**H1:**")
        st.code(result.get("h1", "—"))

    with col2:
        st.markdown("### Дубли Title / Description")

        crawled_pages_count = result.get("crawled_pages_count", 0)
        duplicate_titles = result.get("duplicate_titles", {})
        duplicate_descriptions = result.get("duplicate_descriptions", {})

        st.write("**Проверено страниц:**", crawled_pages_count)
        st.write("**Дублей Title:**", len(duplicate_titles))
        st.write("**Дублей Description:**", len(duplicate_descriptions))

        if duplicate_titles:
            with st.expander("Найденные дубли Title"):
                for title, pages in duplicate_titles.items():
                    st.error(title)
                    for page in pages:
                        st.write(page)

        if duplicate_descriptions:
            with st.expander("Найденные дубли Description"):
                for description, pages in duplicate_descriptions.items():
                    st.error(description)
                    for page in pages:
                        st.write(page)

        if not duplicate_titles and not duplicate_descriptions:
            st.success("Дубли Title и Description не найдены")

    st.divider()
