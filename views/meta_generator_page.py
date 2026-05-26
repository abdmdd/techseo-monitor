from html import escape

import pandas as pd
import streamlit as st

from database.db import (
    get_latest_ai_audit_insight,
    get_latest_audit_job,
    get_yandex_traffic_snapshots,
    save_ai_audit_insight,
)
from services.ai_service import (
    generate_ai_audit_insight,
    generate_competitor_analysis,
    generate_text_check_analysis,
    yandex_gpt_available,
)
from views.auth_page import require_user_id
from views.cached_data import cached_get_sites


PRIORITY_LABELS = {
    "critical": "Критично",
    "high": "Высокий",
    "medium": "Средний",
    "low": "Низкий",
}

PRIORITY_CLASSES = {
    "critical": "ts-priority-critical",
    "high": "ts-priority-high",
    "medium": "ts-priority-medium",
    "low": "ts-priority-low",
}


def _inject_ai_hub_styles():
    st.markdown(
        """
        <style>
        .ts-ai-hub-hero {
            padding: 22px 24px;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            background: #ffffff;
            display: flex;
            justify-content: space-between;
            gap: 18px;
            align-items: flex-start;
            margin-bottom: 18px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
        }
        .ts-ai-hub-title {
            font-size: 28px;
            line-height: 1.15;
            font-weight: 800;
            color: #0f172a;
            margin-bottom: 8px;
        }
        .ts-ai-hub-subtitle {
            color: #475569;
            font-size: 15px;
            max-width: 820px;
        }
        .ts-ai-status {
            border-radius: 999px;
            padding: 7px 12px;
            font-size: 13px;
            font-weight: 700;
            white-space: nowrap;
            background: #eef2ff;
            color: #3730a3;
        }
        .ts-ai-card {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            background: #ffffff;
            padding: 16px;
            margin: 8px 0 14px;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.04);
        }
        .ts-ai-card-title {
            font-size: 14px;
            font-weight: 800;
            color: #0f172a;
            margin-bottom: 6px;
        }
        .ts-ai-card-text {
            color: #475569;
            font-size: 14px;
            line-height: 1.45;
        }
        .ts-ai-section-title {
            font-size: 20px;
            font-weight: 800;
            color: #0f172a;
            margin: 22px 0 6px;
        }
        .ts-ai-section-subtitle {
            color: #64748b;
            font-size: 14px;
            margin-bottom: 12px;
        }
        .ts-ai-priority {
            display: inline-flex;
            align-items: center;
            padding: 4px 9px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 800;
            margin-bottom: 8px;
        }
        .ts-priority-critical { background: #fee2e2; color: #991b1b; }
        .ts-priority-high { background: #ffedd5; color: #9a3412; }
        .ts-priority-medium { background: #fef3c7; color: #92400e; }
        .ts-priority-low { background: #dcfce7; color: #166534; }
        .ts-copy-block {
            white-space: pre-wrap;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            background: #f8fafc;
            color: #0f172a;
            padding: 14px;
            font-size: 14px;
            line-height: 1.5;
        }
        .ts-empty-state {
            border: 1px dashed #cbd5e1;
            border-radius: 8px;
            padding: 18px;
            background: #f8fafc;
            color: #475569;
        }
        @media (max-width: 760px) {
            .ts-ai-hub-hero { flex-direction: column; }
            .ts-ai-status { white-space: normal; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _card(title, text):
    st.markdown(
        f"""
        <div class="ts-ai-card">
            <div class="ts-ai-card-title">{escape(str(title))}</div>
            <div class="ts-ai-card-text">{escape(str(text or "Нет данных"))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _section(title, subtitle=""):
    st.markdown(
        f"""
        <div class="ts-ai-section-title">{escape(title)}</div>
        <div class="ts-ai-section-subtitle">{escape(subtitle)}</div>
        """,
        unsafe_allow_html=True,
    )


def _empty_state(title, text):
    st.markdown(
        f"""
        <div class="ts-empty-state">
            <strong>{escape(title)}</strong><br>
            {escape(text)}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _priority_badge(priority):
    normalized = (priority or "medium").lower()
    label = PRIORITY_LABELS.get(normalized, "Средний")
    css_class = PRIORITY_CLASSES.get(normalized, "ts-priority-medium")
    return f'<span class="ts-ai-priority {css_class}">{escape(label)}</span>'


def _copy_block(text):
    st.markdown(
        f'<div class="ts-copy-block">{escape(str(text or ""))}</div>',
        unsafe_allow_html=True,
    )


def _site_options(sites):
    return {f"{site[1]} · {site[2]}": site for site in sites}


def _latest_metrika_snapshot(user_id, site_id):
    snapshots = get_yandex_traffic_snapshots(user_id, site_id=site_id, limit=1)
    if not snapshots:
        return "нет данных"

    snapshot = snapshots[0]
    return {
        "counter_id": snapshot[3],
        "period": f"{snapshot[4]} - {snapshot[5]}",
        "visits": snapshot[6],
        "pageviews": snapshot[7],
        "users": snapshot[8],
        "bounce_rate": snapshot[9],
        "search_visits": snapshot[10],
        "ads_visits": snapshot[11],
    }


def _build_site_info(site, user_id):
    return {
        "id": site[0],
        "name": site[1],
        "url": site[2],
        "yandex_webmaster_summary": "нет сохранённых данных в AI помощнике; используйте сводку Monthly Audit",
        "yandex_metrika_summary": _latest_metrika_snapshot(user_id, site[0]),
    }


def _audit_payload(latest_job):
    if not latest_job:
        return {}
    payload = latest_job.get("result") or {}
    if isinstance(payload, dict):
        payload = dict(payload)
        payload.setdefault("seo_score", latest_job.get("seo_score"))
        payload.setdefault("errors_count", latest_job.get("errors_count"))
    return payload


def _render_summary(insight):
    summary = insight.get("ai_summary") or {}
    _section("AI Summary", "Короткий вывод по состоянию сайта и первые действия.")
    col1, col2 = st.columns(2)
    with col1:
        _card("Общее состояние", summary.get("summary"))
        _card("Что критично", summary.get("critical"))
    with col2:
        _card("Что плохо", summary.get("what_is_bad"))
        _card("Что делать первым", summary.get("first_actions"))


def _render_priority_center(insight):
    problems = insight.get("priority_center") or []
    _section("AI Priority Center", "Проблемы отсортированы по влиянию на индексацию, трафик и качество сниппетов.")
    if not problems:
        _empty_state("Проблемы не найдены", "AI не выделил приоритетных задач по последнему аудиту.")
        return

    for index, item in enumerate(problems, start=1):
        title = item.get("title") or f"Проблема {index}"
        with st.expander(f"{PRIORITY_LABELS.get((item.get('priority') or '').lower(), 'Средний')} · {title}", expanded=index <= 2):
            st.markdown(_priority_badge(item.get("priority")), unsafe_allow_html=True)
            _card("Почему это важно", item.get("why_it_matters"))
            _card("Как исправить", item.get("how_to_fix"))
            urls = [url for url in item.get("affected_urls", []) if url]
            if urls:
                st.markdown("**Затронутые URL**")
                st.dataframe(pd.DataFrame({"URL": urls}), use_container_width=True, hide_index=True)


def _render_tasks(insight):
    tasks = insight.get("tasks") or []
    _section("AI Task Generator", "Готовый чеклист для SEO-специалиста.")
    if not tasks:
        _empty_state("Задач пока нет", "Сформируйте AI-анализ после появления Monthly Audit.")
        return

    rows = [
        {
            "Задача": task.get("task", ""),
            "Приоритет": PRIORITY_LABELS.get((task.get("priority") or "").lower(), task.get("priority", "")),
            "Источник": task.get("source_section", ""),
            "Ожидаемый результат": task.get("expected_result", ""),
        }
        for task in tasks
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_page_analyzer(insight):
    pages = insight.get("page_analyzer") or []
    _section("AI Page Analyzer MVP", "До 10 страниц с проблемами из meta audit.")
    if not pages:
        _empty_state("Страниц с проблемами нет", "AI не нашёл подходящих страниц для точечного разбора.")
        return

    for page in pages:
        label = page.get("url") or "Страница"
        with st.expander(label, expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                _card("Текущий title", page.get("current_title"))
                _card("Текущий description", page.get("current_description"))
                _card("H1", page.get("h1"))
            with col2:
                _card("Улучшенный title", page.get("improved_title"))
                _card("Улучшенный description", page.get("improved_description"))
            problems = page.get("problems") or []
            if problems:
                st.markdown("**Проблемы**")
                st.write("\n".join(f"- {problem}" for problem in problems))
            _card("Комментарий по интенту", page.get("intent_comment"))
            _card("Комментарий по CTR", page.get("ctr_comment"))


def _render_ai_insight(insight, created_at=None):
    if not insight:
        return

    if insight.get("ok"):
        st.success(insight.get("message", "AI-анализ сформирован."))
    else:
        st.warning(insight.get("message", "Показан безопасный fallback-анализ."))

    if created_at:
        st.caption(f"Последний сохранённый AI-анализ: {created_at}")

    _render_summary(insight)
    _render_priority_center(insight)
    _render_tasks(insight)
    _render_page_analyzer(insight)

    tasks_text = "\n".join(
        f"- [{PRIORITY_LABELS.get((task.get('priority') or '').lower(), task.get('priority', ''))}] "
        f"{task.get('task', '')} -> {task.get('expected_result', '')}"
        for task in insight.get("tasks", [])
    )
    with st.expander("Copy-friendly план работ", expanded=False):
        _copy_block(tasks_text or "Задачи пока не сформированы.")


def _show_ai_seo_assistant(user_id):
    sites = cached_get_sites(user_id=user_id)
    if not sites:
        _empty_state("Сайтов пока нет", "Добавьте сайт на странице «Мои сайты», затем вернитесь сюда для AI-анализа.")
        return

    options = _site_options(sites)
    selected_label = st.selectbox("Сайт для AI SEO Assistant", list(options.keys()))
    selected_site = options[selected_label]
    site_id = selected_site[0]
    site_url = selected_site[2]
    latest_job = get_latest_audit_job(user_id, site_url=site_url, audit_type="monthly")
    latest_insight = get_latest_ai_audit_insight(user_id, site_id)

    col1, col2, col3 = st.columns(3)
    with col1:
        _card("Выбранный сайт", f"{selected_site[1]}\n{site_url}")
    with col2:
        _card("Monthly Audit", latest_job.get("status") if latest_job else "нет аудита")
    with col3:
        _card("AI-история", "есть сохранённый результат" if latest_insight else "пока нет")

    if not latest_job or not latest_job.get("result"):
        _empty_state(
            "Нет данных Monthly Audit",
            "Запустите ежемесячный аудит по этому сайту. AI помощник использует последний завершённый результат аудита.",
        )
        return

    button_label = "Перегенерировать AI-анализ" if latest_insight else "Сформировать AI-анализ"
    if st.button(button_label, type="primary", use_container_width=True):
        with st.spinner("Формируем AI-анализ по последнему Monthly Audit..."):
            site_info = _build_site_info(selected_site, user_id)
            insight = generate_ai_audit_insight(_audit_payload(latest_job), site_info)
            save_ai_audit_insight(user_id, site_id, latest_job.get("id"), insight)
            st.session_state[f"ai_hub_latest_{site_id}"] = insight
            st.session_state[f"ai_hub_latest_created_{site_id}"] = "только что"
            st.success("AI-анализ сохранён.")

    active_insight = st.session_state.get(f"ai_hub_latest_{site_id}")
    active_created = st.session_state.get(f"ai_hub_latest_created_{site_id}")
    if not active_insight and latest_insight:
        active_insight = latest_insight.get("summary")
        active_created = latest_insight.get("created_at")

    if active_insight:
        _render_ai_insight(active_insight, active_created)
    else:
        _empty_state(
            "AI-анализ ещё не сформирован",
            "Нажмите кнопку выше: система возьмёт crawl, meta, canonical, robots, sitemap, ссылки, редиректы, отзывы и доступные Яндекс-сводки.",
        )


def _show_competitor_analysis(user_id):
    sites = cached_get_sites(user_id=user_id)
    site_labels = [""] + [f"{site[1]} · {site[2]}" for site in sites]
    selected = st.selectbox("Ваш сайт", site_labels, index=0, key="ai_competitor_site")
    own_site = selected.split(" · ", 1)[1] if " · " in selected else selected
    if not own_site:
        own_site = st.text_input("Ваш сайт", placeholder="https://example.ru", key="ai_competitor_manual_site")
    query = st.text_input("Поисковый запрос", placeholder="Например: загородный отель с бассейном")
    city = st.text_input("Город", placeholder="Например: Самара")
    competitors = st.text_area(
        "Конкуренты вручную, если уже известны",
        placeholder="https://competitor-1.ru\nhttps://competitor-2.ru\nили список названий сайтов",
        height=160,
    )

    if st.button("Сформировать анализ", type="primary", use_container_width=True, key="ai_competitor_button"):
        with st.spinner("Сравниваем конкурентов через YandexGPT..."):
            st.session_state.ai_competitor_result = generate_competitor_analysis(own_site, query, city, competitors)

    result = st.session_state.get("ai_competitor_result")
    if not result:
        _empty_state(
            "MVP без настоящего SERP-парсера",
            "Введите сайт, запрос и город. Если конкурентов не указать вручную, AI сформирует предполагаемый список для первичной SEO-гипотезы.",
        )
        return

    if result.get("ok"):
        st.success(result.get("message", "Анализ сформирован."))
    else:
        st.warning(result.get("message", "Показана базовая структура анализа."))

    st.info(result.get("mvp_notice", "Это MVP-анализ: настоящий SERP-парсер пока не подключён."))

    _section("Основные конкуренты", "Если список не был введён вручную, это предполагаемые конкуренты для первичного анализа.")
    competitors_rows = [{"Конкурент": item} for item in result.get("competitors", [])]
    if competitors_rows:
        st.dataframe(pd.DataFrame(competitors_rows), use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        _section("Чем конкуренты сильнее")
        for item in result.get("competitor_strengths", []):
            _card("Сильная сторона", item)
    with col2:
        _section("Почему они могут быть выше")
        for item in result.get("why_they_rank_higher", []):
            _card("Причина", item)

    _section("Title / H1 / структура / контент")
    for item in result.get("title_h1_structure_content", []):
        _card("Что сравнить", item)

    col3, col4 = st.columns(2)
    with col3:
        _card("Геозапросы", result.get("geo_queries"))
        _card("Коммерческие слова", result.get("commercial_words"))
    with col4:
        blocks = result.get("blocks_check") or {}
        _card("FAQ", blocks.get("faq"))
        _card("Услуги", blocks.get("services"))
        _card("Цены", blocks.get("prices"))
        _card("Контакты", blocks.get("contacts"))

    _section("Что улучшить на нашем сайте")
    for item in result.get("our_improvements", []):
        _card("Улучшение", item)

    _section("Конкретный план действий")
    plan_rows = [{"Шаг": index, "Действие": item} for index, item in enumerate(result.get("action_plan", []), start=1)]
    if plan_rows:
        st.dataframe(pd.DataFrame(plan_rows), use_container_width=True, hide_index=True)
    _card("Вывод", result.get("conclusion"))


def _show_text_check():
    source_text = st.text_area(
        "Текст для проверки",
        placeholder="Вставьте текст страницы, описания услуги, новости или SEO-блока...",
        height=220,
    )
    col1, col2 = st.columns(2)
    with col1:
        text_type = st.selectbox(
            "Тип текста",
            ["письмо", "текст на сайт", "SEO-текст", "пост", "коммерческое предложение"],
        )
    with col2:
        tone = st.selectbox(
            "Тон",
            ["деловой", "дружелюбный", "продающий", "официальный", "SEO-оптимизированный"],
        )

    if st.button("Проверить текст", type="primary", use_container_width=True, key="ai_text_check_button"):
        with st.spinner("Проверяем текст через YandexGPT..."):
            st.session_state.ai_text_check_result = generate_text_check_analysis(source_text, tone, text_type)

    result = st.session_state.get("ai_text_check_result")
    if not result:
        _empty_state(
            "Готово к глубокой проверке",
            "AI проверит орфографию, пунктуацию, стилистику, повторы, канцеляризмы и SEO-переспам. Ошибки будут подсвечены в тексте.",
        )
        return

    if result.get("ok"):
        st.success(result.get("message", "Текст проверен."))
    else:
        st.warning(result.get("message", "Показана мягкая fallback-правка."))

    _section("Исходный текст с подсветкой ошибок")
    st.markdown(
        f'<div class="ts-copy-block">{result.get("highlighted_text") or escape(source_text)}</div>',
        unsafe_allow_html=True,
    )

    _section("Найденные ошибки и объяснения")
    errors = result.get("errors") or []
    if errors:
        rows = [
            {
                "Фрагмент": item.get("fragment", ""),
                "Тип": item.get("type", ""),
                "Почему это ошибка": item.get("explanation", ""),
                "Как исправить": item.get("suggestion", ""),
            }
            for item in errors
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        for index, item in enumerate(errors, start=1):
            with st.expander(f"{index}. {item.get('type', 'ошибка')} · {item.get('fragment') or 'без точного фрагмента'}", expanded=index <= 3):
                _card("Почему это ошибка", item.get("explanation"))
                _card("Как исправить", item.get("suggestion"))
    else:
        _empty_state("Ошибок не найдено", "AI не нашёл явных ошибок, но всё равно подготовил улучшенный вариант ниже.")

    _section("Исправленный вариант")
    _copy_block(result.get("corrected_text"))
    _section("Улучшенный вариант под выбранный тон")
    _copy_block(result.get("improved_text"))


def show_meta_generator_page():
    user_id = require_user_id()
    _inject_ai_hub_styles()

    status = "YandexGPT подключён" if yandex_gpt_available() else "YandexGPT не настроен, включён fallback"
    st.markdown(
        f"""
        <div class="ts-ai-hub-hero">
            <div>
                <div class="ts-ai-hub-title">AI помощник</div>
                <div class="ts-ai-hub-subtitle">
                    Единый рабочий центр для AI SEO Assistant, анализа конкурентов и проверки текста.
                    Основной сценарий сейчас — разбор последнего Monthly Audit и генерация понятного плана работ.
                </div>
            </div>
            <div class="ts-ai-status">{escape(status)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_assistant, tab_competitors, tab_text = st.tabs([
        "AI SEO Assistant",
        "Анализ конкурентов",
        "Проверка текста",
    ])

    with tab_assistant:
        _show_ai_seo_assistant(user_id)

    with tab_competitors:
        _show_competitor_analysis(user_id)

    with tab_text:
        _show_text_check()
