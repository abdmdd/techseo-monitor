from html import escape

import streamlit as st


def show_detailed_errors(result):
    st.subheader("9. Ошибки и рекомендации")

    errors = result.get("errors", [])
    recommendations = result.get("recommendations", [])

    if errors:
        st.markdown("#### Найденные ошибки")
        for error in errors:
            st.markdown(
                f"""
                <div class="ts-rec-card" style="border-left-color:#dc2626;">
                    <div class="ts-rec-title">Ошибка</div>
                    <div class="ts-rec-body">{escape(str(error))}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
    else:
        st.success("Критические ошибки не найдены")

    if recommendations:
        st.markdown("#### Рекомендации")
        for recommendation in recommendations:
            st.markdown(
                f"""
                <div class="ts-rec-card" style="border-left-color:#2563eb;">
                    <div class="ts-rec-title">Рекомендация</div>
                    <div class="ts-rec-body">{escape(str(recommendation))}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

    st.divider()
