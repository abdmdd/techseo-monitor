from datetime import date, datetime
from html import escape
from urllib.parse import quote_plus

import streamlit as st

from database.db import (
    get_quarterly_audit_checks,
    get_quarterly_audit_history,
    get_sites,
    upsert_quarterly_audit_check,
)
from views.auth_page import get_current_user, require_user_id


STATUS_OPTIONS = ["all_good", "needs_fix", "acceptable"]
STATUS_LABELS = {
    "all_good": "Все хорошо",
    "needs_fix": "Нужно исправить",
    "acceptable": "Допустимо",
}
STATUS_CSS = {
    "all_good": "qa-status-good",
    "needs_fix": "qa-status-fix",
    "acceptable": "qa-status-acceptable",
}

CHECK_CATEGORIES = [
    (
        "Техническое SEO",
        [
            {
                "key": "responsive",
                "title": "Проверка адаптивности",
                "help": "Проверьте, удобно ли пользоваться ключевыми страницами на мобильных устройствах.",
                "tool": "Открыть PageSpeed",
                "tool_url": "https://pagespeed.web.dev/report?url={site_url}",
            },
            {
                "key": "site_speed",
                "title": "Скорость сайта",
                "help": "Зафиксируйте показатели PageSpeed и Core Web Vitals вручную.",
                "tool": "Открыть PageSpeed",
                "tool_url": "https://pagespeed.web.dev/report?url={site_url}",
                "speed": True,
            },
            {
                "key": "malware",
                "title": "Проверка вирусов",
                "help": "Проверьте сайт на вредоносный код, подозрительные скрипты и блокировки.",
                "tool": "Открыть Dr.Web",
                "tool_url": "https://vms.drweb.ru/online/?url={site_url}",
            },
            {
                "key": "cyclic_links",
                "title": "Циклические ссылки",
                "help": "Отметьте страницы, где ссылки ведут сами на себя и создают лишний шум.",
                "tool": "Screaming Frog",
                "tool_url": "https://www.screamingfrog.co.uk/seo-spider/",
            },
            {
                "key": "extra_redirects",
                "title": "Лишние редиректы",
                "help": "Проверьте цепочки редиректов и оставьте только необходимые переходы.",
                "tool": "Screaming Frog",
                "tool_url": "https://www.screamingfrog.co.uk/seo-spider/",
            },
            {
                "key": "site_copies_index",
                "title": "Копии сайта в индексе",
                "help": "Проверьте http/https, www/non-www, зеркала и тестовые домены.",
                "tool": "Яндекс поиск",
                "tool_url": "https://yandex.ru/search/?text=site%3A{site_host}",
            },
            {
                "key": "robots_txt",
                "title": "Robots.txt",
                "help": "Убедитесь, что важные разделы не закрыты от индексации.",
                "tool": "Открыть robots.txt",
                "tool_url": "{site_root}/robots.txt",
            },
            {
                "key": "sitemap_xml",
                "title": "Sitemap.xml",
                "help": "Проверьте актуальность URL, статусы страниц и наличие sitemap в robots.txt.",
                "tool": "Открыть sitemap.xml",
                "tool_url": "{site_root}/sitemap.xml",
            },
            {
                "key": "canonical",
                "title": "Canonical",
                "help": "Проверьте корректность canonical на типовых шаблонах и дублях.",
                "tool": "Screaming Frog",
                "tool_url": "https://www.screamingfrog.co.uk/seo-spider/",
            },
            {
                "key": "pagination",
                "title": "Пагинация",
                "help": "Проверьте индексируемость, canonical и внутреннюю перелинковку страниц пагинации.",
                "tool": "Яндекс Вебмастер",
                "tool_url": "https://webmaster.yandex.ru/",
            },
            {
                "key": "page_indexation",
                "title": "Индексация страниц",
                "help": "Сверьте важные URL с фактическим присутствием в поиске.",
                "tool": "Яндекс Вебмастер",
                "tool_url": "https://webmaster.yandex.ru/",
            },
        ],
    ),
    (
        "Коммерческие факторы",
        [
            {
                "key": "commercial_factors",
                "title": "Коммерческие факторы",
                "help": "Проверьте контакты, реквизиты, оплату, доставку, гарантии, отзывы и доверие.",
                "tool": "Открыть сайт",
                "tool_url": "{site_root}",
            },
            {
                "key": "regionality",
                "title": "Региональность",
                "help": "Проверьте регион в Яндекс Вебмастере, контакты и локальные сигналы.",
                "tool": "Яндекс Вебмастер",
                "tool_url": "https://webmaster.yandex.ru/",
            },
            {
                "key": "filters",
                "title": "Проверка фильтров",
                "help": "Проверьте полезные посадочные фильтры, индексацию и закрытие мусорных комбинаций.",
                "tool": "Открыть сайт",
                "tool_url": "{site_root}",
            },
            {
                "key": "external_links",
                "title": "Внешние ссылки",
                "help": "Оцените профиль ссылок, анкоры, доноров и рискованные размещения.",
                "tool": "Яндекс Вебмастер",
                "tool_url": "https://webmaster.yandex.ru/",
            },
            {
                "key": "paid_links_indexation",
                "title": "Индексация закупленных ссылок",
                "help": "Проверьте, проиндексированы ли страницы-доноры и живы ли размещения.",
                "tool": "Яндекс поиск",
                "tool_url": "https://yandex.ru/search/?text={site_host}",
            },
            {
                "key": "outgoing_links",
                "title": "Исходящие ссылки",
                "help": "Проверьте внешние ссылки сайта, nofollow/sponsored и лишние сквозные ссылки.",
                "tool": "Screaming Frog",
                "tool_url": "https://www.screamingfrog.co.uk/seo-spider/",
            },
        ],
    ),
    (
        "Контент",
        [
            {
                "key": "image_alt",
                "title": "Alt картинок",
                "help": "Проверьте alt у важных изображений, карточек товаров и иллюстраций в статьях.",
                "tool": "Screaming Frog",
                "tool_url": "https://www.screamingfrog.co.uk/seo-spider/",
            },
            {
                "key": "meta_tags",
                "title": "Meta tags",
                "help": "Проверьте Title, Description, дубли, длину и соответствие интенту страниц.",
                "tool": "Screaming Frog",
                "tool_url": "https://www.screamingfrog.co.uk/seo-spider/",
            },
            {
                "key": "h1",
                "title": "H1",
                "help": "Проверьте один понятный H1 на странице и отсутствие дублей шаблона.",
                "tool": "Screaming Frog",
                "tool_url": "https://www.screamingfrog.co.uk/seo-spider/",
            },
            {
                "key": "duplicate_pages",
                "title": "Дубли страниц",
                "help": "Проверьте технические, контентные и параметрические дубли.",
                "tool": "Открыть Copyscape",
                "tool_url": "https://www.copyscape.com/?q={site_url}",
            },
        ],
    ),
]


