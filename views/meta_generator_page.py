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
        "AI Meta Generator",
        "Generate SEO titles, descriptions, emoji variants and short/long options."
    )

    col1, col2 = st.columns(2)

    with col1:
        topic = st.text_input("Topic", placeholder="SEO аудит интернет-магазина")
    with col2:
        url = st.text_input("URL", placeholder="https://example.ru/catalog")

    tone = st.segmented_control(
        "Variant type",
        ["Short", "Long", "Emoji", "Balanced"],
        default="Balanced"
    )

    if st.button("Generate meta variants", type="primary", use_container_width=True):
        result = generate_mock_meta(topic, url)
        st.session_state.ai_meta_result = {
            "tone": tone,
            **result
        }

    result = st.session_state.get("ai_meta_result")

    if not result:
        st.info("Add a topic and URL, then generate mock SEO variants. Backend AI generation will be connected later.")
        return

    title_col, description_col = st.columns(2)

    with title_col:
        st.subheader("SEO Titles")

        for index, title in enumerate(result["titles"], start=1):
            output_block(f"Title variant {index}", title)

    with description_col:
        st.subheader("Descriptions")

        for index, description in enumerate(result["descriptions"], start=1):
            output_block(f"Description variant {index}", description)


def show_prompt_generator():
    section_header(
        "Prompt Generator",
        "Prepare prompts for visual SEO assets, page screenshots and creative briefs."
    )

    uploaded = st.file_uploader("Upload image placeholder", type=["png", "jpg", "jpeg", "webp"])
    prompt_context = st.text_area(
        "Prompt context",
        placeholder="Describe what the AI should analyze or generate...",
        height=120
    )

    if st.button("Generate prompt", type="primary", use_container_width=True):
        source = uploaded.name if uploaded else "uploaded image placeholder"
        context = prompt_context.strip() or "an SEO landing page screenshot"
        st.session_state.generated_prompt = (
            f"Analyze {source} as {context}. Identify visual hierarchy, conversion blocks, SEO content gaps, "
            "trust signals, CTA clarity and mobile layout risks. Return prioritized recommendations."
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
        "Grammar Checker",
        "Mock spelling and punctuation review for SEO snippets and page copy."
    )

    source_text = st.text_area(
        "Text to check",
        placeholder="Введите текст для проверки орфографии и пунктуации...",
        height=160
    )

    if st.button("Check text", type="primary", use_container_width=True):
        st.session_state.corrected_text = mock_correct_text(source_text)

    corrected = st.session_state.get("corrected_text", "")

    if corrected:
        output_block("Corrected version", corrected)
        st.caption("Mock checker: trims spacing, capitalizes first letter and adds final punctuation.")
    else:
        st.info("Paste text and run the checker. Full language model correction will be connected later.")


def show_ai_helper():
    section_header(
        "AI Helper Architecture",
        "Future assistant layer for recommendations, audit explanations and workflow automation."
    )

    cols = st.columns(3)

    helpers = [
        ("SEO Assistant", "Explains audit findings and suggests next actions."),
        ("Recommendation Engine", "Will prioritize crawler, indexing and commercial factor tasks."),
        ("Content Copilot", "Will connect meta generation, grammar checks and page briefs."),
    ]

    for column, (title, text) in zip(cols, helpers):
        with column:
            ai_feature_card("AI", title, text)


def show_meta_generator_page():
    st.markdown(
        """
        <div class="ts-ai-hero">
            <div>
                <div class="ts-saas-hero-title">AI Center</div>
                <div class="ts-saas-hero-subtitle">
                    Meta generation, prompt drafting, grammar checks and future SEO assistant workflows in one workspace.
                </div>
            </div>
            <div class="ts-saas-pill">Mock AI outputs</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    feature_cols = st.columns(4)
    features = [
        ("✎", "Meta Generator", "Titles, descriptions and snippet variants."),
        ("▣", "Prompt Generator", "Reusable prompts for visual and SEO tasks."),
        ("✓", "Grammar Checker", "Copy cleanup and punctuation checks."),
        ("AI", "SEO Assistant", "Future recommendation architecture."),
    ]

    for column, feature in zip(feature_cols, features):
        with column:
            ai_feature_card(*feature)

    tab_meta, tab_prompt, tab_grammar, tab_helper = st.tabs([
        "AI Meta Generator",
        "Prompt Generator",
        "Grammar Checker",
        "AI Helper",
    ])

    with tab_meta:
        show_meta_generator()

    with tab_prompt:
        show_prompt_generator()

    with tab_grammar:
        show_grammar_checker()

    with tab_helper:
        show_ai_helper()
