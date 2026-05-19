import streamlit as st


def show_sitemap_block(url, result):
    st.subheader("2. Sitemap.xml")

    st.write("**Сайт:**", url)
    st.write("**Статус:**", result.get("sitemap", "Не проверено"))
    st.write("**Валидность XML:**", result.get("sitemap_valid", "—"))
    st.write("**Тип sitemap:**", result.get("sitemap_type", "—"))
    st.write("**URL в sitemap:**", result.get("sitemap_urls_count", 0))
    st.write("**Lastmod:**", result.get("sitemap_lastmod", "—"))
    st.write("**Пустой sitemap:**", result.get("sitemap_empty", "—"))

    if result.get("sitemap") == "✅ Найден":
        st.success("Sitemap.xml найден")
    elif result.get("sitemap") == "❌ Не найден":
        st.error("Sitemap.xml не найден")
    else:
        st.info("Sitemap.xml не проверен или недоступен")

    st.divider()