def _site_name(site):
    return site[1] or site[2]


def _site_url(site):
    return site[2] or ""


def _site_root(site):
    raw_url = _site_url(site).strip()
    if not raw_url:
        return ""
    if raw_url.startswith(("http://", "https://")):
        return raw_url.rstrip("/")
    return f"https://{raw_url}".rstrip("/")


def _site_host(site):
    return _site_root(site).replace("https://", "").replace("http://", "").split("/")[0]


def _tool_url(check, site):
    root = _site_root(site)
    url = check.get("tool_url", "#")
    return url.format(
        site_url=quote_plus(root),
        site_root=root,
        site_host=quote_plus(_site_host(site)),
    )


def _state_key(site_id, check_key, field):
    return f"quarterly_audit_{site_id}_{check_key}_{field}"


def _parse_date(value):
    if isinstance(value, date):
        return value
    if not value:
        return date.today()
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return date.today()


def _date_to_db(value):
    if isinstance(value, date):
        return value.isoformat()
    return str(value or date.today().isoformat())


def _score_color(value):
    if value is None:
        return "qa-score-empty"
    if value >= 90:
        return "qa-score-good"
    if value >= 50:
        return "qa-score-warn"
    return "qa-score-bad"


def _safe_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _save_cell(user_id, site_id, check_key, user_name, has_speed=False):
    status = st.session_state.get(_state_key(site_id, check_key, "status"), "acceptable")
    comment = st.session_state.get(_state_key(site_id, check_key, "comment"), "")
    checked_at = _date_to_db(st.session_state.get(_state_key(site_id, check_key, "checked_at")))

    mobile_score = None
    desktop_score = None
    lcp = None
    inp = None
    cls = None

    if has_speed:
        mobile_score = _safe_int(st.session_state.get(_state_key(site_id, check_key, "mobile_score")))
        desktop_score = _safe_int(st.session_state.get(_state_key(site_id, check_key, "desktop_score")))
        lcp = _safe_float(st.session_state.get(_state_key(site_id, check_key, "lcp")))
        inp = _safe_float(st.session_state.get(_state_key(site_id, check_key, "inp")))
        cls = _safe_float(st.session_state.get(_state_key(site_id, check_key, "cls")))

    upsert_quarterly_audit_check(
        user_id=user_id,
        site_id=site_id,
        check_key=check_key,
        status=status,
        comment=comment,
        checked_at=checked_at,
        checked_by=user_name,
        mobile_score=mobile_score,
        desktop_score=desktop_score,
        lcp=lcp,
        inp=inp,
        cls=cls,
    )
    st.session_state["quarterly_audit_saved_at"] = datetime.now().strftime("%H:%M:%S")


