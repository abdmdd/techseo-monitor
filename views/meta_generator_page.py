from html import escape

import streamlit as st

from services.ai_service import correct_text_with_yandexgpt, generate_meta_variants, yandex_gpt_available


def section_header(title, subtitle):
    st.markdown(
        f"""
        <div class="ts-dashboard-section">
            <div class="ts-section-title">{escape(title)}</div>
            <div class="ts-section-subtitle">{escape(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
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
        unsafe_allow_html=True,
    )


def output_block(label, text):
    st.markdown(
        f"""
        <div class="ts-ai-output">
            <div class="ts-ai-output-label">{escape(label)}</div>
            <div class="ts-ai-output-text">{escape(text)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_meta_generator():
    section_header(
        "Генератор meta-тегов",
        "YandexGPT генерирует SEO title и description: короткие, длинные, balanced и emoji-варианты.",
    )

    col1, col2 = st.columns(2)

    with col1:
        topic = st.text_input("Тема страницы", placeholder="SEO аудит интернет-магазина")
    with col2:
        url = st.text_input("URL", placeholder="https://example.ru/catalog")

    tone = st.segmented_control(
        "Тип варианта",
        ["Короткий", "Длинный", "С emoji", "Сбалансированный"],
        default="Сбалансированный",
    )

    if st.button("Сгенерировать варианты meta", type="primary", use_container_width=True):
        with st.spinner("Генерируем варианты через YandexGPT..."):
            st.session_state.ai_meta_result = {
                "tone": tone,
                **generate_meta_variants(topic, url, tone),
            }

    result = st.session_state.get("ai_meta_result")

    if not result:
        st.info("Укажите тему и URL, затем запустите генерацию. Если YandexGPT недоступен, платформа покажет fallback-варианты.")
        return

    if result.get("ok"):
        st.success(result.get("message", "Сгенерировано через YandexGPT."))
    else:
        st.warning(result.get("message", "YandexGPT недоступен, показан fallback."))

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
        "Подготовка промптов для визуальных SEO-задач, скриншотов страниц и креативных брифов.",
    )

    uploaded = st.file_uploader("Загрузить изображение", type=["png", "jpg", "jpeg", "webp"])
    prompt_context = st.text_area(
        "Контекст промпта",
        placeholder="Опишите, что нейросеть должна проанализировать или создать...",
        height=120,
    )

    if st.button("Сгенерировать промпт", type="primary", use_container_width=True):
        source = uploaded.name if uploaded else "загруженное изображение"
        context = prompt_context.strip() or "скриншот SEO-страницы"
        st.session_state.generated_prompt = (
            f"Проанализируй {source} как {context}. Найди проблемы визуальной иерархии, "
            "конверсионных блоков, SEO-контента, доверия, понятности CTA и мобильной версии. "
            "Верни рекомендации по приоритету."
        )

    prompt = st.session_state.get("generated_prompt", "")

    if prompt:
        st.text_area("Готовый промпт", value=prompt, height=150)

        if st.button("Скопировать промпт", use_container_width=True):
            st.toast("Промпт готов в поле выше.")
    else:
        st.info("Загрузка изображения пока работает как UI-заготовка. Генерация промпта остаётся локальной.")


def show_grammar_checker():
    section_header(
        "Проверка текста",
        "YandexGPT исправляет орфографию, пунктуацию и явные опечатки в SEO-текстах.",
    )

    source_text = st.text_area(
        "Текст для проверки",
        placeholder="Введите текст для проверки орфографии и пунктуации...",
        height=160,
    )

    if st.button("Проверить текст", type="primary", use_container_width=True):
        with st.spinner("Проверяем текст через YandexGPT..."):
            st.session_state.corrected_text = correct_text_with_yandexgpt(source_text)

    result = st.session_state.get("corrected_text")

    if result and result.get("corrected"):
        if result.get("ok"):
            st.success(result.get("message", "Текст проверен через YandexGPT."))
        else:
            st.warning(result.get("message", "YandexGPT недоступен, применена простая fallback-правка."))

        output_block("Исправленная версия", result["corrected"])
    else:
        st.info("Вставьте текст и запустите проверку. Если API недоступен, интерфейс не упадёт и покажет fallback.")


def show_ai_helper():
    section_header(
        "SEO-помощник",
        "Monthly Audit использует YandexGPT для кратких рекомендаций по результатам аудита, а при ошибке API возвращает локальные подсказки.",
    )

    cols = st.columns(3)

    helpers = [
        ("AI", "Краткие выводы", "Понятные рекомендации по аудиту без технического шума."),
        ("SEO", "Приоритеты", "Помогает понять, какие ошибки исправлять первыми."),
        ("TXT", "Контент", "Связывает meta generation и проверку текста в один рабочий процесс."),
    ]

    for column, (icon, title, text) in zip(cols, helpers):
        with column:
            ai_feature_card(icon, title, text)


def show_meta_generator_page():
    status_text = "YandexGPT подключен" if yandex_gpt_available() else "Нужны ключи в .env"

    st.markdown(
        f"""
        <div class="ts-ai-hero">
            <div>
                <div class="ts-saas-hero-title">Нейросети</div>
                <div class="ts-saas-hero-subtitle">
                    Генерация meta-тегов, проверка текста и SEO-помощник на базе YandexGPT.
                </div>
            </div>
            <div class="ts-saas-pill">{escape(status_text)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    feature_cols = st.columns(4)
    features = [
        ("✎", "Генератор meta", "Title, description и варианты сниппетов."),
        ("▣", "Генератор промптов", "Промпты для визуальных и SEO-задач."),
        ("✓", "Проверка текста", "Орфография, пунктуация и аккуратная редактура."),
        ("AI", "SEO-помощник", "Краткие рекомендации по аудиту."),
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
