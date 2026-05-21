from datetime import datetime

import streamlit as st

from database.db import get_sites
from views.auth_page import require_user_id


CHECKLIST = {
    "Техническое SEO": [
        {
            "id": "tech_crawl",
            "title": "Проверить доступность важных страниц",
            "description": "Убедитесь, что главная, категории, услуги и ключевые посадочные страницы открываются без ошибок.",
            "tool": "Открыть сайт",
            "url": "#",
        },
        {
            "id": "tech_redirects",
            "title": "Проверить редиректы",
            "description": "Лишние цепочки редиректов замедляют сайт и могут мешать поисковым роботам.",
            "tool": "Ежемесячный аудит",
            "url": "#",
        },
        {
            "id": "tech_canonical",
            "title": "Проверить canonical",
            "description": "Canonical помогает поиску понять, какая страница является основной.",
            "tool": "Ежемесячный аудит",
            "url": "#",
        },
    ],
    "Индексация": [
        {
            "id": "index_sitemap",
            "title": "Проверить sitemap.xml",
            "description": "Sitemap должен содержать актуальные страницы, которые вы хотите видеть в поиске.",
            "tool": "Sitemap.xml",
            "url": "#",
        },
        {
            "id": "index_robots",
            "title": "Проверить robots.txt",
            "description": "Robots.txt не должен случайно закрывать важные разделы от индексации.",
            "tool": "Robots.txt",
            "url": "#",
        },
        {
            "id": "index_search",
            "title": "Сверить страницы в поиске",
            "description": "Посмотрите, какие страницы реально находятся в поиске, и нет ли там мусорных URL.",
            "tool": "Яндекс Вебмастер",
            "url": "https://webmaster.yandex.ru/",
        },
    ],
    "Коммерческие факторы": [
        {
            "id": "commercial_contacts",
            "title": "Обновить контакты и реквизиты",
            "description": "Поиску и клиентам важно видеть понятные способы связи с компанией.",
            "tool": "Открыть сайт",
            "url": "#",
        },
        {
            "id": "commercial_trust",
            "title": "Проверить доверие на страницах",
            "description": "Отзывы, гарантии, кейсы и понятные условия помогают посетителю принять решение.",
            "tool": "Открыть сайт",
            "url": "#",
        },
        {
            "id": "commercial_cta",
            "title": "Проверить формы и кнопки заявки",
            "description": "Заявка, звонок или покупка должны быть заметными и работать без лишних шагов.",
            "tool": "Открыть сайт",
            "url": "#",
        },
    ],
    "Ссылки": [
        {
            "id": "links_internal",
            "title": "Проверить внутренние ссылки",
            "description": "Важные страницы должны получать ссылки из меню, блоков и связанных материалов.",
            "tool": "Ежемесячный аудит",
            "url": "#",
        },
        {
            "id": "links_broken",
            "title": "Исправить битые ссылки",
            "description": "Битые ссылки ухудшают опыт пользователя и мешают роботам обходить сайт.",
            "tool": "Ежемесячный аудит",
            "url": "#",
        },
        {
            "id": "links_partners",
            "title": "Проверить внешние упоминания",
            "description": "Полезные упоминания бренда помогают сайту выглядеть надежнее в своей нише.",
            "tool": "Поиск",
            "url": "https://yandex.ru/search/",
        },
    ],
    "Контент": [
        {
            "id": "content_meta",
            "title": "Обновить Title и Description",
            "description": "Сниппеты должны понятно объяснять, чем страница полезна клиенту.",
            "tool": "Нейросети",
            "url": "#",
        },
        {
            "id": "content_h1",
            "title": "Проверить H1 и структуру текста",
            "description": "Заголовок и структура страницы должны быстро отвечать на вопрос посетителя.",
            "tool": "Ежемесячный аудит",
            "url": "#",
        },
        {
            "id": "content_freshness",
            "title": "Обновить устаревшие материалы",
            "description": "Свежие цены, сроки, примеры и условия помогают странице оставаться полезной.",
            "tool": "Открыть сайт",
            "url": "#",
        },
    ],
}


def _site_label(site):
    return f"{site[1]} · {site[2]}"


def _state_key(site_id, item_id, suffix):
    return f"quarterly_notebook_{site_id}_{item_id}_{suffix}"


def _checked_count(site_id):
    total = 0
    done = 0
    with_notes = 0
    category_stats = {}

    for category, items in CHECKLIST.items():
        category_total = len(items)
        category_done = 0
        for item in items:
            total += 1
            checked = bool(st.session_state.get(_state_key(site_id, item["id"], "checked"), False))
            notes = str(st.session_state.get(_state_key(site_id, item["id"], "notes"), "")).strip()
            if checked:
                done += 1
                category_done += 1
            if notes:
                with_notes += 1
        category_stats[category] = (category_done, category_total)

    return done, total, with_notes, category_stats


def _progress_line(done, total):
    percent = int(round((done / total) * 100)) if total else 0
    st.progress(percent / 100 if total else 0, text=f"Готово {done} из {total} проверок")
    return percent