def _ensure_cell_state(site_id, check, saved):
    check_key = check["key"]
    defaults = {
        "status": (saved.get("status") or "acceptable") if saved else "acceptable",
        "comment": saved.get("comment") if saved else "",
        "checked_at": _parse_date(saved.get("checked_at") if saved else None),
        "mobile_score": saved.get("mobile_score") if saved else None,
        "desktop_score": saved.get("desktop_score") if saved else None,
        "lcp": saved.get("lcp") if saved else None,
        "inp": saved.get("inp") if saved else None,
        "cls": saved.get("cls") if saved else None,
    }

    for field, value in defaults.items():
        key = _state_key(site_id, check_key, field)
        if key not in st.session_state:
            st.session_state[key] = value


def _status_badge(status):
    normalized = status if status in STATUS_OPTIONS else "acceptable"
    return (
        f'<span class="qa-status {STATUS_CSS[normalized]}">'
        f'{escape(STATUS_LABELS[normalized])}'
        f'</span>'
    )


def _render_css():
    st.markdown(
        """
        <style>
            .qa-hero {
                display: flex;
                justify-content: space-between;
                gap: 18px;
                align-items: flex-start;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                padding: 22px;
                margin-bottom: 16px;
                background: linear-gradient(135deg, rgba(14, 165, 233, 0.10), rgba(22, 163, 74, 0.08)), #ffffff;
                box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
            }
            .qa-title {
                color: #0f172a;
                font-size: 30px;
                font-weight: 850;
                line-height: 1.15;
                margin-bottom: 8px;
            }
            .qa-subtitle {
                color: #475569;
                font-size: 14px;
                line-height: 1.55;
                max-width: 850px;
            }
            .qa-save-pill {
                display: inline-flex;
                white-space: nowrap;
                border-radius: 999px;
                padding: 7px 11px;
                color: #166534;
                background: #dcfce7;
                border: 1px solid #bbf7d0;
                font-size: 12px;
                font-weight: 850;
            }
            .qa-helper {
                color: #64748b;
                font-size: 13px;
                line-height: 1.45;
                margin: -2px 0 14px 0;
            }
            .qa-category {
                position: sticky;
                top: 0;
                z-index: 4;
                display: flex;
                justify-content: space-between;
                gap: 12px;
                align-items: center;
                margin: 20px 0 8px 0;
                padding: 12px 14px;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                background: rgba(248, 250, 252, 0.97);
                backdrop-filter: blur(8px);
            }
            .qa-category-title {
                color: #0f172a;
                font-size: 18px;
                font-weight: 850;
            }
            .qa-category-note {
                color: #64748b;
                font-size: 12px;
                font-weight: 750;
            }
            .qa-workspace-header {
                position: sticky;
                top: 0;
                z-index: 5;
                border: 1px solid #dbeafe;
                border-radius: 8px;
                padding: 10px;
                margin: 10px 0 12px 0;
                background: rgba(239, 246, 255, 0.98);
                backdrop-filter: blur(8px);
                box-shadow: 0 8px 18px rgba(15, 23, 42, 0.06);
            }
            .qa-workspace-head-cell {
                color: #1e3a8a;
                font-size: 12px;
                font-weight: 900;
                text-transform: uppercase;
                letter-spacing: 0.03em;
                overflow-wrap: anywhere;
            }
            .qa-row {
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                background: #ffffff;
                margin-bottom: 10px;
                padding: 10px;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
                transition: border-color 140ms ease, box-shadow 140ms ease;
            }
            .qa-row:hover {
                border-color: #bfdbfe;
                box-shadow: 0 10px 24px rgba(15, 23, 42, 0.07);
            }
            .qa-check-title {
                color: #0f172a;
                font-size: 15px;
                font-weight: 850;
                line-height: 1.3;
                margin-bottom: 7px;
            }
            .qa-check-help {
                color: #64748b;
                font-size: 12px;
                line-height: 1.42;
                margin-bottom: 10px;
            }
            .qa-site-chip {
                display: inline-flex;
                max-width: 100%;
                border-radius: 999px;
                padding: 4px 9px;
                color: #1d4ed8;
                background: #eff6ff;
                border: 1px solid #bfdbfe;
                font-size: 11px;
                font-weight: 850;
                overflow-wrap: anywhere;
            }
            .qa-status {
                display: inline-flex;
                align-items: center;
                border-radius: 999px;
                padding: 4px 9px;
                font-size: 11px;
                font-weight: 850;
                border: 1px solid transparent;
                margin-bottom: 6px;
            }
            .qa-status-good {
                color: #166534;
                background: #dcfce7;
                border-color: #bbf7d0;
            }
            .qa-status-fix {
                color: #9a3412;
                background: #ffedd5;
                border-color: #fed7aa;
            }
            .qa-status-acceptable {
                color: #854d0e;
                background: #fef9c3;
                border-color: #fde68a;
            }
            .qa-byline {
                color: #64748b;
                font-size: 11px;
                margin: 4px 0 6px 0;
            }
            .qa-speed-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 6px;
                margin: 4px 0 8px 0;
            }
            .qa-score {
                border-radius: 8px;
                padding: 6px 8px;
                font-size: 11px;
                font-weight: 850;
                border: 1px solid #e2e8f0;
            }
            .qa-score-good {
                color: #166534;
                background: #dcfce7;
                border-color: #bbf7d0;
            }
            .qa-score-warn {
                color: #9a3412;
                background: #ffedd5;
                border-color: #fed7aa;
            }
            .qa-score-bad {
                color: #991b1b;
                background: #fee2e2;
                border-color: #fecaca;
            }
            .qa-score-empty {
                color: #475569;
                background: #f8fafc;
                border-color: #e2e8f0;
            }
            .qa-empty {
                border: 1px dashed #cbd5e1;
                border-radius: 10px;
                padding: 18px;
                color: #64748b;
                background: #ffffff;
            }
            div[data-testid="stHorizontalBlock"] {
                align-items: stretch;
            }
            @media (max-width: 760px) {
                .qa-hero {
                    flex-direction: column;
                    padding: 18px;
                }
                .qa-title {
                    font-size: 24px;
                }
                .qa-category {
                    position: static;
                    flex-direction: column;
                    align-items: flex-start;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_speed_badges(site_id, check_key):
    mobile = _safe_int(st.session_state.get(_state_key(site_id, check_key, "mobile_score")))
    desktop = _safe_int(st.session_state.get(_state_key(site_id, check_key, "desktop_score")))

    st.markdown(
        f"""
        <div class="qa-speed-grid">
            <div class="qa-score {_score_color(mobile)}">Mobile: {mobile if mobile is not None else "-"}</div>
            <div class="qa-score {_score_color(desktop)}">Desktop: {desktop if desktop is not None else "-"}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_cell(user_id, site, check, saved, user_name):
    site_id = site[0]
    check_key = check["key"]
    has_speed = bool(check.get("speed"))
    _ensure_cell_state(site_id, check, saved)

    status = st.session_state.get(_state_key(site_id, check_key, "status"), "acceptable")
    checked_by = (saved or {}).get("checked_by") or user_name
    updated_at = (saved or {}).get("updated_at")

    st.markdown(
        f"""
        <div>
            <div class="qa-site-chip">{escape(_site_name(site))}</div><br>
            {_status_badge(status)}
            <div class="qa-byline">SEO специалист: {escape(checked_by)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    callback_args = (user_id, site_id, check_key, user_name, has_speed)

    st.selectbox(
        "Статус",
        STATUS_OPTIONS,
        format_func=lambda option: STATUS_LABELS[option],
        key=_state_key(site_id, check_key, "status"),
        label_visibility="collapsed",
        on_change=_save_cell,
        args=callback_args,
    )
    st.text_area(
        "Комментарий SEO специалиста",
        key=_state_key(site_id, check_key, "comment"),
        height=94,
        placeholder="Что проверено, что исправить, куда вернуться в следующем квартале...",
        label_visibility="collapsed",
        on_change=_save_cell,
        args=callback_args,
    )
    st.date_input(
        "Дата проверки",
        key=_state_key(site_id, check_key, "checked_at"),
        format="DD.MM.YYYY",
        on_change=_save_cell,
        args=callback_args,
    )

    if has_speed:
        _render_speed_badges(site_id, check_key)
        speed_cols = st.columns(2)
        with speed_cols[0]:
            st.number_input(
                "Mobile score",
                min_value=0,
                max_value=100,
                step=1,
                key=_state_key(site_id, check_key, "mobile_score"),
                on_change=_save_cell,
                args=callback_args,
            )
            st.number_input(
                "LCP",
                min_value=0.0,
                step=0.1,
                key=_state_key(site_id, check_key, "lcp"),
                on_change=_save_cell,
                args=callback_args,
            )
            st.number_input(
                "CLS",
                min_value=0.0,
                step=0.01,
                key=_state_key(site_id, check_key, "cls"),
                on_change=_save_cell,
                args=callback_args,
            )
        with speed_cols[1]:
            st.number_input(
                "Desktop score",
                min_value=0,
                max_value=100,
                step=1,
                key=_state_key(site_id, check_key, "desktop_score"),
                on_change=_save_cell,
                args=callback_args,
            )
            st.number_input(
                "INP",
                min_value=0.0,
                step=10.0,
                key=_state_key(site_id, check_key, "inp"),
                on_change=_save_cell,
                args=callback_args,
            )

    if updated_at:
        st.caption(f"Сохранено: {updated_at}")

    st.link_button(check["tool"], _tool_url(check, site), use_container_width=True)


def _status_totals(checks):
    totals = {"all_good": 0, "needs_fix": 0, "acceptable": 0}
    for check in checks.values():
        status = check.get("status") or "acceptable"
        if status in totals:
            totals[status] += 1
    return totals


def _flatten_checks():
    return [check for _, checks in CHECK_CATEGORIES for check in checks]


def _render_history(user_id, sites_by_id):
    history = get_quarterly_audit_history(user_id=user_id, limit=60)
    if not history:
        st.markdown('<div class="qa-empty">История появится после первых сохранений в таблице.</div>', unsafe_allow_html=True)
        return

    check_titles = {check["key"]: check["title"] for check in _flatten_checks()}

    for row in history[:20]:
        _, _, site_id, check_key, old_status, new_status, old_comment, new_comment, changed_at, changed_by = row
        site = sites_by_id.get(site_id)
        site_name = _site_name(site) if site else f"Сайт #{site_id}"
        title = check_titles.get(check_key, check_key)
        old_label = STATUS_LABELS.get(old_status, old_status or "пусто")
        new_label = STATUS_LABELS.get(new_status, new_status or "пусто")

        st.markdown(
            f"""
            <div class="ts-card" style="margin-bottom: 8px;">
                <div class="ts-card-title">{escape(site_name)} · {escape(title)}</div>
                <div class="ts-card-text">Статус: {escape(old_label)} → {escape(new_label)}</div>
                <div class="ts-card-text">Изменил: {escape(changed_by or "не указан")} · {escape(changed_at or "")}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if (old_comment or "") != (new_comment or ""):
            st.caption("Комментарий был обновлен.")


def show_quarterly_audit_page():
    user_id = require_user_id()
    user = get_current_user() or {}
    user_name = user.get("name") or user.get("email") or "SEO специалист"
    sites = get_sites(user_id=user_id)
    sites_by_id = {site[0]: site for site in sites}
    saved_checks = get_quarterly_audit_checks(user_id=user_id)

    _render_css()

    saved_at = st.session_state.get("quarterly_audit_saved_at")
    save_label = f"Автосохранено в {saved_at}" if saved_at else "Автосохранение включено"

    st.markdown(
        f"""
        <div class="qa-hero">
            <div>
                <div class="qa-title">Ежеквартальный SEO Workspace</div>
                <div class="qa-subtitle">
                    Рабочая матрица для ручных quarterly SEO проверок. Строки — проверки, колонки — ваши сайты,
                    ячейки — состояние конкретной проверки: статус, комментарий, дата, специалист и метрики скорости.
                </div>
            </div>
            <div class="qa-save-pill">{escape(save_label)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not sites:
        st.markdown(
            '<div class="qa-empty">Добавьте первый сайт в разделе «Мои сайты», чтобы начать вести ежеквартальный SEO workspace.</div>',
            unsafe_allow_html=True,
        )
        return

    totals = _status_totals(saved_checks)
    total_cells = len(_flatten_checks()) * len(sites)
    filled_cells = len(saved_checks)

    metric_cols = st.columns(4)
    metric_cols[0].metric("Сайтов в workspace", len(sites))
    metric_cols[1].metric("Проверок", len(_flatten_checks()))
    metric_cols[2].metric("Заполнено ячеек", f"{filled_cells}/{total_cells}")
    metric_cols[3].metric("Нужно исправить", totals["needs_fix"])

    st.markdown(
        '<div class="qa-helper">Изменения сохраняются автоматически в SQLite. После F5 статусы, комментарии, даты и speed-метрики останутся на месте.</div>',
        unsafe_allow_html=True,
    )

    selected_sites = st.multiselect(
        "Колонки таблицы",
        options=[site[0] for site in sites],
        default=[site[0] for site in sites],
        format_func=lambda site_id: _site_name(sites_by_id[site_id]),
        help="Можно временно скрыть часть сайтов, сами данные при этом не удаляются.",
    )

    visible_sites = [sites_by_id[site_id] for site_id in selected_sites]
    if not visible_sites:
        st.info("Выберите хотя бы один сайт, чтобы показать таблицу.")
        return

    tabs = st.tabs(["SEO workspace", "История изменений"])

    with tabs[0]:
        st.markdown('<div class="qa-workspace-header">', unsafe_allow_html=True)
        header_cols = st.columns([1.15] + [1 for _ in visible_sites], gap="medium")
        with header_cols[0]:
            st.markdown('<div class="qa-workspace-head-cell">SEO проверка</div>', unsafe_allow_html=True)
        for header_col, site in zip(header_cols[1:], visible_sites):
            with header_col:
                st.markdown(
                    f'<div class="qa-workspace-head-cell">{escape(_site_name(site))}</div>',
                    unsafe_allow_html=True,
                )
        st.markdown("</div>", unsafe_allow_html=True)

        for category, checks in CHECK_CATEGORIES:
            st.markdown(
                f"""
                <div class="qa-category">
                    <div class="qa-category-title">{escape(category)}</div>
                    <div class="qa-category-note">{len(checks)} проверок · {len(visible_sites)} сайтов</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            for check in checks:
                st.markdown('<div class="qa-row">', unsafe_allow_html=True)
                columns = st.columns([1.15] + [1 for _ in visible_sites], gap="medium")

                with columns[0]:
                    st.markdown(
                        f"""
                        <div class="qa-check-title">{escape(check["title"])}</div>
                        <div class="qa-check-help">{escape(check["help"])}</div>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.caption("Подсказка: каждая ячейка сохраняется сразу после изменения поля.")

                for column, site in zip(columns[1:], visible_sites):
                    with column:
                        _render_cell(
                            user_id=user_id,
                            site=site,
                            check=check,
                            saved=saved_checks.get((site[0], check["key"])),
                            user_name=user_name,
                        )

                st.markdown("</div>", unsafe_allow_html=True)

    with tabs[1]:
        st.markdown(
            '<div class="qa-helper">История хранит старые и новые значения статуса и комментария для каждой измененной проверки.</div>',
            unsafe_allow_html=True,
        )
        _render_history(user_id, sites_by_id)
