import streamlit as st


def show_canonical_block(result):
    st.subheader("5. Canonical")

    canonical = result.get("canonical", "—")

    if canonical and canonical != "Нет canonical":
        st.success("Canonical найден")
        st.code(canonical)
    else:
        st.error("Canonical отсутствует")

    st.divider()
