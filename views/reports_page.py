import streamlit as st

from components.ui_helpers import page_header, warnings_block
from crawlers.seo_crawler import check_technical_seo
from services.ai_service import generate_ai_recommendations
from services.report_service import generate_pdf_report
from services.score_service import calculate_seo_score, get_errors_count


def show_reports_page():
    page_header(
        "PDF SEO-отчеты",
        "Быстрая генерация PDF на основе текущего crawler и единого SEO score."
    )

    url = st.text_input(
        "Введите URL сайта",
        "https://example.ru"
    )

    if st.button("Сгенерировать PDF-отчет", type="primary"):
        with st.status("Создаем PDF-отчет", expanded=True) as status:
            st.write("Запускаем аудит сайта.")
            result = check_technical_seo(url)
            errors_count = get_errors_count(result)
            score = calculate_seo_score(result)
            recommendations = generate_ai_recommendations(result)
            st.write("Формируем PDF-файл.")

            pdf_file = generate_pdf_report(
                url=url,
                score=score,
                errors_count=errors_count,
                recommendations=recommendations
            )
            status.update(label="PDF-отчет готов", state="complete")

        st.success("PDF-отчет успешно создан")
        st.caption(f"SEO Score: {score}/100 · Ошибок: {errors_count}")
        warnings_block(result.get("crawler_warnings", []))

        with open(pdf_file, "rb") as file:
            st.download_button(
                label="Скачать PDF",
                data=file,
                file_name=pdf_file,
                mime="application/pdf"
            )