def _notebook_card(site_id, category, item):
    checked_key = _state_key(site_id, item["id"], "checked")
    notes_key = _state_key(site_id, item["id"], "notes")
    date_key = _state_key(site_id, item["id"], "date")

    checked_before = bool(st.session_state.get(checked_key, False))
    checked = st.checkbox(item["title"], key=checked_key)

    if checked and not checked_before:
        st.session_state[date_key] = datetime.now().strftime("%d.%m.%Y")
    if not checked:
        st.session_state[date_key] = ""

    checked_date = st.session_state.get(date_key, "")
    status = "Готово" if checked else "В работе"
    badge_class = "ok" if checked else "neutral"

    st.markdown(
        f"""
        <div class="ts-check-card">
            <div class="ts-check-card__top">
                <span class="ts-badge {badge_class}">{status}</span>
                <span class="ts-check-category">{category}</span>
            </div>
            <p>{item["description"]}</p>
            <div class="ts-check-date">Дата проверки: {checked_date or "пока не отмечено"}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.text_area(
        "Заметки",
        key=notes_key,
        height=88,
        placeholder="Что проверили, что решили исправить, к чему вернуться позже...",
    )

    if item["url"] != "#":
        st.link_button(item["tool"], item["url"], use_container_width=True)
    else:
        st.caption(f"Инструмент: {item['tool']}")


def show_quarterly_audit_page():
    user_id = require_user_id()
    sites = get_sites(user_id=user_id)

    st.markdown(
        """
        <style>
            .ts-notebook-hero {
                padding: 26px;
                border: 1px solid #e5e7eb;
                border-radius: 18px;
                background: linear-gradient(135deg, #f8fafc 0%, #eef7ff 100%);
                margin-bottom: 18px;
            }
            .ts-notebook-hero h1 {
                margin: 0 0 8px 0;
                font-size: 30px;
                color: #0f172a;
            }
            .ts-notebook-hero p {
                margin: 0;
                color: #64748b;
                font-size: 15px;
                line-height: 1.6;
            }
            .ts-check-card {
                padding: 16px;
                border: 1px solid #e5e7eb;
                border-radius: 16px;
                background: #ffffff;
                box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05);
                margin: 8px 0 10px;
            }
            .ts-check-card__top {
                display: flex;
                justify-content: space-between;
                gap: 12px;
                align-items: center;
                margin-bottom: 10px;
            }
            .ts-check-card p {
                margin: 0 0 12px;
                color: #475569;
                line-height: 1.55;
            }
            .ts-check-date,
            .ts-check-category {
                color: #64748b;
                font-size: 13px;
            }
            .ts-badge {
                display: inline-flex;
                align-items: center;
                border-radius: 999px;
                padding: 5px 10px;
                font-size: 12px;
                font-weight: 700;
            }
            .ts-badge.ok {
                color: #047857;
                background: #d1fae5;
            }
            .ts-badge.neutral {
                color: #475569;
                background: #f1f5f9;
            }
            .ts-small-note {
                padding: 14px 16px;
                border-radius: 14px;
                background: #fff7ed;
                color: #9a3412;
                border: 1px solid #fed7aa;
                margin: 14px 0 18px;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="ts-notebook-hero">
            <h1>Ежеквартальный SEO-блокнот</h1>
            <p>Спокойный чеклист для плановой работы: отмечайте проверки, оставляйте заметки и возвращайтесь к ним перед следующим кварталом.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not sites:
        st.info("Добавьте первый сайт, чтобы начать вести SEO-блокнот.")
        return

    selected_label = st.selectbox("Сайт для проверки", [_site_label(site) for site in sites])
    selected_site = sites[[_site_label(site) for site in sites].index(selected_label)]
    site_id = selected_site[0]

    done, total, with_notes, category_stats = _checked_count(site_id)
    percent = _progress_line(done, total)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Выполнено", f"{done}/{total}")
    c2.metric("Прогресс", f"{percent}%")
    c3.metric("Разделов", len(CHECKLIST))
    c4.metric("С заметками", with_notes)

    st.markdown(
        '<div class="ts-small-note">Пока блокнот хранится в сессии браузера. Архитектура подготовлена так, чтобы позже сохранить состояние чеклиста в SQLite.</div>',
        unsafe_allow_html=True,
    )

    st.subheader("Прогресс по разделам")
    progress_cols = st.columns(len(CHECKLIST))
    for col, (category, (cat_done, cat_total)) in zip(progress_cols, category_stats.items()):
        cat_percent = int(round((cat_done / cat_total) * 100)) if cat_total else 0
        with col:
            st.metric(category, f"{cat_percent}%")

    tabs = st.tabs(list(CHECKLIST.keys()))
    for tab, (category, items) in zip(tabs, CHECKLIST.items()):
        with tab:
            cols = st.columns(2)
            for index, item in enumerate(items):
                with cols[index % 2]:
                    _notebook_card(site_id, category, item)
