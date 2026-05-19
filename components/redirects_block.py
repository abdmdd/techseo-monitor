import streamlit as st


def show_redirects_block(result):
    st.subheader("8. Редиректы главной страницы")

    redirects = result.get("homepage_redirects", [])

    if not redirects:
        st.info("Редиректы не проверялись")
        st.divider()
        return

    for item in redirects:
        status = item.get("status")
        url = item.get("url")
        location = item.get("location", "")

        if status in [301, 302, 308]:
            st.success(f"{url} → {status} {location}")
        else:
            st.warning(f"{url} → {status}")

    st.divider()
