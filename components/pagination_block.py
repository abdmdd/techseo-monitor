import streamlit as st


def show_pagination_block(result):
    st.subheader("6. Пагинация")

    st.write("**Статус:**", result.get("pagination_status", "Не проверено"))
    st.write("**Страниц пагинации найдено:**", result.get("pagination_pages_count", 0))

    pagination_errors = result.get("pagination_errors", [])
    pagination_pages = result.get("pagination_pages", [])

    if pagination_errors:
        for error in pagination_errors:
            st.error(error)

    if pagination_pages:
        with st.expander("Страницы пагинации"):
            for page in pagination_pages:
                st.write(page.get("url"))
                st.caption(f"Canonical: {page.get('canonical_status')}")

    if not pagination_errors:
        st.success("Критических ошибок пагинации не найдено")

    st.divider()
