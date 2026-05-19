import streamlit as st


def show_robots_block(url, result):
    st.subheader("3. Robots.txt")

    st.write("**Сайт:**", url)
    st.write("**Статус:**", result.get("robots_txt", "Не проверено"))

    robots_errors = result.get("robots_errors", [])

    if robots_errors:
        st.markdown("### Ошибки robots.txt")
        for error in robots_errors:
            st.error(error)
    else:
        st.success("Критических ошибок robots.txt не найдено")

    robots_content = result.get("robots_content", "")
    if robots_content:
        with st.expander("Содержимое robots.txt"):
            st.code(robots_content, language="text")

    st.divider()
