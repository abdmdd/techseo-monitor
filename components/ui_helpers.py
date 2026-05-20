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

            .ts-saas-hero {
                display: flex;
                justify-content: space-between;
                gap: 18px;
                align-items: flex-start;
                background:
                    linear-gradient(135deg, rgba(37, 99, 235, 0.10), rgba(22, 163, 74, 0.08)),
                    #ffffff;
                border: 1px solid var(--ts-border);
                border-radius: 10px;
                padding: 22px;
                margin-bottom: 18px;
                box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
            }

            .ts-saas-hero-title {
                color: var(--ts-text);
                font-size: 28px;
                font-weight: 850;
                line-height: 1.15;
                margin-bottom: 8px;
            }

            .ts-saas-hero-subtitle {
                color: #475569;
                font-size: 14px;
                line-height: 1.5;
                max-width: 720px;
            }

            .ts-saas-pill {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                border: 1px solid #bfdbfe;
                background: #eff6ff;
                color: #1d4ed8;
                border-radius: 999px;
                padding: 7px 11px;
                font-size: 12px;
                font-weight: 800;
                white-space: nowrap;
            }

            .ts-dashboard-section {
                margin-top: 22px;
                margin-bottom: 10px;
            }

            .ts-section-title {
                color: var(--ts-text);
                font-size: 19px;
                font-weight: 850;
                margin-bottom: 4px;
            }

            .ts-section-subtitle {
                color: var(--ts-muted);
                font-size: 13px;
                margin-bottom: 12px;
            }

            .ts-action-card,
            .ts-audit-card,
            .ts-feature-card {
                background: var(--ts-surface);
                border: 1px solid var(--ts-border);
                border-radius: 10px;
                padding: 15px;
                min-height: 112px;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
                transition: transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease;
            }

            .ts-action-card:hover,
            .ts-audit-card:hover,
            .ts-feature-card:hover {
                transform: translateY(-2px);
                border-color: #bfdbfe;
                box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
            }

            .ts-action-icon,
            .ts-feature-icon {
                width: 34px;
                height: 34px;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                border-radius: 9px;
                background: #eff6ff;
                color: #1d4ed8;
                font-size: 17px;
                margin-bottom: 10px;
            }

            .ts-card-title {
                color: var(--ts-text);
                font-size: 15px;
                font-weight: 850;
                line-height: 1.25;
                margin-bottom: 6px;
            }

            .ts-card-text {
                color: var(--ts-muted);
                font-size: 13px;
                line-height: 1.42;
            }

            .ts-audit-meta {
                display: flex;
                justify-content: space-between;
                gap: 10px;
                align-items: center;
                margin-top: 12px;
                color: var(--ts-muted);
                font-size: 12px;
            }

            .ts-score-chip {
                display: inline-flex;
                align-items: center;
                border-radius: 999px;
                padding: 4px 9px;
                color: #ffffff;
                font-size: 12px;
                font-weight: 850;
            }

            .ts-empty-state {
                background: #ffffff;
                border: 1px dashed #cbd5e1;
                border-radius: 10px;
                padding: 18px;
                color: var(--ts-muted);
                font-size: 14px;
            }

            .ts-sites-header {
                display: flex;
                justify-content: space-between;
                gap: 18px;
                align-items: flex-start;
                background:
                    linear-gradient(135deg, rgba(15, 118, 110, 0.10), rgba(37, 99, 235, 0.08)),
                    #ffffff;
                border: 1px solid var(--ts-border);
                border-radius: 10px;
                padding: 22px;
                margin-bottom: 18px;
                box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
            }

            .ts-site-card,
            .ts-integration-card {
                background: #ffffff;
                border: 1px solid var(--ts-border);
                border-radius: 10px;
                padding: 16px;
                min-height: 172px;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
                transition: transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease;
            }

            .ts-site-card:hover,
            .ts-integration-card:hover {
                transform: translateY(-2px);
                border-color: #99f6e4;
                box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
            }

            .ts-site-domain {
                color: var(--ts-text);
                font-size: 17px;
                font-weight: 850;
                line-height: 1.25;
                margin-bottom: 6px;
                overflow-wrap: anywhere;
            }

            .ts-site-url {
                color: var(--ts-muted);
                font-size: 12px;
                line-height: 1.35;
                margin-bottom: 14px;
                overflow-wrap: anywhere;
            }

            .ts-site-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 10px;
                margin: 12px 0;
            }

            .ts-site-stat {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 9px 10px;
            }

            .ts-site-stat-label {
                color: var(--ts-muted);
                font-size: 11px;
                font-weight: 750;
                text-transform: uppercase;
                letter-spacing: 0.03em;
            }

            .ts-site-stat-value {
                color: var(--ts-text);
                font-size: 16px;
                font-weight: 850;
                margin-top: 3px;
            }

            .ts-status-chip {
                display: inline-flex;
                align-items: center;
                border-radius: 999px;
                padding: 4px 9px;
                font-size: 12px;
                font-weight: 850;
                margin-top: 4px;
            }

            .ts-status-good {
                color: #166534;
                background: #dcfce7;
                border: 1px solid #bbf7d0;
            }

            .ts-status-warn {
                color: #92400e;
                background: #fef3c7;
                border: 1px solid #fde68a;
            }

            .ts-status-bad {
                color: #991b1b;
                background: #fee2e2;
                border: 1px solid #fecaca;
            }

            .ts-status-neutral {
                color: #334155;
                background: #f1f5f9;
                border: 1px solid #e2e8f0;
            }

            .ts-integration-icon {
                width: 36px;
                height: 36px;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                border-radius: 10px;
                background: #ecfeff;
                color: #0f766e;
                font-size: 18px;
                margin-bottom: 10px;
            }

            .ts-integration-center-card {
                background: #ffffff;
                border: 1px solid var(--ts-border);
                border-radius: 10px;
                padding: 18px;
                min-height: 260px;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
                transition: transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease;
            }

            .ts-integration-center-card:hover {
                transform: translateY(-2px);
                border-color: #bfdbfe;
                box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
            }

            .ts-integration-header {
                display: flex;
                justify-content: space-between;
                gap: 12px;
                align-items: flex-start;
                margin-bottom: 14px;
            }

            .ts-integration-title-wrap {
                display: flex;
                gap: 11px;
                align-items: center;
            }

            .ts-integration-meta-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 10px;
                margin-top: 12px;
            }

            .ts-integration-meta {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 9px 10px;
            }

            .ts-integration-label {
                color: var(--ts-muted);
                font-size: 11px;
                font-weight: 850;
                text-transform: uppercase;
                letter-spacing: 0.03em;
                margin-bottom: 4px;
            }

            .ts-integration-value {
                color: var(--ts-text);
                font-size: 13px;
                font-weight: 800;
                overflow-wrap: anywhere;
            }

            .ts-status-connected {
                color: #166534;
                background: #dcfce7;
                border: 1px solid #bbf7d0;
            }

            .ts-status-pending {
                color: #92400e;
                background: #fef3c7;
                border: 1px solid #fde68a;
            }

            .ts-status-disconnected {
                color: #334155;
                background: #f1f5f9;
                border: 1px solid #e2e8f0;
            }

            .ts-checklist-card {
                background: #ffffff;
                border: 1px solid var(--ts-border);
                border-radius: 10px;
                padding: 16px;
                min-height: 212px;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
                transition: transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease;
            }

            .ts-checklist-card:hover {
                transform: translateY(-2px);
                border-color: #bfdbfe;
                box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
            }

            .ts-checklist-title {
                color: var(--ts-text);
                font-size: 15px;
                font-weight: 850;
                line-height: 1.28;
                margin-bottom: 6px;
            }

            .ts-checklist-meta-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 9px;
                margin-top: 12px;
            }

            .ts-checklist-meta {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 9px 10px;
            }

            .ts-progress-track {
                height: 10px;
                border-radius: 999px;
                background: #e5e7eb;
                overflow: hidden;
                margin: 10px 0 6px 0;
            }

            .ts-progress-fill {
                height: 100%;
                border-radius: 999px;
                background: linear-gradient(90deg, #2563eb, #0f766e);
            }

            .ts-ai-card {
                background: #ffffff;
                border: 1px solid var(--ts-border);
                border-radius: 10px;
                padding: 16px;
                min-height: 140px;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
                transition: transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease;
            }

            .ts-ai-card:hover {
                transform: translateY(-2px);
                border-color: #c4b5fd;
                box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
            }

            .ts-ai-hero {
                display: flex;
                justify-content: space-between;
                gap: 18px;
                align-items: flex-start;
                background:
                    linear-gradient(135deg, rgba(124, 58, 237, 0.12), rgba(37, 99, 235, 0.08)),
                    #ffffff;
                border: 1px solid var(--ts-border);
                border-radius: 10px;
                padding: 22px;
                margin-bottom: 18px;
                box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
            }

            .ts-competitors-hero {
                display: flex;
                justify-content: space-between;
                gap: 18px;
                align-items: flex-start;
                background:
                    linear-gradient(135deg, rgba(14, 165, 233, 0.12), rgba(124, 58, 237, 0.08)),
                    #ffffff;
                border: 1px solid var(--ts-border);
                border-radius: 10px;
                padding: 22px;
                margin-bottom: 18px;
                box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
            }

            .ts-competitor-card {
                background: #ffffff;
                border: 1px solid var(--ts-border);
                border-radius: 10px;
                padding: 16px;
                min-height: 360px;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
                transition: transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease;
            }

            .ts-competitor-card:hover {
                transform: translateY(-2px);
                border-color: #c4b5fd;
                box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
            }

            .ts-competitor-head {
                display: flex;
                justify-content: space-between;
                gap: 12px;
                align-items: flex-start;
                margin-bottom: 12px;
            }

            .ts-keyword-row {
                display: flex;
                flex-wrap: wrap;
                gap: 7px;
                margin-top: 12px;
            }

            .ts-keyword-chip {
                display: inline-flex;
                align-items: center;
                border-radius: 999px;
                padding: 4px 9px;
                color: #3730a3;
                background: #eef2ff;
                border: 1px solid #c7d2fe;
                font-size: 12px;
                font-weight: 800;
            }

            .ts-compact-list {
                margin: 7px 0 0 0;
                padding-left: 18px;
                color: #334155;
                font-size: 13px;
                line-height: 1.45;
            }

            .ts-chart-placeholder {
                background: #ffffff;
                border: 1px solid var(--ts-border);
                border-radius: 10px;
                padding: 16px;
                min-height: 210px;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
            }

            .ts-placeholder-bars {
                display: flex;
                align-items: end;
                gap: 10px;
                height: 116px;
                margin-top: 18px;
                padding: 12px;
                border-radius: 8px;
                background: #f8fafc;
                border: 1px solid #e2e8f0;
            }

            .ts-placeholder-bars span {
                flex: 1;
                min-width: 22px;
                border-radius: 8px 8px 3px 3px;
                background: linear-gradient(180deg, #7c3aed, #0ea5e9);
            }

            .ts-ai-output {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 10px;
            }

            .ts-ai-output-label {
                color: var(--ts-muted);
                font-size: 11px;
                font-weight: 850;
                text-transform: uppercase;
                letter-spacing: 0.03em;
                margin-bottom: 6px;
            }

            .ts-ai-output-text {
                color: var(--ts-text);
                font-size: 14px;
                line-height: 1.45;
                font-weight: 700;
            }

            .ts-audit-header {
                display: flex;
                justify-content: space-between;
                gap: 18px;
                align-items: flex-start;
                background:
                    linear-gradient(135deg, rgba(37, 99, 235, 0.10), rgba(245, 158, 11, 0.08)),
                    #ffffff;
                border: 1px solid var(--ts-border);
                border-radius: 10px;
                padding: 22px;
                margin-bottom: 18px;
                box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
            }

            .ts-audit-launch {
                background: #ffffff;
                border: 1px solid var(--ts-border);
                border-radius: 10px;
                padding: 18px;
                margin: 16px 0 18px 0;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
            }

            .ts-audit-section-card,
            .ts-error-card,
            .ts-redirect-chain {
                background: #ffffff;
                border: 1px solid var(--ts-border);
                border-radius: 10px;
                padding: 16px;
                margin-bottom: 12px;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
                transition: transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease;
            }

            .ts-audit-section-card:hover,
            .ts-error-card:hover,
            .ts-redirect-chain:hover {
                transform: translateY(-2px);
                border-color: #bfdbfe;
                box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
            }

            .ts-audit-section-title {
                color: var(--ts-text);
                font-size: 17px;
                font-weight: 850;
                margin-bottom: 6px;
            }

            .ts-audit-kv {
                display: flex;
                justify-content: space-between;
                gap: 12px;
                padding: 9px 0;
                border-bottom: 1px solid #f1f5f9;
                color: #334155;
                font-size: 13px;
            }

            .ts-audit-kv:last-child {
                border-bottom: 0;
            }

            .ts-audit-kv span:first-child {
                color: var(--ts-muted);
                font-weight: 750;
            }

            .ts-severity {
                display: inline-flex;
                align-items: center;
                border-radius: 999px;
                padding: 4px 9px;
                font-size: 12px;
                font-weight: 850;
                margin-right: 8px;
            }

            .ts-severity-high {
                color: #991b1b;
                background: #fee2e2;
                border: 1px solid #fecaca;
            }

            .ts-severity-medium {
                color: #92400e;
                background: #fef3c7;
                border: 1px solid #fde68a;
            }

            .ts-severity-low {
                color: #166534;
                background: #dcfce7;
                border: 1px solid #bbf7d0;
            }

            .ts-error-category {
                color: var(--ts-text);
                font-size: 15px;
                font-weight: 850;
                margin: 10px 0 6px 0;
            }

            .ts-error-intel-card {
                background: #ffffff;
                border: 1px solid var(--ts-border);
                border-radius: 10px;
                padding: 14px 15px;
                margin-bottom: 10px;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
                transition: transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease;
            }

            .ts-error-intel-card:hover {
                transform: translateY(-2px);
                border-color: #bfdbfe;
                box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
            }

            .ts-error-intel-head {
                display: flex;
                justify-content: space-between;
                gap: 12px;
                align-items: flex-start;
                margin-bottom: 10px;
            }

            .ts-error-intel-title {
                color: var(--ts-text);
                font-size: 15px;
                font-weight: 850;
                line-height: 1.3;
            }

            .ts-error-grid {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 10px;
                margin-top: 10px;
            }

            .ts-error-mini {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 10px;
            }

            .ts-error-mini-label {
                color: var(--ts-muted);
                font-size: 11px;
                font-weight: 850;
                text-transform: uppercase;
                letter-spacing: 0.03em;
                margin-bottom: 5px;
            }

            .ts-error-mini-text {
                color: #334155;
                font-size: 13px;
                line-height: 1.4;
            }

            .ts-severity-critical {
                color: #991b1b;
                background: #fee2e2;
                border: 1px solid #fecaca;
            }

            .ts-severity-important {
                color: #92400e;
                background: #fef3c7;
                border: 1px solid #fde68a;
            }

            .ts-severity-recommendation {
                color: #166534;
                background: #dcfce7;
                border: 1px solid #bbf7d0;
            }

            .ts-chain-row {
                display: grid;
                grid-template-columns: 1fr auto 1fr;
                gap: 10px;
                align-items: center;
                color: #334155;
                font-size: 13px;
                padding: 8px 0;
                border-bottom: 1px solid #f1f5f9;
            }

            .ts-chain-row:last-child {
                border-bottom: 0;
            }

            .ts-chain-arrow {
                color: var(--ts-blue);
                font-weight: 900;
            }

            @media (max-width: 760px) {
                .ts-saas-hero {
                    flex-direction: column;
                    padding: 18px;
                }

                .ts-saas-hero-title {
                    font-size: 24px;
                }

                .ts-sites-header {
                    flex-direction: column;
                    padding: 18px;
                }

                .ts-audit-header {
                    flex-direction: column;
                    padding: 18px;
                }

                .ts-competitors-hero {
                    flex-direction: column;
                    padding: 18px;
                }

                .ts-chain-row {
                    grid-template-columns: 1fr;
                }

                .ts-error-grid {
                    grid-template-columns: 1fr;
                }

                .ts-integration-meta-grid {
                    grid-template-columns: 1fr;
                }
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
