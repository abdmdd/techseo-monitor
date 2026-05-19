from html import escape

import streamlit as st


def apply_global_styles():
    st.markdown(
        """
        <style>
            :root {
                --ts-bg: #f8fafc;
                --ts-surface: #ffffff;
                --ts-border: #e2e8f0;
                --ts-muted: #64748b;
                --ts-text: #0f172a;
                --ts-blue: #2563eb;
                --ts-green: #16a34a;
                --ts-amber: #f59e0b;
                --ts-red: #dc2626;
            }

            .block-container {
                padding-top: 1.5rem;
                padding-bottom: 2.5rem;
                max-width: 1320px;
            }

            section[data-testid="stSidebar"] {
                min-width: 292px !important;
                width: 292px !important;
                border-right: 1px solid var(--ts-border);
            }

            section[data-testid="stSidebar"] .stRadio label {
                width: 100%;
                white-space: normal;
                line-height: 1.25;
            }

            section[data-testid="stSidebar"] [role="radiogroup"] label {
                padding: 0.25rem 0;
            }

            h1, h2, h3 {
                letter-spacing: 0;
                color: var(--ts-text);
            }

            div[data-testid="stMetric"] {
                background: var(--ts-surface);
                border: 1px solid var(--ts-border);
                border-radius: 8px;
                padding: 14px 16px;
            }

            div[data-testid="stDataFrame"] {
                border: 1px solid var(--ts-border);
                border-radius: 8px;
                overflow: hidden;
            }

            .ts-page-title {
                font-size: 34px;
                font-weight: 800;
                margin: 0 0 4px 0;
                color: var(--ts-text);
            }

            .ts-page-subtitle {
                font-size: 15px;
                color: var(--ts-muted);
                margin: 0 0 22px 0;
            }

            .ts-card {
                background: var(--ts-surface);
                border: 1px solid var(--ts-border);
                border-radius: 8px;
                padding: 16px;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
            }

            .ts-metric-label {
                color: var(--ts-muted);
                font-size: 12px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.04em;
            }

            .ts-metric-value {
                color: var(--ts-text);
                font-size: 30px;
                font-weight: 800;
                line-height: 1.1;
                margin-top: 8px;
            }

            .ts-metric-note {
                color: var(--ts-muted);
                font-size: 13px;
                margin-top: 8px;
            }

            .ts-risk-bar {
                height: 8px;
                border-radius: 999px;
                background: #e5e7eb;
                overflow: hidden;
                margin-top: 12px;
            }

            .ts-risk-fill {
                height: 100%;
                border-radius: 999px;
            }

            .ts-badge {
                display: inline-flex;
                align-items: center;
                border-radius: 999px;
                padding: 3px 9px;
                font-size: 12px;
                font-weight: 700;
                border: 1px solid transparent;
            }

            .ts-badge-high {
                color: #991b1b;
                background: #fee2e2;
                border-color: #fecaca;
            }

            .ts-badge-medium {
                color: #92400e;
                background: #fef3c7;
                border-color: #fde68a;
            }

            .ts-badge-low {
                color: #166534;
                background: #dcfce7;
                border-color: #bbf7d0;
            }

            .ts-rec-card {
                background: var(--ts-surface);
                border: 1px solid var(--ts-border);
                border-left: 4px solid var(--ts-blue);
                border-radius: 8px;
                padding: 14px 16px;
                margin-bottom: 10px;
            }

            .ts-rec-title {
                font-weight: 800;
                color: var(--ts-text);
                margin-bottom: 6px;
            }

            .ts-rec-body {
                color: #334155;
                font-size: 14px;
                line-height: 1.45;
                margin-top: 8px;
            }

            .ts-warning-card {
                background: #fffbeb;
                border: 1px solid #fde68a;
                border-radius: 8px;
                padding: 12px 14px;
                color: #78350f;
                margin-bottom: 8px;
            }

            .ts-compact-note {
                color: var(--ts-muted);
                font-size: 13px;
                line-height: 1.45;
            }
        </style>
        """,
        unsafe_allow_html=True
    )


def page_header(title, subtitle):
    st.markdown(
        f"""
        <div class="ts-page-title">{escape(title)}</div>
        <div class="ts-page-subtitle">{escape(subtitle)}</div>
        """,
        unsafe_allow_html=True
    )


def metric_card(label, value, note="", accent="#2563eb"):
    st.markdown(
        f"""
        <div class="ts-card">
            <div class="ts-metric-label">{escape(str(label))}</div>
            <div class="ts-metric-value">{escape(str(value))}</div>
            <div class="ts-metric-note">{escape(str(note))}</div>
            <div class="ts-risk-bar">
                <div class="ts-risk-fill" style="width: 100%; background: {escape(accent)};"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def risk_card(score, risk, color):
    normalized_score = max(0, min(100, int(score or 0)))
    st.markdown(
        f"""
        <div class="ts-card">
            <div class="ts-metric-label">SEO Risk</div>
            <div class="ts-metric-value" style="color: {escape(color)};">{escape(str(risk))}</div>
            <div class="ts-metric-note">Score: {normalized_score}/100</div>
            <div class="ts-risk-bar">
                <div class="ts-risk-fill" style="width: {normalized_score}%; background: {escape(color)};"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def priority_badge(priority):
    priority_text = str(priority or "").lower()

    if "выс" in priority_text:
        class_name = "ts-badge-high"
    elif "сред" in priority_text:
        class_name = "ts-badge-medium"
    else:
        class_name = "ts-badge-low"

    return f'<span class="ts-badge {class_name}">{escape(str(priority))}</span>'


def recommendation_card(recommendation):
    title = recommendation.get("title", "Рекомендация")
    priority = recommendation.get("priority", "Средний")
    body = recommendation.get("recommendation", "")

    st.markdown(
        f"""
        <div class="ts-rec-card">
            <div class="ts-rec-title">{escape(title)}</div>
            {priority_badge(priority)}
            <div class="ts-rec-body">{escape(body)}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def warnings_block(warnings):
    if not warnings:
        return

    with st.expander(f"Предупреждения crawler: {len(warnings)}", expanded=False):
        for warning in warnings:
            st.markdown(
                f'<div class="ts-warning-card">{escape(str(warning))}</div>',
                unsafe_allow_html=True
            )


def compact_note(text):
    st.markdown(
        f'<div class="ts-compact-note">{escape(text)}</div>',
        unsafe_allow_html=True
    )
