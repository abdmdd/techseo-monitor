import streamlit as st


def show_broken_links_block(result):
    st.subheader("7. Битые ссылки")

    st.write("**Проверено внутренних ссылок:**", result.get("internal_links_total", 0))
    st.write("**Найдено битых ссылок:**", result.get("broken_links_total", 0))

    broken_links = result.get("broken_links", [])

    if broken_links:
        for link in broken_links:
            st.error(f"{link.get('url')} — {link.get('status_code')}")
    else:
        st.success("Битые ссылки не найдены")

    st.divider()
