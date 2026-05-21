from html import escape

import streamlit as st


def section_header(title, subtitle):
    st.markdown(
        f"""
        <div class="ts-dashboard-section">
            <div class="ts-section-title">{escape(title)}</div>
            <div class="ts-section-subtitle">{escape(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def ai_feature_card(icon, title, text):
    st.markdown(
        f"""
        <div class="ts-ai-card">
            <div class="ts-action-icon">{escape(icon)}</div>
            <div class="ts-card-title">{escape(title)}</div>
            <div class="ts-card-text">{escape(text)}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def output_block(label, text):
    st.markdown(
        f"""
        <div class="ts-ai-output">
            <div class="ts-ai-output-label">{escape(label)}</div>
            <div class="ts-ai-output-text">{escape(text)}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def generate_mock_meta(topic, url):
    clean_topic = topic.strip() or "SEO аудит сайта"
    clean_url = url.strip() or "https://example.ru"

    return {
        "titles": [
            f"{clean_topic}: технический SEO-аудит и рост видимости",
            f"Проверка SEO для {clean_topic} - ошибки, индексация, рекомендации",
            f"🚀 {clean_topic}: быстрый SEO-анализ и план улучшений",
            f"{clean_topic} | Полный аудит сайта и поисковых факторов",
        ],
        "descriptions": [
            f"Проверьте {clean_topic.lower()} на технические ошибки, индексацию, meta tags, redirects и broken links. Получите понятный SEO-план.",
            f"SEO-анализ страницы {clean_url}: title, description, H1, canonical, sitemap, robots и рекомендации для роста органики.",
            f"✨ Улучшите {clean_topic.lower()} с помощью AI-рекомендаций, crawler-сигналов и понятного списка приоритетов.",
            f"Короткий аудит {clean_topic.lower()}: находим ошибки, объясняем риски и подсказываем, что исправить в первую очередь.",
        ],
    }


def show_meta_generator():
    section_header(
        "Генератор meta-тегов",
        "Создавайте SEO title, description, короткие, длинные и более выразительные варианты."
    )

    col1, col2 = st.columns(2)

    with col1:
        topic = st.text_input("Тема страницы", placeholder="SEO аудит интернет-магазина")
    with col2:
        url = st.text_input("URL", placeholder="https://example.ru/catalog")

    tone = st.segmented_control(
        "Тип варианта",
        ["Короткий", "Длинный", "С emoji", "Сбалансированный"],
        default="Сбалансированный"
    )

    if st.button("Сгенерировать варианты meta", type="primary", use_container_width=True):
        result = generate_mock_meta(topic, url)
        st.session_state.ai_meta_result = {
            "tone": tone,
            **result
        }

    result = st.session_state.get("ai_meta_result")

    if not result:
        st.info("Укажите тему и URL, затем сгенерируйте демо-варианты. Реальная AI-генерация будет подключена позже.")
        return

    title_col, description_col = st.columns(2)

    with title_col:
        st.subheader("SEO-заголовки")

        for index, title in enumerate(result["titles"], start=1):
            output_block(f"Вариант title {index}", title)

    with description_col:
        st.subheader("Описания")

        for index, description in enumerate(result["descriptions"], start=1):
            output_block(f"Вариант description {index}", description)


def show_prompt_generator():
    section_header(
        "Генератор промптов",
        "Готовьте промпты для визуальных SEO-задач, скриншотов страниц и творческих брифов."
    )

    uploaded = st.file_uploader("Загрузить изображение", type=["png", "jpg", "jpeg", "webp"])
    prompt_context = st.text_area(
        "Контекст промпта",
        placeholder="Опишите, что нейросеть должна проанализировать или создать...",
        height=120
    )

    if st.button("Сгенерировать промпт", type="primary", use_container_width=True):
        source = uploaded.name if uploaded else "загруженное изображение"
        context = prompt_context.strip() or "скриншот SEO-страницы"
        st.session_state.generated_prompt = (
            f"Проанализируй {source} как {context}. Найди проблемы визуальной иерархии, конверсионных блоков, "
            "SEO-контента, доверия, понятности CTA и мобильной верстки. Верни рекомендации по приоритету."
        )

    prompt = st.session_state.get("generated_prompt", "")

    if prompt:
        st.text_area("Generated prompt", value=prompt, height=150)

        if st.button("Copy prompt", use_container_width=True):
            st.toast("Prompt is ready to copy from the text area.")
    else:
        st.info("Upload placeholder is UI-only for now. Prompt generation uses mock output.")


def mock_correct_text(text):
    if not text.strip():
        return ""

    corrected = text.strip()
    corrected = corrected.replace("  ", " ")

    if corrected and corrected[-1] not in ".!?":
        corrected += "."

    return corrected[0].upper() + corrected[1:] if corrected else corrected


def show_grammar_checker():
    section_header(
        "Проверка текста",
        "Демо-проверка орфографии и пунктуации для SEO-текстов и описаний страниц."
    )

    source_text = st.text_area(
        "Текст для проверки",
        placeholder="Введите текст для проверки орфографии и пунктуации...",
        height=160
    )

    if st.button("Проверить текст", type="primary", use_container_width=True):
        st.session_state.corrected_text = mock_correct_text(source_text)

    corrected = st.session_state.get("corrected_text", "")

    if corrected:
        output_block("Исправленная версия", corrected)
        st.caption("Демо-проверка убирает лишние пробелы, исправляет первую букву и добавляет знак в конце.")
    else:
        st.info("Вставьте текст и запустите проверку. Полная языковая модель будет подключена позже.")


def show_ai_helper():
    section_header(
        "Архитектура SEO-помощника",
        "Будущий слой подсказок, объяснений аудита и автоматизации рабочих задач."
    )

    cols = st.columns(3)

    helpers = [
        ("SEO-помощник", "Объяснит результаты аудита и подскажет следующий шаг."),
        ("Умные рекомендации", "Поможет расставить приоритеты по ошибкам и задачам."),
        ("Помощник по контенту", "Свяжет генерацию meta, проверку текста и брифы страниц."),
    ]

    for column, (title, text) in zip(cols, helpers):
        with column:
            ai_feature_card("AI", title, text)


def show_meta_generator_page():
    st.markdown(
        """
        <div class="ts-ai-hero">
            <div>
                <div class="ts-saas-hero-title">Нейросети</div>
                <div class="ts-saas-hero-subtitle">
                    Генерация meta-тегов, подготовка промптов, проверка текста и будущий SEO-помощник в одном разделе.
                </div>
            </div>
            <div class="ts-saas-pill">Демо-ответы</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    feature_cols = st.columns(4)
    features = [
        ("✎", "Генератор meta", "Title, description и варианты сниппетов."),
        ("▣", "Генератор промптов", "Промпты для визуальных и SEO-задач."),
        ("✓", "Проверка текста", "Уборка лишних пробелов и пунктуация."),
        ("AI", "SEO-помощник", "Архитектура будущих рекомендаций."),
    ]

    for column, feature in zip(feature_cols, features):
        with column:
            ai_feature_card(*feature)

    tab_meta, tab_prompt, tab_grammar, tab_helper = st.tabs([
        "Генератор meta",
        "Генератор промптов",
        "Проверка текста",
        "SEO-помощник",
    ])

    with tab_meta:
        show_meta_generator()

    with tab_prompt:
        show_prompt_generator()

    with tab_grammar:
        show_grammar_checker()

    with tab_helper:
        show_ai_helper()
