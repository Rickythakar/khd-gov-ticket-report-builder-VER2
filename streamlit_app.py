from __future__ import annotations

import html
import json
from io import BytesIO
from pathlib import Path
import shutil
import uuid

import pandas as pd
import streamlit as st

from config import APP_NAME, APP_VERSION, DEFAULT_LOGO_PATH, REPORT_MODE_INTERNAL, REPORT_MODE_CUSTOMER
from settings import load_settings, save_settings, reset_settings, MODE_CUSTOMER, MODE_INTERNAL
from utils import (
    build_output_path,
    build_report_artifacts,
    build_report_title,
    default_filename_from_title,
    infer_date_range,
    infer_partner_name,
)
from validators import DataValidationResult, ValidationError, validate_and_prepare_dataframe


class WorkbookGenerationError(Exception):
    """Raised when workbook generation fails."""


class PdfSnapshotGenerationError(Exception):
    """Raised when PDF snapshot generation fails."""


st.set_page_config(page_title=APP_NAME, page_icon=":bar_chart:", layout="wide", initial_sidebar_state="expanded")


# ---------------------------------------------------------------------------
# Theme -- Cyber Neo-Brutalist with Kaseya Baby Blue
# ---------------------------------------------------------------------------

def apply_theme() -> None:
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;600;700;800;900&display=swap');

            :root {
                --cb-bg: #0A1219;
                --cb-primary: #009CDE;
                --cb-accent: #00D4FF;
                --cb-text: #D0E8F0;
                --cb-text-bright: #FFFFFF;
                --cb-text-muted: #5A7A8A;
                --cb-green: #00E676;
                --cb-red: #FF5252;
                --cb-card: rgba(10, 18, 25, 0.8);
                --cb-card-border: rgba(0, 156, 222, 0.35);
                --cb-sidebar: #080E14;
                --cb-input-bg: #0C1520;
                --cb-hover-glow: rgba(0, 156, 222, 0.25);
                --cb-accent-glow: rgba(0, 212, 255, 0.12);
                --cb-border-subtle: rgba(0, 156, 222, 0.2);
                --cb-dash: 1px dashed rgba(0, 156, 222, 0.3);
                --cb-mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
                --cb-sans: 'JetBrains Mono', 'Fira Code', monospace;
            }

            /* ---- Global ---- */
            .stApp {
                background: var(--cb-bg);
                color: var(--cb-text);
                font-family: var(--cb-mono);
                font-size: 0.88rem;
            }

            .block-container {
                max-width: 1440px;
                padding-top: 1rem;
                padding-bottom: 2rem;
            }

            *, *::before, *::after {
                transition: all 0.2s ease;
            }

            /* ---- Scrollbar ---- */
            ::-webkit-scrollbar {
                width: 6px;
                height: 6px;
            }
            ::-webkit-scrollbar-track {
                background: var(--cb-bg);
            }
            ::-webkit-scrollbar-thumb {
                background: var(--cb-primary);
                border-radius: 3px;
            }
            ::-webkit-scrollbar-thumb:hover {
                background: var(--cb-accent);
            }

            /* ---- Sidebar ---- */
            [data-testid="stSidebar"] {
                background: var(--cb-sidebar);
                border-right: 1px dashed rgba(0, 156, 222, 0.4);
            }

            [data-testid="stSidebar"] * {
                color: var(--cb-text) !important;
            }

            [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
                background: transparent;
                border: 1px dashed rgba(0, 156, 222, 0.35);
                border-radius: 2px;
                padding: 0.6rem !important;
                min-height: auto !important;
            }

            [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"]:hover {
                border-color: var(--cb-accent);
                background: rgba(0, 156, 222, 0.05);
            }

            [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] span {
                font-size: 0.75rem !important;
            }

            [data-testid="stSidebar"] input,
            [data-testid="stSidebar"] textarea {
                background: var(--cb-input-bg) !important;
                border: 1px solid var(--cb-border-subtle) !important;
                border-radius: 4px !important;
                color: var(--cb-text) !important;
                font-family: var(--cb-mono) !important;
            }

            [data-testid="stSidebar"] input:focus,
            [data-testid="stSidebar"] textarea:focus {
                border-color: var(--cb-accent) !important;
                box-shadow: 0 0 12px var(--cb-hover-glow) !important;
            }

            /* ---- Buttons ---- */
            .stButton > button {
                background: transparent !important;
                border: 1px solid var(--cb-primary) !important;
                border-radius: 2px !important;
                color: var(--cb-accent) !important;
                font-family: var(--cb-mono) !important;
                font-weight: 700 !important;
                font-size: 0.75rem !important;
                text-transform: uppercase !important;
                letter-spacing: 0.1em !important;
                padding: 0.4rem 0.8rem !important;
            }

            .stButton > button:hover {
                background: rgba(0, 156, 222, 0.1) !important;
                border-color: var(--cb-accent) !important;
                color: #FFFFFF !important;
                text-shadow: 0 0 8px rgba(0, 212, 255, 0.5) !important;
            }

            .stButton > button[kind="primary"],
            .stButton > button[data-testid="stBaseButton-primary"] {
                background: rgba(0, 156, 222, 0.15) !important;
                color: var(--cb-accent) !important;
                border-color: var(--cb-primary) !important;
            }

            .stButton > button[kind="primary"]:hover,
            .stButton > button[data-testid="stBaseButton-primary"]:hover {
                background: rgba(0, 156, 222, 0.25) !important;
                color: #FFFFFF !important;
                text-shadow: 0 0 10px rgba(0, 212, 255, 0.6) !important;
            }

            .stDownloadButton > button {
                background: rgba(0, 156, 222, 0.15) !important;
                border: 1px solid var(--cb-primary) !important;
                border-radius: 2px !important;
                color: var(--cb-accent) !important;
                font-family: var(--cb-mono) !important;
                font-weight: 700 !important;
                font-size: 0.75rem !important;
                text-transform: uppercase !important;
                letter-spacing: 0.1em !important;
            }

            .stDownloadButton > button:hover {
                background: rgba(0, 156, 222, 0.25) !important;
                color: #FFFFFF !important;
                text-shadow: 0 0 10px rgba(0, 212, 255, 0.6) !important;
            }

            /* ---- Radio as Bracket Toggle ---- */
            [data-testid="stSidebar"] [role="radiogroup"] {
                display: flex !important;
                gap: 0.4rem !important;
                padding: 0 !important;
                border: none !important;
            }

            [data-testid="stSidebar"] [role="radiogroup"] label {
                flex: 1 !important;
                background: transparent !important;
                border: 1px dashed rgba(0, 156, 222, 0.3) !important;
                border-radius: 0 !important;
                margin: 0 !important;
                padding: 0.4rem 0.3rem !important;
                text-align: center !important;
                font-family: var(--cb-mono) !important;
                font-size: 0.7rem !important;
                font-weight: 700 !important;
                letter-spacing: 0.08em !important;
                cursor: pointer !important;
                transition: all 0.2s ease !important;
                white-space: nowrap !important;
                color: var(--cb-text-muted) !important;
            }

            [data-testid="stSidebar"] [role="radiogroup"] label:hover {
                border-color: rgba(0, 156, 222, 0.6) !important;
                color: var(--cb-text) !important;
            }

            [data-testid="stSidebar"] [role="radiogroup"] label[data-checked="true"],
            [data-testid="stSidebar"] [role="radiogroup"] label[aria-checked="true"],
            [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked),
            [data-testid="stSidebar"] [role="radio"][aria-checked="true"] {
                border: 1px solid var(--cb-accent) !important;
                color: var(--cb-accent) !important;
                background: rgba(0, 212, 255, 0.08) !important;
                text-shadow: 0 0 8px rgba(0, 212, 255, 0.4) !important;
            }

            [data-testid="stSidebar"] [role="radiogroup"] label > div:first-child:not([data-testid="stMarkdownContainer"]) {
                display: none !important;
            }

            /* ---- Tabs ---- */
            button[data-baseweb="tab"] {
                color: var(--cb-text-muted) !important;
                font-size: 0.85rem !important;
                font-weight: 700 !important;
                text-transform: uppercase !important;
                letter-spacing: 0.08em !important;
                padding-left: 0.5rem !important;
                padding-right: 0.5rem !important;
                border-bottom: 2px solid transparent !important;
            }

            button[data-baseweb="tab"][aria-selected="true"] {
                color: var(--cb-accent) !important;
                font-weight: 800 !important;
                border-bottom: 2px solid var(--cb-accent) !important;
                text-shadow: 0 0 12px var(--cb-accent-glow);
            }

            button[data-baseweb="tab"] p {
                font-size: inherit !important;
                font-weight: inherit !important;
                color: inherit !important;
            }

            div[data-baseweb="tab-highlight"] {
                background-color: var(--cb-accent) !important;
            }

            /* ---- Expander ---- */
            [data-testid="stExpander"] {
                background: transparent;
                border: 1px dashed rgba(0, 156, 222, 0.3);
                border-radius: 0;
                margin-bottom: 0.4rem;
            }

            [data-testid="stExpander"]:hover {
                border-color: rgba(0, 156, 222, 0.6);
            }

            [data-testid="stExpander"] summary {
                color: var(--cb-text) !important;
                font-family: var(--cb-mono) !important;
                font-weight: 700 !important;
                font-size: 0.8rem !important;
                text-transform: uppercase !important;
                letter-spacing: 0.1em !important;
            }

            [data-testid="stExpander"] summary span {
                color: var(--cb-text) !important;
            }

            /* ---- Container / Cards ---- */
            [data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlock"] {
                background: transparent;
            }

            div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div.stMarkdown .cb-card) {
                border: none !important;
                background: transparent !important;
            }

            /* ---- DataFrames ---- */
            div[data-testid="stDataFrame"] {
                border-radius: 0;
                overflow: hidden;
                border: 1px dashed rgba(0, 156, 222, 0.25);
            }

            /* ---- Charts ---- */
            div[data-testid="stVegaLiteChart"] {
                border-radius: 4px;
                overflow: hidden;
            }

            /* ---- Inputs in main area ---- */
            .stTextInput input,
            .stNumberInput input,
            .stTextArea textarea {
                background: var(--cb-input-bg) !important;
                border: 1px solid var(--cb-border-subtle) !important;
                border-radius: 4px !important;
                color: var(--cb-text) !important;
            }

            .stTextInput input:focus,
            .stNumberInput input:focus,
            .stTextArea textarea:focus {
                border-color: var(--cb-accent) !important;
                box-shadow: 0 0 12px var(--cb-hover-glow) !important;
            }

            .stCheckbox label span {
                color: var(--cb-text) !important;
            }

            /* ---- Info / Error / Success ---- */
            [data-testid="stAlert"] {
                background: var(--cb-card) !important;
                border: 2px solid var(--cb-border-subtle) !important;
                border-radius: 4px !important;
                color: var(--cb-text) !important;
            }

            /* ---- Divider ---- */
            [data-testid="stSidebar"] hr {
                border-color: rgba(0, 156, 222, 0.2) !important;
            }

            hr {
                border-color: rgba(0, 156, 222, 0.15) !important;
            }

            /* ---- Dialog ---- */
            [data-testid="stDialog"] {
                background: var(--cb-bg) !important;
                border: 1px dashed var(--cb-primary) !important;
                border-radius: 0 !important;
            }

            [data-testid="stDialog"] * {
                color: var(--cb-text) !important;
            }

            /* ---- ASCII Logo ---- */
            .cb-ascii-logo {
                display: flex;
                align-items: center;
                gap: 0.6rem;
                padding: 0.3rem 0;
                margin-bottom: 0.3rem;
            }

            .cb-logo-hd {
                font-family: var(--cb-mono);
                font-size: 1.8rem;
                font-weight: 700;
                color: var(--cb-accent);
                line-height: 1;
                text-shadow: 0 0 12px rgba(0, 212, 255, 0.4);
            }

            .cb-logo-text {
                font-family: var(--cb-mono);
                font-size: 0.65rem;
                line-height: 1.35;
                color: var(--cb-text-muted);
                letter-spacing: 0.04em;
            }

            .cb-logo-text strong {
                color: var(--cb-text);
                font-size: 0.72rem;
            }

            /* ---- Custom Classes ---- */

            .cb-header-bar {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 0.4rem 0;
                margin-bottom: 0.6rem;
                border-bottom: 1px dashed rgba(0, 156, 222, 0.3);
            }

            .cb-header-title {
                font-family: var(--cb-mono);
                font-weight: 400;
                font-size: 0.85rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                color: var(--cb-text-muted);
            }

            .cb-header-chips {
                display: flex;
                gap: 0.5rem;
                align-items: center;
                flex-wrap: wrap;
            }

            .cb-chip {
                display: inline-block;
                padding: 0.15rem 0.5rem;
                border: none;
                font-family: var(--cb-mono);
                font-size: 0.72rem;
                color: var(--cb-text-muted);
                background: transparent;
            }

            .cb-chip::before { content: "[ "; color: rgba(0, 156, 222, 0.5); }
            .cb-chip::after { content: " ]"; color: rgba(0, 156, 222, 0.5); }

            .cb-chip--mode {
                color: var(--cb-accent);
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.06em;
            }

            .cb-metric-card {
                background: transparent;
                border: 1px dashed rgba(0, 156, 222, 0.3);
                border-radius: 0;
                padding: 0.7rem 0.8rem;
                min-height: 72px;
            }

            .cb-metric-card:hover {
                border-color: rgba(0, 156, 222, 0.6);
                background: rgba(0, 156, 222, 0.03);
            }

            .cb-metric-label {
                color: var(--cb-text-muted);
                font-family: var(--cb-mono);
                font-size: 0.65rem;
                text-transform: uppercase;
                letter-spacing: 0.12em;
                font-weight: 400;
            }

            .cb-metric-value {
                color: var(--cb-text-bright);
                font-family: var(--cb-mono);
                font-size: 1.5rem;
                font-weight: 700;
                margin-top: 0.15rem;
                line-height: 1.1;
            }

            /* ---- Mode Toggle ---- */
            .cb-mode-toggle {
                display: flex;
                border: 2px solid var(--cb-primary);
                border-radius: 4px;
                overflow: hidden;
                margin: 0.5rem 0;
            }

            .cb-mode-toggle .cb-mode-opt {
                flex: 1;
                padding: 0.5rem 0.4rem;
                text-align: center;
                font-family: var(--cb-mono);
                font-size: 0.72rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                cursor: pointer;
                color: var(--cb-text-muted);
                background: var(--cb-card);
                transition: all 0.25s ease;
            }

            .cb-mode-toggle .cb-mode-opt:hover {
                background: rgba(0, 156, 222, 0.1);
            }

            .cb-mode-toggle .cb-mode-opt.active {
                background: var(--cb-primary);
                color: #FFFFFF;
                text-shadow: 0 0 12px rgba(255,255,255,0.3);
                box-shadow: 0 0 16px rgba(0, 156, 222, 0.4);
            }

            /* ---- Widget Cards ---- */
            .cb-widget {
                background: linear-gradient(180deg, #0F1D2F 0%, #0C1825 100%);
                border: 2px solid rgba(0, 156, 222, 0.25);
                border-radius: 4px;
                padding: 0;
                margin-bottom: 0.6rem;
                overflow: hidden;
            }

            .cb-widget:hover {
                border-color: rgba(0, 156, 222, 0.5);
                box-shadow: 0 0 24px var(--cb-hover-glow);
            }

            .cb-widget-header {
                background: rgba(0, 156, 222, 0.08);
                border-bottom: 1px solid rgba(0, 156, 222, 0.2);
                padding: 0.55rem 0.9rem;
                display: flex;
                align-items: center;
                justify-content: space-between;
            }

            .cb-widget-title {
                font-family: var(--cb-mono);
                font-size: 0.78rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.1em;
                color: var(--cb-accent);
            }

            .cb-widget-badge {
                font-family: var(--cb-mono);
                font-size: 0.68rem;
                padding: 0.15rem 0.45rem;
                border: 1px solid rgba(0, 212, 255, 0.3);
                border-radius: 3px;
                color: var(--cb-accent);
                background: rgba(0, 212, 255, 0.06);
            }

            .cb-widget-body {
                padding: 0.8rem 0.9rem;
            }

            .cb-section-header {
                font-family: var(--cb-mono);
                font-size: 0.82rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.1em;
                color: var(--cb-text);
                margin-bottom: 0.3rem;
                padding-bottom: 0.3rem;
                border-bottom: 1px dashed rgba(0, 156, 222, 0.2);
            }

            .cb-pulse-band {
                background: transparent;
                border: 1px dashed rgba(0, 156, 222, 0.25);
                border-left: 3px solid var(--cb-accent);
                border-radius: 0;
                padding: 0.6rem 0.8rem;
                color: var(--cb-text);
                margin-bottom: 0.6rem;
                font-size: 0.82rem;
                font-family: var(--cb-mono);
            }

            .cb-state-band {
                background: transparent;
                border: 1px dashed rgba(0, 156, 222, 0.2);
                border-radius: 0;
                padding: 0.5rem 0.8rem;
                color: var(--cb-text-muted);
                margin-bottom: 0.6rem;
                font-family: var(--cb-mono);
                font-size: 0.8rem;
                text-align: center;
            }

            .cb-empty-workspace {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                min-height: 340px;
                text-align: center;
            }

            .cb-empty-title {
                font-family: var(--cb-mono);
                font-size: 1.1rem;
                font-weight: 400;
                text-transform: uppercase;
                letter-spacing: 0.12em;
                color: var(--cb-text-muted);
                margin-bottom: 0.5rem;
            }

            .cb-empty-title::before { content: "> "; color: var(--cb-accent); }

            .cb-empty-sub {
                font-family: var(--cb-mono);
                font-size: 0.78rem;
                color: rgba(90, 122, 138, 0.6);
            }

            .cb-list-clean {
                margin: 0;
                padding-left: 0;
                list-style: none;
            }

            .cb-list-clean li {
                margin-bottom: 0.45rem;
                line-height: 1.5;
                color: var(--cb-text);
                font-size: 0.92rem;
            }

            .cb-list-clean li::before {
                content: ">";
                color: var(--cb-accent);
                font-family: var(--cb-mono);
                font-weight: 700;
                margin-right: 0.55rem;
            }

            .cb-context-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 0.6rem;
                margin-top: 0.25rem;
            }

            .cb-context-card {
                background: var(--cb-card);
                border: 2px solid var(--cb-border-subtle);
                border-radius: 4px;
                padding: 0.7rem 0.85rem;
            }

            .cb-context-card:hover {
                border-color: var(--cb-primary);
                box-shadow: 0 0 16px var(--cb-hover-glow);
            }

            .cb-context-label {
                font-size: 0.68rem;
                text-transform: uppercase;
                letter-spacing: 0.1em;
                color: var(--cb-text-muted);
                margin-bottom: 0.2rem;
                font-weight: 700;
            }

            .cb-context-value {
                color: var(--cb-text);
                font-family: var(--cb-mono);
                font-size: 0.92rem;
                font-weight: 700;
                line-height: 1.3;
                word-break: break-word;
            }

            .cb-export-card {
                background: var(--cb-card);
                border: 3px solid var(--cb-border-subtle);
                border-radius: 4px;
                padding: 1.2rem;
                text-align: center;
                cursor: pointer;
                min-height: 140px;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
            }

            .cb-export-card:hover {
                border-color: var(--cb-accent);
                box-shadow: 0 0 24px var(--cb-hover-glow);
            }

            .cb-export-icon {
                font-size: 2rem;
                margin-bottom: 0.5rem;
            }

            .cb-export-title {
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 0.06em;
                font-size: 0.95rem;
                color: var(--cb-text);
                margin-bottom: 0.3rem;
            }

            .cb-export-desc {
                font-size: 0.8rem;
                color: var(--cb-text-muted);
            }

            .cb-sidebar-logo {
                display: flex;
                justify-content: center;
                margin-bottom: 0.5rem;
            }

            .cb-sidebar-logo img {
                max-width: 180px;
                height: auto;
            }

            .cb-sidebar-btn-row {
                display: flex;
                gap: 0.5rem;
                margin-top: 0.3rem;
            }

            .cb-brutalist-header {
                font-family: var(--cb-sans);
                font-size: 1.15rem;
                font-weight: 900;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                color: var(--cb-text-muted);
                margin-top: 1rem;
                margin-bottom: 0.5rem;
            }

            .cb-debug-box {
                background: var(--cb-card);
                border: 1px solid var(--cb-border-subtle);
                border-radius: 4px;
                padding: 0.7rem 0.85rem;
                font-family: var(--cb-mono);
                font-size: 0.82rem;
                white-space: pre-wrap;
                color: var(--cb-text-muted);
                max-height: 300px;
                overflow-y: auto;
            }

            .cb-download-row {
                background: var(--cb-card);
                border: 2px solid var(--cb-primary);
                border-radius: 4px;
                padding: 0.8rem 1rem;
                margin-bottom: 0.8rem;
                display: flex;
                align-items: center;
                gap: 1rem;
            }

            .cb-download-label {
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.06em;
                font-size: 0.85rem;
                color: var(--cb-accent);
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Render Helpers
# ---------------------------------------------------------------------------

def render_metric(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="cb-metric-card">
            <div class="cb-metric-label">{html.escape(label)}</div>
            <div class="cb-metric-value">{html.escape(value)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_list(lines: list[str]) -> None:
    items = "".join(f"<li>{html.escape(str(line))}</li>" for line in lines) if lines else "<li>No items yet.</li>"
    st.markdown(f'<ul class="cb-list-clean">{items}</ul>', unsafe_allow_html=True)


def render_header_bar(title: str, partner_name: str, date_range: str, mode: str = "") -> None:
    chips: list[str] = []
    if mode == MODE_INTERNAL:
        chips.append('<span class="cb-chip cb-chip--mode">Internal</span>')
    elif mode == MODE_CUSTOMER:
        chips.append('<span class="cb-chip cb-chip--mode">Customer</span>')
    if partner_name.strip():
        chips.append(f'<span class="cb-chip">{html.escape(partner_name.strip())}</span>')
    if date_range.strip():
        chips.append(f'<span class="cb-chip">{html.escape(date_range.strip())}</span>')
    chip_markup = "".join(chips)

    st.markdown(
        f"""
        <div class="cb-header-bar">
            <div class="cb-header-title">{html.escape(APP_NAME)}</div>
            <div class="cb-header-chips">{chip_markup}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(title: str, copy: str = "") -> None:
    copy_markup = f'<div style="color:var(--cb-text-muted);font-size:0.88rem;margin-top:0.15rem;">{html.escape(copy)}</div>' if copy else ""
    st.markdown(f'<div class="cb-section-header">{html.escape(title)}</div>{copy_markup}', unsafe_allow_html=True)


def render_pulse_band(text: str) -> None:
    st.markdown(f'<div class="cb-pulse-band"><strong>Pulse:</strong> {html.escape(text)}</div>', unsafe_allow_html=True)


def render_state_band(text: str) -> None:
    st.markdown(f'<div class="cb-state-band">{html.escape(text)}</div>', unsafe_allow_html=True)


def render_empty_workspace() -> None:
    st.markdown(
        """
        <div class="cb-empty-workspace">
            <div class="cb-empty-title">Upload a Ticket CSV to Begin</div>
            <div class="cb-empty-sub">Drop a file in the sidebar to start building the governance report.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_context_cards(items: list[tuple[str, str]], *, sidebar: bool = False) -> None:
    markup = "".join(
        f'<div class="cb-context-card"><div class="cb-context-label">{html.escape(str(label))}</div><div class="cb-context-value">{html.escape(str(value))}</div></div>'
        for label, value in items
    )
    st.markdown(f'<div class="cb-context-grid">{markup}</div>', unsafe_allow_html=True)


def _table_height(row_count: int, *, max_height: int = 420) -> int:
    return min(max_height, 42 + 35 * (max(row_count, 1) + 1))


def render_dataframe_block(title: str, dataframe: pd.DataFrame, empty_message: str, *, max_height: int = 420) -> None:
    st.markdown(f"#### {title}")
    if dataframe.empty:
        st.info(empty_message)
        return
    st.dataframe(
        dataframe,
        width="stretch",
        hide_index=True,
        height=_table_height(len(dataframe), max_height=max_height),
    )


def _truncate_chart_label(value: object, limit: int = 34) -> str:
    text = str(value)
    return text if len(text) <= limit else f"{text[: limit - 1].rstrip()}..."


def render_table_and_chart(title: str, dataframe: pd.DataFrame, index_column: str) -> None:
    import altair as alt

    if dataframe.empty:
        st.info(f"No {title.lower()} available in this file.")
        return
    st.markdown(f"#### {title}")
    st.dataframe(dataframe, width="stretch", hide_index=True, height=_table_height(len(dataframe), max_height=360))

    chart_df = dataframe.copy()
    chart_df["Label"] = chart_df[index_column].apply(_truncate_chart_label)
    chart_height = max(240, min(520, 48 + (len(chart_df) * 36)))
    chart = (
        alt.Chart(chart_df)
        .mark_bar(color="#009CDE", cornerRadiusEnd=3)
        .encode(
            x=alt.X("Tickets:Q", title="Tickets"),
            y=alt.Y("Label:N", sort="-x", title=None, axis=alt.Axis(labelLimit=320, labelFontSize=12)),
            tooltip=[
                alt.Tooltip(f"{index_column}:N", title=index_column),
                alt.Tooltip("Tickets:Q", title="Tickets"),
                alt.Tooltip("Share:Q", title="Share", format=".1f"),
            ],
        )
        .properties(height=chart_height)
    )
    st.altair_chart(chart, width="stretch")


# ---------------------------------------------------------------------------
# Preserved business logic functions (DO NOT MODIFY)
# ---------------------------------------------------------------------------

def apply_pending_sidebar_defaults() -> None:
    pending_partner = st.session_state.pop("pending_partner_name_autofill", "")
    if pending_partner:
        current_partner_name = st.session_state.get("partner_name", "").strip()
        previous_partner_autofill = st.session_state.get("partner_name_autofill", "").strip()
        if not current_partner_name or current_partner_name == previous_partner_autofill:
            st.session_state["partner_name"] = pending_partner
        st.session_state["partner_name_autofill"] = pending_partner
    pending_date_range = st.session_state.pop("pending_date_range_autofill", "")
    if pending_date_range:
        current_date_range = st.session_state.get("date_range", "").strip()
        previous_date_autofill = st.session_state.get("date_range_autofill", "").strip()
        if not current_date_range or current_date_range == previous_date_autofill:
            st.session_state["date_range"] = pending_date_range
        st.session_state["date_range_autofill"] = pending_date_range


def settings_to_queue_override_text(settings: dict) -> str:
    overrides = settings.get("sla_queue_overrides", {})
    return "\n".join(f"{queue}={minutes}" for queue, minutes in overrides.items())


def apply_pending_settings_refresh() -> None:
    pending_settings = st.session_state.pop("pending_settings_refresh", None)
    if not pending_settings:
        return

    st.session_state["app_settings"] = pending_settings
    st.session_state["settings_mode"] = pending_settings.get("mode", MODE_CUSTOMER)

    sla_targets = pending_settings.get("sla_targets", {})
    for priority in ["Critical", "High", "Medium", "Low", "None"]:
        st.session_state[f"sla_{priority}"] = int(sla_targets.get(priority, 1440))

    st.session_state["sla_queue_overrides_text"] = settings_to_queue_override_text(pending_settings)

    noise = pending_settings.get("noise_filter", {})
    st.session_state["noise_spam"] = noise.get("hide_spam", True)
    st.session_state["noise_sync"] = noise.get("hide_sync_errors", True)
    st.session_state["danger_threshold"] = int(pending_settings.get("danger_zone_threshold", 3))
    st.session_state["expert_mode"] = bool(pending_settings.get("expert_mode", False))


def push_status(message: str) -> None:
    log = st.session_state.setdefault("status_log", [])
    log.append(message)


def read_logo_bytes(uploaded_logo) -> bytes:
    if uploaded_logo is not None:
        return uploaded_logo.getvalue()
    if DEFAULT_LOGO_PATH.exists():
        return DEFAULT_LOGO_PATH.read_bytes()
    raise ValidationError("Upload a PNG logo or add `assets/hd_services_logo.png` to the project.")


@st.cache_data(show_spinner="Building workbook...")
def build_workbook_bytes(
    prepared_df: pd.DataFrame,
    report_title: str,
    logo_bytes: bytes,
    output_filename: str,
    partner_name: str,
    date_range: str,
    report_mode: str = REPORT_MODE_CUSTOMER,
    settings: dict | None = None,
) -> bytes:
    from excel_builder import ExcelBuilderError, ExcelReportBuilder, ReportRequest

    workspace_temp_root = Path.cwd() / ".tmp_exports"
    workspace_temp_root.mkdir(parents=True, exist_ok=True)
    temp_dir = workspace_temp_root / f"khd-report-{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        temp_logo = temp_dir / "logo.png"
        temp_output = temp_dir / output_filename
        temp_logo.write_bytes(logo_bytes)

        builder = ExcelReportBuilder(status_callback=push_status)
        request = ReportRequest(
            dataframe=prepared_df,
            report_title=report_title,
            logo_path=temp_logo,
            output_path=temp_output,
            partner_name=partner_name,
            date_range=date_range,
            report_mode=report_mode,
            settings=settings,
        )
        built_path = builder.build_report(request)
        return built_path.read_bytes()
    except ExcelBuilderError as exc:
        raise WorkbookGenerationError(str(exc)) from exc
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        try:
            if workspace_temp_root.exists() and not any(workspace_temp_root.iterdir()):
                workspace_temp_root.rmdir()
        except OSError:
            pass


@st.cache_data(show_spinner="Building executive PDF snapshot...")
def build_pdf_snapshot_bytes(
    *,
    artifacts,
    report_title: str,
    logo_bytes: bytes | None,
    partner_name: str,
    date_range: str,
) -> bytes:
    from pdf_builder import ExecutivePdfSnapshotBuilder, PdfBuilderError

    builder = ExecutivePdfSnapshotBuilder()
    try:
        return builder.build_pdf_bytes(
            report_title=report_title,
            partner_name=partner_name,
            date_range=date_range,
            artifacts=artifacts,
            logo_bytes=logo_bytes,
        )
    except PdfBuilderError as exc:
        raise PdfSnapshotGenerationError(str(exc)) from exc


@st.cache_data(show_spinner="Inspecting CSV...")
def inspect_uploaded_csv(csv_bytes: bytes) -> tuple[pd.DataFrame, DataValidationResult, str, str]:
    raw_df = pd.read_csv(BytesIO(csv_bytes))
    validation_result = validate_and_prepare_dataframe(raw_df)
    prepared_df = validation_result.dataframe
    inferred_partner_name = infer_partner_name(prepared_df)
    inferred_date_range = infer_date_range(prepared_df)
    return prepared_df, validation_result, inferred_partner_name, inferred_date_range


@st.cache_data(show_spinner="Parsing and analyzing CSV...")
def analyze_uploaded_csv(
    csv_bytes: bytes,
    report_mode: str = REPORT_MODE_CUSTOMER,
    settings: dict | None = None,
) -> tuple[pd.DataFrame, object, str, str, DataValidationResult]:
    prepared_df, validation_result, inferred_partner_name, inferred_date_range = inspect_uploaded_csv(csv_bytes)
    artifacts = build_report_artifacts(prepared_df, report_mode=report_mode, settings=settings)
    return prepared_df, artifacts, inferred_partner_name, inferred_date_range, validation_result


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------

@st.dialog("Settings", width="large")
def open_settings_dialog() -> None:
    app_settings = st.session_state.get("app_settings") or load_settings()

    settings_tab, sla_tab, about_tab = st.tabs(["GENERAL", "SLA TARGETS", "ABOUT & DEBUG"])

    with settings_tab:
        left_col, right_col = st.columns(2, gap="medium")

        with left_col:
            st.markdown("**REPORT MODE**")
            mode_options = [MODE_CUSTOMER, MODE_INTERNAL]
            mode_labels = {MODE_CUSTOMER: "Customer Deliverable", MODE_INTERNAL: "Internal Analysis"}
            selected_mode = st.radio(
                "Mode",
                options=mode_options,
                format_func=lambda m: mode_labels.get(m, m),
                key="dlg_settings_mode",
                index=mode_options.index(app_settings.get("mode", MODE_CUSTOMER)),
                label_visibility="collapsed",
            )
            app_settings["mode"] = selected_mode

            st.markdown("")
            st.markdown("**EXPERT MODE**")
            app_settings["expert_mode"] = st.checkbox(
                "Show full diagnostics and advanced detail",
                value=bool(app_settings.get("expert_mode", False)),
                key="dlg_expert_mode",
            )

        with right_col:
            st.markdown("**NOISE FILTERING**")
            noise = app_settings.get("noise_filter", {})
            noise["hide_spam"] = st.checkbox("Hide spam tickets", value=noise.get("hide_spam", True), key="dlg_noise_spam")
            noise["hide_sync_errors"] = st.checkbox("Hide sync-error tickets", value=noise.get("hide_sync_errors", True), key="dlg_noise_sync")
            app_settings["noise_filter"] = noise
            app_settings["danger_zone_threshold"] = st.number_input(
                "Danger zone threshold (repeat contacts)",
                min_value=2,
                max_value=50,
                value=int(app_settings.get("danger_zone_threshold", 3)),
                key="dlg_danger_threshold",
            )

    with sla_tab:
        st.markdown("**SLA TARGETS (MINUTES)**")
        sla = app_settings.get("sla_targets", {})
        sla_cols = st.columns(5, gap="small")
        for idx, priority in enumerate(["Critical", "High", "Medium", "Low", "None"]):
            with sla_cols[idx]:
                sla[priority] = st.number_input(
                    priority,
                    min_value=1,
                    max_value=10080,
                    step=15,
                    value=int(sla.get(priority, 1440)),
                    key=f"dlg_sla_{priority}",
                )
        app_settings["sla_targets"] = sla

        st.markdown("")
        st.markdown("**QUEUE OVERRIDES**")
        st.caption("Override SLA target for specific queues (one per line, format: Queue=Minutes)")
        override_text = st.text_area(
            "Queue=Minutes",
            value=settings_to_queue_override_text(app_settings),
            height=68,
            key="dlg_sla_queue_overrides_text",
            help="Example: KHD - Triage=15",
            label_visibility="collapsed",
        )
        parsed_overrides = {}
        for line in override_text.strip().splitlines():
            if "=" in line:
                parts = line.split("=", 1)
                try:
                    parsed_overrides[parts[0].strip()] = int(parts[1].strip())
                except ValueError:
                    pass
        app_settings["sla_queue_overrides"] = parsed_overrides

    with about_tab:
        st.markdown(f"**{APP_NAME}**")
        st.markdown(f"Version `{APP_VERSION}`")
        st.caption("Local-only governance report builder. No external APIs or cloud services.")

        st.markdown("")
        st.markdown("**STATUS LOG**")
        status_text = "\n".join(st.session_state.get("status_log", [])) or "No activity yet."
        st.markdown(f'<div class="cb-debug-box">{html.escape(status_text)}</div>', unsafe_allow_html=True)

        st.markdown("")
        st.markdown("**DETECTED COLUMNS**")
        detected_columns = st.session_state.get("detected_columns", [])
        if detected_columns:
            st.markdown(f'<div class="cb-debug-box">{html.escape(", ".join(detected_columns))}</div>', unsafe_allow_html=True)
        else:
            st.caption("Upload a CSV to review detected columns.")

        missing_required_columns = st.session_state.get("missing_required_columns", [])
        if missing_required_columns:
            st.markdown("**MISSING REQUIRED FIELDS**")
            st.warning(f"{', '.join(missing_required_columns)} -- These fields were not found. The app will leave those fields blank where needed.")

        st.markdown("")
        st.markdown("**BRANDING**")
        st.file_uploader(
            "Logo PNG",
            type=["png"],
            help="Optional if `assets/hd_services_logo.png` already exists.",
            key="uploaded_logo",
        )

    st.divider()
    btn_left, btn_right, _ = st.columns([1, 1, 2])
    with btn_left:
        if st.button("SAVE", type="primary", key="dlg_save_settings", use_container_width=True):
            st.session_state["settings_mode"] = app_settings.get("mode", MODE_CUSTOMER)
            sla_targets = app_settings.get("sla_targets", {})
            for priority in ["Critical", "High", "Medium", "Low", "None"]:
                st.session_state[f"sla_{priority}"] = int(sla_targets.get(priority, 1440))
            st.session_state["sla_queue_overrides_text"] = settings_to_queue_override_text(app_settings)
            noise_s = app_settings.get("noise_filter", {})
            st.session_state["noise_spam"] = noise_s.get("hide_spam", True)
            st.session_state["noise_sync"] = noise_s.get("hide_sync_errors", True)
            st.session_state["danger_threshold"] = int(app_settings.get("danger_zone_threshold", 3))
            st.session_state["expert_mode"] = bool(app_settings.get("expert_mode", False))

            save_settings(app_settings)
            st.session_state["app_settings"] = app_settings
            push_status("Settings saved")
            st.toast("Settings saved")
            st.rerun()
    with btn_right:
        if st.button("RESET DEFAULTS", key="dlg_reset_settings", use_container_width=True):
            app_settings = reset_settings()
            st.session_state["pending_settings_refresh"] = app_settings
            push_status("Settings reset to defaults")
            st.rerun()


@st.dialog("Export Report", width="large")
def open_export_dialog() -> None:
    prepared_df = st.session_state.get("prepared_df")
    artifacts = st.session_state.get("artifacts")
    app_settings = st.session_state.get("app_settings") or load_settings()

    if prepared_df is None or artifacts is None:
        st.warning("No analyzed data. Upload and analyze a CSV first.")
        return

    partner_name = st.session_state.get("partner_name", "").strip()
    date_range = st.session_state.get("date_range", "").strip()

    title_col, file_col = st.columns(2, gap="medium")
    with title_col:
        report_title = st.text_input("Report Title", key="report_title")
    with file_col:
        output_filename = st.text_input("Output Filename", key="output_filename")

    final_title = build_report_title(partner_name, date_range, report_title)
    st.divider()

    wb_bytes = st.session_state.get("workbook_bytes")
    pdf_bytes = st.session_state.get("pdf_snapshot_bytes")

    if wb_bytes or pdf_bytes:
        st.markdown("**EXPORTS READY**")
        if wb_bytes:
            st.download_button(
                label="Download Workbook",
                data=wb_bytes,
                file_name=st.session_state.get("workbook_name", "khd_ticket_report.xlsx"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True,
            )
        if pdf_bytes:
            st.download_button(
                label="Download PDF Snapshot",
                data=pdf_bytes,
                file_name=st.session_state.get("pdf_snapshot_name", "khd_ticket_report_executive_snapshot.pdf"),
                mime="application/pdf",
                use_container_width=True,
            )
        st.divider()

    st.markdown("**GENERATE NEW EXPORT**")
    col_wb, col_full = st.columns(2, gap="medium")

    with col_wb:
        st.markdown(
            """
            <div class="cb-export-card">
                <div class="cb-export-icon">&#128218;</div>
                <div class="cb-export-title">Workbook Only</div>
                <div class="cb-export-desc">Excel workbook with summary, tickets, and escalation sheets.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        gen_wb = st.button("Generate Workbook", key="dlg_gen_wb", use_container_width=True, type="primary")

    with col_full:
        st.markdown(
            """
            <div class="cb-export-card">
                <div class="cb-export-icon">&#128196;&#128218;</div>
                <div class="cb-export-title">Workbook + PDF Snapshot</div>
                <div class="cb-export-desc">Full workbook plus an executive PDF snapshot for stakeholders.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        gen_full = st.button("Generate Both", key="dlg_gen_full", use_container_width=True)

    if gen_wb or gen_full:
        st.session_state["status_log"] = []
        st.session_state["workbook_bytes"] = None
        st.session_state["workbook_name"] = ""
        st.session_state["pdf_snapshot_bytes"] = None
        st.session_state["pdf_snapshot_name"] = ""
        try:
            logo_bytes = read_logo_bytes(st.session_state.get("uploaded_logo"))
            final_filename = build_output_path(".", output_filename.strip() or default_filename_from_title(final_title)).name
            push_status("Preparing workbook")
            workbook_bytes = build_workbook_bytes(
                prepared_df=prepared_df,
                report_title=final_title,
                logo_bytes=logo_bytes,
                output_filename=final_filename,
                partner_name=partner_name,
                date_range=date_range,
                report_mode=artifacts.report_mode,
                settings=app_settings,
            )
            st.session_state["workbook_bytes"] = workbook_bytes
            st.session_state["workbook_name"] = final_filename
            push_status("Workbook ready for download")

            if gen_full and artifacts is not None:
                push_status("Generating PDF snapshot")
                try:
                    pdf_snapshot_bytes = build_pdf_snapshot_bytes(
                        artifacts=artifacts,
                        report_title=final_title,
                        logo_bytes=logo_bytes,
                        partner_name=partner_name,
                        date_range=date_range,
                    )
                    pdf_name = f"{default_filename_from_title(final_title)}_Executive_Snapshot.pdf"
                    st.session_state["pdf_snapshot_bytes"] = pdf_snapshot_bytes
                    st.session_state["pdf_snapshot_name"] = pdf_name
                    push_status("PDF snapshot ready for download")
                except PdfSnapshotGenerationError as exc:
                    push_status(f"PDF error: {exc}")
                    st.error(f"PDF generation failed: {exc}")

            st.success("Export complete.")
            st.rerun()
        except (ValidationError, WorkbookGenerationError) as exc:
            push_status(f"Error: {exc}")
            st.error(str(exc))
        except Exception as exc:
            push_status(f"Unexpected error: {exc}")
            st.error(f"Unexpected error: {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    apply_theme()
    apply_pending_sidebar_defaults()

    st.session_state.setdefault(
        "status_log",
        [
            f"Version {APP_VERSION} ready.",
            "Version 1 focuses on a cleaner governance-review workflow, workbook-first export, and more flexible Autotask CSV handling.",
            "Load a CSV to begin.",
        ],
    )
    st.session_state.setdefault("workbook_bytes", None)
    st.session_state.setdefault("workbook_name", "")
    st.session_state.setdefault("partner_name", "")
    st.session_state.setdefault("partner_name_autofill", "")
    st.session_state.setdefault("date_range", "")
    st.session_state.setdefault("date_range_autofill", "")
    st.session_state.setdefault("report_title", "")
    st.session_state.setdefault("report_title_autofill", "")
    st.session_state.setdefault("output_filename", "")
    st.session_state.setdefault("output_filename_autofill", "")
    st.session_state.setdefault("prepared_df", None)
    st.session_state.setdefault("artifacts", None)
    st.session_state.setdefault("analysis_error", "")
    st.session_state.setdefault("analyzed_file_token", "")
    st.session_state.setdefault("analyzed_settings_token", "")
    st.session_state.setdefault("detected_columns", [])
    st.session_state.setdefault("missing_required_columns", [])
    st.session_state.setdefault("pending_partner_name_autofill", "")
    st.session_state.setdefault("pending_date_range_autofill", "")
    st.session_state.setdefault("enable_pdf_snapshot", False)
    st.session_state.setdefault("pdf_snapshot_bytes", None)
    st.session_state.setdefault("pdf_snapshot_name", "")
    st.session_state.setdefault("app_settings", load_settings())
    apply_pending_settings_refresh()
    app_settings = st.session_state.get("app_settings") or load_settings()
    st.session_state["app_settings"] = app_settings
    settings_token = json.dumps(app_settings, sort_keys=True, default=str)

    # Initialize settings defaults for re-analysis
    st.session_state.setdefault("settings_mode", app_settings.get("mode", MODE_CUSTOMER))
    sla_init = app_settings.get("sla_targets", {})
    for priority in ["Critical", "High", "Medium", "Low", "None"]:
        st.session_state.setdefault(f"sla_{priority}", int(sla_init.get(priority, 1440)))
    st.session_state.setdefault("sla_queue_overrides_text", settings_to_queue_override_text(app_settings))
    noise_init = app_settings.get("noise_filter", {})
    st.session_state.setdefault("noise_spam", noise_init.get("hide_spam", True))
    st.session_state.setdefault("noise_sync", noise_init.get("hide_sync_errors", True))
    st.session_state.setdefault("danger_threshold", int(app_settings.get("danger_zone_threshold", 3)))
    st.session_state.setdefault("expert_mode", bool(app_settings.get("expert_mode", False)))

    prepared_df = None
    artifacts = None
    error_message = None
    inferred_partner_name = ""
    inferred_date_range = ""
    detected_columns: list[str] = st.session_state.get("detected_columns", [])
    missing_required_columns: list[str] = st.session_state.get("missing_required_columns", [])

    # -----------------------------------------------------------------------
    # Sidebar
    # -----------------------------------------------------------------------
    with st.sidebar:
        st.markdown(
            '<div class="cb-ascii-logo">'
            '<span class="cb-logo-hd">HD</span>'
            '<span class="cb-logo-text">Kaseya<br><strong>Help Desk</strong><br>Services</span>'
            '</div>',
            unsafe_allow_html=True,
        )

        st.markdown("")
        uploaded_csv = st.file_uploader("Ticket CSV", type=["csv"], key="uploaded_csv")

        # Auto-analyze logic (PRESERVED)
        if uploaded_csv is not None:
            file_token = f"{uploaded_csv.name}:{uploaded_csv.size}"

            if (
                file_token != st.session_state.get("analyzed_file_token", "")
                or settings_token != st.session_state.get("analyzed_settings_token", "")
            ):
                st.session_state["workbook_bytes"] = None
                st.session_state["workbook_name"] = ""
                st.session_state["pdf_snapshot_bytes"] = None
                st.session_state["pdf_snapshot_name"] = ""
                try:
                    csv_bytes = uploaded_csv.getvalue()
                    prepared_df, artifacts, inferred_partner_name, inferred_date_range, validation_result = analyze_uploaded_csv(
                        csv_bytes,
                        report_mode=REPORT_MODE_INTERNAL if app_settings.get("mode") == MODE_INTERNAL else REPORT_MODE_CUSTOMER,
                        settings=app_settings,
                    )
                    detected_columns = [str(column_name) for column_name in validation_result.column_mapping.values()]
                    missing_required_columns = list(validation_result.missing_columns)
                    st.session_state["prepared_df"] = prepared_df
                    st.session_state["artifacts"] = artifacts
                    st.session_state["analysis_error"] = ""
                    st.session_state["analyzed_file_token"] = file_token
                    st.session_state["analyzed_settings_token"] = settings_token
                    st.session_state["detected_columns"] = detected_columns
                    st.session_state["missing_required_columns"] = missing_required_columns
                    push_status("Auto-analysis complete")
                    if missing_required_columns:
                        push_status(f"Missing fields: {', '.join(missing_required_columns)}")
                except ValidationError as exc:
                    error_message = str(exc)
                    st.session_state["prepared_df"] = None
                    st.session_state["artifacts"] = None
                    st.session_state["detected_columns"] = []
                    st.session_state["missing_required_columns"] = []
                except Exception as exc:
                    error_message = f"Could not read the CSV: {exc}"
                    st.session_state["prepared_df"] = None
                    st.session_state["artifacts"] = None
                    st.session_state["detected_columns"] = []
                    st.session_state["missing_required_columns"] = []
            else:
                detected_columns = st.session_state.get("detected_columns", [])
                missing_required_columns = st.session_state.get("missing_required_columns", [])
        else:
            st.session_state["prepared_df"] = None
            st.session_state["artifacts"] = None
            st.session_state["analysis_error"] = ""
            st.session_state["analyzed_file_token"] = ""
            st.session_state["analyzed_settings_token"] = ""
            st.session_state["workbook_bytes"] = None
            st.session_state["workbook_name"] = ""
            st.session_state["pdf_snapshot_bytes"] = None
            st.session_state["pdf_snapshot_name"] = ""
            st.session_state["detected_columns"] = []
            st.session_state["missing_required_columns"] = []

        # Autofill logic (PRESERVED)
        if inferred_partner_name:
            current_partner_name = st.session_state.get("partner_name", "").strip()
            previous_partner_autofill = st.session_state.get("partner_name_autofill", "").strip()
            if not current_partner_name or current_partner_name == previous_partner_autofill:
                st.session_state["partner_name"] = inferred_partner_name
            st.session_state["partner_name_autofill"] = inferred_partner_name
        if inferred_date_range:
            current_date_range = st.session_state.get("date_range", "").strip()
            previous_date_autofill = st.session_state.get("date_range_autofill", "").strip()
            if not current_date_range or current_date_range == previous_date_autofill:
                st.session_state["date_range"] = inferred_date_range
            st.session_state["date_range_autofill"] = inferred_date_range

        auto_title_seed = build_report_title(
            st.session_state.get("partner_name", ""),
            st.session_state.get("date_range", ""),
        )
        if (
            not st.session_state.get("report_title", "").strip()
            or st.session_state.get("report_title", "").strip() == st.session_state.get("report_title_autofill", "").strip()
        ):
            st.session_state["report_title"] = auto_title_seed
            st.session_state["report_title_autofill"] = auto_title_seed

        auto_filename_seed = default_filename_from_title(st.session_state.get("report_title", "") or auto_title_seed)
        if (
            not st.session_state.get("output_filename", "").strip()
            or st.session_state.get("output_filename", "").strip() == st.session_state.get("output_filename_autofill", "").strip()
        ):
            st.session_state["output_filename"] = auto_filename_seed
            st.session_state["output_filename_autofill"] = auto_filename_seed

        partner_name = st.session_state.get("partner_name", "").strip()
        date_range = st.session_state.get("date_range", "").strip()
        auto_title_live = build_report_title(partner_name, date_range)
        if (
            not st.session_state.get("report_title", "").strip()
            or st.session_state.get("report_title", "").strip() == st.session_state.get("report_title_autofill", "").strip()
        ):
            st.session_state["report_title"] = auto_title_live
            st.session_state["report_title_autofill"] = auto_title_live
        report_title = st.session_state.get("report_title", "").strip()

        auto_filename_live = default_filename_from_title(report_title or auto_title_live)
        if (
            not st.session_state.get("output_filename", "").strip()
            or st.session_state.get("output_filename", "").strip() == st.session_state.get("output_filename_autofill", "").strip()
        ):
            st.session_state["output_filename"] = auto_filename_live
            st.session_state["output_filename_autofill"] = auto_filename_live
        output_filename = st.session_state.get("output_filename", "").strip()

        st.divider()

        selected_mode = st.radio(
            "MODE",
            options=[MODE_CUSTOMER, MODE_INTERNAL],
            format_func=lambda m: {MODE_CUSTOMER: "PARTNER", MODE_INTERNAL: "INTERNAL"}.get(m, m),
            key="settings_mode",
            horizontal=True,
        )
        app_settings["mode"] = selected_mode

        st.markdown("")
        btn_left, btn_right = st.columns(2, gap="small")
        with btn_left:
            if st.button("Export", type="primary", use_container_width=True, disabled=st.session_state.get("prepared_df") is None, key="sidebar_export_btn"):
                open_export_dialog()
        with btn_right:
            if st.button("Settings", use_container_width=True, key="sidebar_settings_btn"):
                open_settings_dialog()

    # -----------------------------------------------------------------------
    # Main area
    # -----------------------------------------------------------------------
    final_title = build_report_title(partner_name, date_range, report_title)

    # Header bar
    render_header_bar(final_title, partner_name, date_range, mode=app_settings.get("mode", MODE_CUSTOMER))

    prepared_df = st.session_state.get("prepared_df")
    artifacts = st.session_state.get("artifacts")
    analysis_error = st.session_state.get("analysis_error", "")

    if error_message:
        st.error(error_message)
    elif analysis_error:
        st.error(analysis_error)

    # Download row (if exports are available)
    wb_bytes = st.session_state.get("workbook_bytes")
    pdf_bytes = st.session_state.get("pdf_snapshot_bytes")
    if wb_bytes or pdf_bytes:
        dl_cols = st.columns([1, 1, 2] if pdf_bytes else [1, 3])
        with dl_cols[0]:
            if wb_bytes:
                st.download_button(
                    label="Download Workbook",
                    data=wb_bytes,
                    file_name=st.session_state.get("workbook_name", "khd_ticket_report.xlsx"),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True,
                )
        if pdf_bytes:
            with dl_cols[1]:
                st.download_button(
                    label="Download PDF Snapshot",
                    data=pdf_bytes,
                    file_name=st.session_state.get("pdf_snapshot_name", "khd_ticket_report_executive_snapshot.pdf"),
                    mime="application/pdf",
                    use_container_width=True,
                )

    # Empty state
    if prepared_df is None and not error_message and not analysis_error:
        render_empty_workspace()

    # Dashboard
    if prepared_df is not None and artifacts is not None:
        is_internal = app_settings.get("mode") == MODE_INTERNAL

        # --- Metric cards row ---
        all_metrics = list(artifacts.headline_metrics[:9])
        if all_metrics:
            rows = [all_metrics[i : i + 3] for i in range(0, len(all_metrics), 3)]
            for row in rows:
                cols = st.columns(3)
                for idx, (label, value) in enumerate(row):
                    with cols[idx]:
                        render_metric(label, value)
            st.markdown("")

        # --- WHAT DO YOU WANT TO KNOW? ---
        st.markdown('<div class="cb-brutalist-header">What Do You Want to Know?</div>', unsafe_allow_html=True)

        # --- Executive Brief ---
        with st.expander("EXECUTIVE BRIEF", expanded=False):
            brief_left, brief_right = st.columns([1.3, 0.7], gap="large")
            with brief_left:
                render_section_header("Brief Points")
                render_list(artifacts.executive_brief_points)
            with brief_right:
                render_section_header("Review Topics")
                render_list(artifacts.priority_actions[:4])
            if artifacts.service_observations:
                render_pulse_band(artifacts.service_observations[0])

        # --- Resolution Time ---
        with st.expander("RESOLUTION TIME", expanded=False):
            rm = artifacts.resolution_metrics
            if rm and rm.median_minutes > 0:
                from metrics import format_minutes as _fmt_min
                res_cols = st.columns(4)
                with res_cols[0]:
                    render_metric("Median", _fmt_min(rm.median_minutes))
                with res_cols[1]:
                    render_metric("Mean", _fmt_min(rm.mean_minutes))
                with res_cols[2]:
                    render_metric("P90", _fmt_min(rm.p90_minutes))
                with res_cols[3]:
                    render_metric("P95", _fmt_min(rm.p95_minutes))
                st.markdown("")
                res_sub = st.tabs(["By Queue", "By Priority", "By Issue Type"])
                with res_sub[0]:
                    render_dataframe_block("Resolution by Queue", rm.by_queue, "No queue breakdown available.", max_height=360)
                with res_sub[1]:
                    render_dataframe_block("Resolution by Priority", rm.by_priority, "No priority breakdown available.", max_height=360)
                with res_sub[2]:
                    render_dataframe_block("Resolution by Issue Type", rm.by_issue_type, "No issue type breakdown available.", max_height=360)
            else:
                st.info("No resolution time data available.")

        # --- SLA Compliance ---
        with st.expander("SLA COMPLIANCE", expanded=False):
            sla = artifacts.sla_metrics
            if sla and sla.overall_compliance > 0:
                st.markdown(f"#### Overall SLA Compliance: **{sla.overall_compliance}%**")
                render_dataframe_block("Compliance by Priority", sla.by_priority, "No SLA data available.", max_height=300)
                if not sla.breaching_tickets.empty:
                    st.markdown(f"#### SLA Breaches ({len(sla.breaching_tickets)} tickets)")
                    st.dataframe(sla.breaching_tickets, width="stretch", hide_index=True, height=_table_height(len(sla.breaching_tickets)))
            else:
                st.info("No SLA compliance data available. Configure SLA targets in Settings.")

        # --- Queue & Escalation ---
        with st.expander("QUEUE & ESCALATION", expanded=False):
            render_table_and_chart("Queue Distribution", artifacts.queue_table, "Queue")
            st.divider()
            reason_tab, category_tab = st.tabs(["Escalation Reasons", "Escalation Categories"])
            with reason_tab:
                render_table_and_chart("Escalation Reasons", artifacts.escalation_table, "Escalation Reason")
            with category_tab:
                if not artifacts.escalation_category_table.empty:
                    import altair as alt
                    st.markdown("#### Escalation Reason Categories")
                    st.dataframe(artifacts.escalation_category_table, width="stretch", hide_index=True, height=_table_height(len(artifacts.escalation_category_table), max_height=360))
                    category_chart = artifacts.escalation_category_table.groupby("Category", as_index=False)["Tickets"].sum().sort_values("Tickets", ascending=False)
                    category_chart["Label"] = category_chart["Category"]
                    st.altair_chart(
                        alt.Chart(category_chart).mark_bar(color="#009CDE", cornerRadiusEnd=3).encode(
                            x=alt.X("Tickets:Q", title="Tickets"),
                            y=alt.Y("Label:N", sort="-x", title=None),
                            tooltip=[alt.Tooltip("Category:N", title="Category"), alt.Tooltip("Tickets:Q", title="Tickets")],
                        ).properties(height=max(220, 44 + len(category_chart) * 40)),
                        width="stretch",
                    )
                else:
                    st.info("No escalated tickets were found, so category reporting is empty.")

        # --- Coverage ---
        with st.expander("COVERAGE", expanded=False):
            coverage_left, coverage_right = st.columns(2, gap="large")
            with coverage_left:
                render_dataframe_block("Customer Accounts", artifacts.company_table, "No customer account summary available.", max_height=320)
            with coverage_right:
                render_dataframe_block("Request Types", artifacts.issue_type_table, "No request type summary available.", max_height=320)
            sub_cols = st.columns([0.18, 0.64, 0.18], gap="large")
            with sub_cols[1]:
                render_dataframe_block("Sub-Issue Types", artifacts.sub_issue_type_table, "No sub-issue summary available.", max_height=320)

        # --- Danger Zone ---
        with st.expander("DANGER ZONE", expanded=False):
            dz_left, dz_right = st.columns(2, gap="large")
            with dz_left:
                st.markdown("#### Repeat Contacts")
                rc = artifacts.repeat_contacts
                if rc is not None and not rc.empty:
                    st.dataframe(rc, width="stretch", hide_index=True, height=_table_height(len(rc), max_height=360))
                else:
                    st.info("No repeat contacts detected above the threshold.")
            with dz_right:
                st.markdown("#### High-Escalation Companies")
                dz = artifacts.danger_zone_companies
                if dz is not None and not dz.empty:
                    st.dataframe(dz.head(15), width="stretch", hide_index=True, height=_table_height(min(len(dz), 15), max_height=360))
                else:
                    st.info("No danger zone companies detected.")
            ah = artifacts.after_hours_metrics
            if ah and ah.total_after_hours > 0:
                st.markdown(f"#### After-Hours Tickets: **{ah.total_after_hours}** ({ah.after_hours_rate}%)")
                ah_cols = st.columns(3)
                with ah_cols[0]:
                    render_metric("Weekend", str(ah.weekend_count))
                with ah_cols[1]:
                    render_metric("Weekday After-Hours", str(ah.weekday_after_hours))
                with ah_cols[2]:
                    render_metric("FCR Rate", f"{artifacts.fcr_rate}%")

        # --- Technicians (internal only) ---
        if is_internal:
            with st.expander("TECHNICIANS", expanded=False):
                st.markdown("#### Technician Scorecards")
                st.caption("Internal analysis only -- not included in customer deliverables.")
                tech = artifacts.technician_scorecards
                if tech is not None and not tech.empty:
                    st.dataframe(tech, width="stretch", hide_index=True, height=_table_height(len(tech), max_height=520))
                else:
                    st.info("No technician data available (Primary Resource column may be missing).")
                noise = artifacts.noise_metrics
                if noise and noise.total_noise > 0:
                    st.markdown(f"#### Noise Tickets: **{noise.total_noise}** ({noise.noise_rate}%)")
                    noise_cols = st.columns(2)
                    with noise_cols[0]:
                        render_metric("Spam", str(noise.spam_count))
                    with noise_cols[1]:
                        render_metric("Sync Errors", str(noise.sync_error_count))
                    if not noise.noise_df.empty:
                        preview_cols = [c for c in ["Ticket Number", "Title", "Queue", "Source"] if c in noise.noise_df.columns]
                        st.dataframe(noise.noise_df[preview_cols].head(20), width="stretch", hide_index=True, height=_table_height(min(len(noise.noise_df), 20)))

        # --- Raw Data (internal only) ---
        if is_internal:
            with st.expander("RAW DATA", expanded=False):
                preview_tabs = st.tabs(["Completed Tickets", "Escalated Tickets", "Normalized Data"])
                with preview_tabs[0]:
                    st.dataframe(artifacts.tickets_view, width="stretch", hide_index=True, height=420)
                with preview_tabs[1]:
                    if artifacts.escalated_df.empty:
                        st.info("No escalated tickets were found in this file.")
                    else:
                        st.dataframe(artifacts.escalated_df, width="stretch", hide_index=True, height=420)
                with preview_tabs[2]:
                    st.dataframe(artifacts.normalized_df, width="stretch", hide_index=True, height=420)



if __name__ == "__main__":
    main()
