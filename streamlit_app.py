from __future__ import annotations

import html
from io import BytesIO
from pathlib import Path
import shutil
import uuid

import pandas as pd
import streamlit as st

from config import APP_NAME, APP_VERSION, DEFAULT_LOGO_PATH
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


def apply_theme() -> None:
    st.markdown(
        """
        <style>
            :root {
                --app-navy: #113a62;
                --app-blue: #1d6fa7;
                --app-sky: #5caad3;
                --app-ink: #17324d;
                --app-muted: #607588;
                --app-border: rgba(17, 58, 98, 0.10);
                --app-panel: rgba(255, 255, 255, 0.96);
                --app-bg: #edf3f8;
            }

            .stApp {
                background:
                    radial-gradient(circle at top left, rgba(29, 111, 167, 0.10), transparent 28%),
                    linear-gradient(180deg, #f5f9fc 0%, var(--app-bg) 100%);
                color: var(--app-ink);
            }

            .block-container {
                max-width: 1440px;
                padding-top: 1.1rem;
                padding-bottom: 2rem;
            }

            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, #254d79 0%, #2e5f93 100%);
                border-right: 1px solid rgba(255,255,255,0.08);
            }

            [data-testid="stSidebar"] * {
                color: #f7fbff;
            }

            [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
                background: rgba(8, 15, 24, 0.62);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 16px;
            }

            [data-testid="stSidebar"] input {
                background: rgba(10, 16, 24, 0.82) !important;
                border-radius: 14px !important;
            }

            .hero {
                background:
                    radial-gradient(circle at top right, rgba(255,255,255,0.22), transparent 26%),
                    linear-gradient(135deg, #103f67 0%, #17588d 58%, #4aa1cf 100%);
                border-radius: 28px;
                padding: 2rem 2.1rem;
                color: white;
                box-shadow: 0 18px 42px rgba(13, 43, 70, 0.12);
                margin-bottom: 1.15rem;
                position: relative;
                overflow: hidden;
            }

            .hero h1 {
                margin: 0;
                font-size: 2.2rem;
                letter-spacing: -0.03em;
                line-height: 1.05;
            }

            .hero p {
                margin: 0.7rem 0 0 0;
                max-width: 920px;
                color: rgba(255,255,255,0.88);
                line-height: 1.55;
                font-size: 1rem;
            }

            .hero-meta {
                display: inline-flex;
                gap: 0.6rem;
                flex-wrap: wrap;
                margin-top: 1rem;
            }

            .hero-chip {
                display: inline-block;
                padding: 0.28rem 0.55rem;
                border-radius: 8px;
                background: rgba(255,255,255,0.10);
                border: 1px solid rgba(255,255,255,0.14);
                font-size: 0.84rem;
                color: rgba(244, 251, 255, 0.92);
            }

            .section-title {
                font-size: 1.1rem;
                font-weight: 700;
                color: var(--app-ink);
                margin-bottom: 0.2rem;
            }

            .section-copy {
                color: var(--app-muted);
                margin-bottom: 0.9rem;
                line-height: 1.52;
            }

            .metric-card {
                background: #ffffff;
                border: 1px solid var(--app-border);
                border-radius: 12px;
                padding: 1rem 1rem 0.9rem 1rem;
                min-height: 96px;
                box-shadow: none;
                position: relative;
            }

            .metric-card::before {
                content: "";
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 4px;
                border-radius: 18px 18px 0 0;
                background: linear-gradient(90deg, var(--app-blue) 0%, var(--app-sky) 100%);
            }

            .metric-label {
                color: #6a8195;
                font-size: 0.75rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                padding-top: 0.25rem;
            }

            .metric-value {
                color: #123d62;
                font-size: 1.6rem;
                font-weight: 800;
                margin-top: 0.28rem;
                line-height: 1.1;
            }

            .pulse-band {
                background: #f7fafc;
                border: 1px solid var(--app-border);
                border-radius: 12px;
                padding: 0.95rem 1rem;
                color: var(--app-ink);
                margin-bottom: 1rem;
            }

            .state-band {
                background: #f7fafc;
                border: 1px solid var(--app-border);
                border-radius: 12px;
                padding: 0.85rem 1rem;
                color: var(--app-ink);
                margin-bottom: 1rem;
                font-weight: 600;
            }

            .stage-card {
                background: #ffffff;
                border: 1px solid var(--app-border);
                border-radius: 12px;
                padding: 1rem 1rem 0.95rem 1rem;
                min-height: 150px;
            }

            .workflow-card {
                background: #ffffff;
                border: 1px solid var(--app-border);
                border-radius: 12px;
                padding: 0.95rem 1rem 1rem 1rem;
                min-height: 132px;
                position: relative;
                box-shadow: none;
            }

            .workflow-card--active {
                border-color: rgba(17, 58, 98, 0.18);
                background: #fcfdff;
            }

            .workflow-step {
                color: #74879a;
                font-size: 0.7rem;
                letter-spacing: 0.09em;
                text-transform: uppercase;
                font-weight: 700;
                margin-bottom: 0.35rem;
            }

            .workflow-title {
                color: var(--app-ink);
                font-size: 1rem;
                font-weight: 700;
                margin-bottom: 0.35rem;
            }

            .workflow-copy {
                color: var(--app-muted);
                line-height: 1.45;
                font-size: 0.92rem;
            }

            .workflow-badge {
                position: static;
                display: inline-block;
                margin-bottom: 0.55rem;
                padding: 0;
                border-radius: 0;
                font-size: 0.72rem;
                font-weight: 700;
                letter-spacing: 0.04em;
                background: transparent;
                color: #5d7287;
                border: 0;
            }

            .deliverable-card {
                background: #ffffff;
                border: 1px solid var(--app-border);
                border-radius: 12px;
                padding: 1rem 1rem 0.95rem 1rem;
                min-height: 180px;
                box-shadow: none;
            }

            .deliverable-kicker {
                color: #6a8195;
                font-size: 0.74rem;
                letter-spacing: 0.09em;
                text-transform: uppercase;
                font-weight: 700;
                margin-bottom: 0.45rem;
            }

            .deliverable-title {
                color: var(--app-ink);
                font-size: 1.08rem;
                font-weight: 800;
                margin-bottom: 0.45rem;
            }

            .deliverable-copy {
                color: var(--app-muted);
                line-height: 1.52;
                font-size: 0.95rem;
                margin-bottom: 0.7rem;
            }

            .deliverable-note {
                color: #123d62;
                font-size: 0.87rem;
                font-weight: 700;
            }

            .stage-kicker {
                color: #6a8195;
                font-size: 0.74rem;
                letter-spacing: 0.09em;
                text-transform: uppercase;
                margin-bottom: 0.45rem;
                font-weight: 700;
            }

            .stage-title {
                color: var(--app-ink);
                font-size: 1.08rem;
                font-weight: 700;
                margin-bottom: 0.45rem;
            }

            .stage-copy {
                color: var(--app-muted);
                line-height: 1.5;
                font-size: 0.96rem;
            }

            .mini-note {
                color: var(--app-muted);
                font-size: 0.92rem;
                line-height: 1.5;
            }

            .context-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 0.8rem;
                margin-top: 0.25rem;
            }

            .context-card {
                background: linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(245,249,252,0.98) 100%);
                border: 1px solid var(--app-border);
                border-radius: 18px;
                padding: 0.9rem 0.95rem;
                box-shadow: 0 8px 24px rgba(17, 58, 98, 0.06);
            }

            .context-card--sidebar {
                background: rgba(8, 15, 24, 0.24);
                border: 1px solid rgba(255,255,255,0.10);
                box-shadow: none;
            }

            .context-label {
                font-size: 0.74rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                color: #6a8195;
                margin-bottom: 0.35rem;
                font-weight: 700;
            }

            .context-card--sidebar .context-label {
                color: rgba(247, 251, 255, 0.72);
            }

            .context-value {
                color: var(--app-ink);
                font-size: 1rem;
                font-weight: 700;
                line-height: 1.3;
                word-break: break-word;
            }

            .context-card--sidebar .context-value {
                color: #f7fbff;
            }

            .sidebar-actions {
                margin-top: 0.55rem;
                margin-bottom: 0.15rem;
            }

            .context-panel {
                background: linear-gradient(180deg, #ffffff 0%, #f8fbfd 100%);
                border: 1px solid var(--app-border);
                border-radius: 20px;
                padding: 1rem 1.05rem;
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.75);
            }

            .list-clean {
                margin: 0;
                padding-left: 1.15rem;
            }

            .list-clean li {
                margin-bottom: 0.5rem;
                line-height: 1.52;
                color: var(--app-ink);
            }

            .status-box {
                background: #f8fbfd;
                border: 1px solid var(--app-border);
                border-radius: 16px;
                padding: 0.95rem 1rem;
                font-family: Consolas, monospace;
                min-height: 120px;
                white-space: pre-wrap;
                color: var(--app-ink);
            }

            .status-box--sidebar {
                background: rgba(8, 15, 24, 0.42);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 16px;
                padding: 0.9rem 0.95rem;
                font-family: Consolas, monospace;
                min-height: 120px;
                white-space: pre-wrap;
                color: #f7fbff;
                font-size: 0.9rem;
            }

            .status-scroll-box {
                background: rgba(8, 15, 24, 0.42);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 16px;
                padding: 0.7rem 0.85rem;
                max-height: 220px;
                overflow-y: auto;
                color: #f7fbff;
                font-family: Consolas, monospace;
                font-size: 0.88rem;
                line-height: 1.45;
            }

            .status-note-box {
                background: rgba(169, 68, 66, 0.16);
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 14px;
                padding: 0.7rem 0.85rem;
                color: #fce7e7;
                font-size: 0.9rem;
                line-height: 1.45;
            }

            .status-log-label {
                color: rgba(247, 251, 255, 0.72);
                font-size: 0.76rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                font-weight: 700;
                margin-bottom: 0.2rem;
            }

            .status-log-value {
                color: #f7fbff;
                font-size: 0.98rem;
                font-weight: 700;
                margin-bottom: 0.8rem;
                line-height: 1.3;
            }

            div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stTabs"]) {
                margin-top: 0.15rem;
            }

            button[data-baseweb="tab"] {
                color: #4e6478 !important;
                font-size: 0.96rem !important;
                font-weight: 600 !important;
                letter-spacing: 0 !important;
                padding-left: 0.25rem !important;
                padding-right: 0.25rem !important;
            }

            button[data-baseweb="tab"][aria-selected="true"] {
                color: #123d62 !important;
                font-weight: 700 !important;
            }

            button[data-baseweb="tab"] p {
                font-size: 0.96rem !important;
                font-weight: inherit !important;
                color: inherit !important;
            }

            div[data-testid="stDataFrame"] {
                border-radius: 16px;
                overflow: hidden;
                border: 1px solid var(--app-border);
            }

            div[data-testid="stPlotlyChart"], div[data-testid="stVegaLiteChart"] {
                border-radius: 16px;
                overflow: hidden;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero(title: str, partner_name: str, date_range: str) -> None:
    chips: list[str] = []
    if partner_name.strip():
        chips.append(f'<span class="hero-chip">Partner: {partner_name.strip()}</span>')
    if date_range.strip():
        chips.append(f'<span class="hero-chip">Period: {date_range.strip()}</span>')
    chip_markup = "".join(chips)

    st.markdown(
        f"""
        <div class="hero">
            <h1>{APP_NAME}</h1>
            <p>
                Turn an Autotask Ticket Export into an executive-ready service review
                for MSP partners, product owners, and leadership stakeholders.
            </p>
            <p style="font-weight:700;">{title}</p>
            {f'<div class="hero-meta">{chip_markup}</div>' if chip_markup else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(title: str, copy: str = "") -> None:
    copy_markup = f'<div class="section-copy">{copy}</div>' if copy else ""
    st.markdown(f'<div class="section-title">{title}</div>{copy_markup}', unsafe_allow_html=True)


def render_metric(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_workbook_download_control(container, workbook_bytes: bytes | None, workbook_name: str) -> None:
    with container:
        st.download_button(
            label="Download Excel Workbook",
            data=workbook_bytes or b"",
            file_name=workbook_name or "khd_ticket_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
            type="primary",
            disabled=workbook_bytes is None,
        )
        if workbook_bytes is None:
            st.caption("Generate the workbook to enable the download.")


def render_pulse_band(text: str) -> None:
    st.markdown(f'<div class="pulse-band"><strong>Delivery Pulse:</strong> {text}</div>', unsafe_allow_html=True)


def render_state_band(text: str) -> None:
    st.markdown(f'<div class="state-band">{text}</div>', unsafe_allow_html=True)

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


def push_status(message: str) -> None:
    log = st.session_state.setdefault("status_log", [])
    log.append(message)


def read_logo_bytes(uploaded_logo) -> bytes:
    if uploaded_logo is not None:
        return uploaded_logo.getvalue()
    if DEFAULT_LOGO_PATH.exists():
        return DEFAULT_LOGO_PATH.read_bytes()
    raise ValidationError("Upload a PNG logo or add `assets/hd_services_logo.png` to the project.")


def build_workbook_bytes(
    prepared_df: pd.DataFrame,
    report_title: str,
    logo_bytes: bytes,
    output_filename: str,
    partner_name: str,
    date_range: str,
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


def render_list(lines: list[str]) -> None:
    items = "".join(f"<li>{html.escape(str(line))}</li>" for line in lines) if lines else "<li>No items yet.</li>"
    st.markdown(f'<ul class="list-clean">{items}</ul>', unsafe_allow_html=True)


def render_context_cards(items: list[tuple[str, str]], *, sidebar: bool = False) -> None:
    card_class = "context-card context-card--sidebar" if sidebar else "context-card"
    markup = "".join(
        f'<div class="{card_class}"><div class="context-label">{html.escape(str(label))}</div><div class="context-value">{html.escape(str(value))}</div></div>'
        for label, value in items
    )
    st.markdown(f'<div class="context-grid">{markup}</div>', unsafe_allow_html=True)


def render_deliverable_card(kicker: str, title: str, copy: str, note: str) -> None:
    st.markdown(
        f"""
        <div class="deliverable-card">
            <div class="deliverable-kicker">{html.escape(kicker)}</div>
            <div class="deliverable-title">{html.escape(title)}</div>
            <div class="deliverable-copy">{html.escape(copy)}</div>
            <div class="deliverable-note">{html.escape(note)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_status_scroll_box(lines: list[str], empty_message: str = "No items to show.") -> None:
    if not lines:
        content = html.escape(empty_message)
    else:
        content = "<br>".join(html.escape(str(line)) for line in lines)
    st.markdown(f'<div class="status-scroll-box">{content}</div>', unsafe_allow_html=True)


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
    return text if len(text) <= limit else f"{text[: limit - 1].rstrip()}…"


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
        .mark_bar(color="#76B4E6", cornerRadiusEnd=3)
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


def render_empty_workspace() -> None:
    render_state_band("Upload a ticket CSV to begin building the governance workbook.")

    with st.container(border=True):
        render_section_header("Getting Started", "This app takes a completed-ticket CSV, summarizes the reporting period, and prepares a workbook for partner governance review.")
        render_list(
            [
                "Upload the Autotask ticket CSV.",
                "Analyze the file to detect the reporting context and build the review summary.",
                "Generate the workbook when the report context and summary look right.",
            ]
        )

    st.markdown("")
    with st.container(border=True):
        render_section_header("What The Workbook Includes", "The workbook remains the primary deliverable and is structured for service review conversations.")
        render_list(
            [
                "Dashboard summary with factual service-review context and suggested talking points.",
                "Tickets sheet with queue distribution, request type distribution, and completed-ticket detail.",
                "Escalation sheet with escalation categories, sources, reasons, and drill-down detail.",
                "Hidden raw-data support sheet for traceability.",
            ]
        )


def render_pre_analysis_workspace(file_name: str, file_size_kb: float, inferred_partner_name: str, date_range: str) -> None:
    partner_text = inferred_partner_name or "Pending detection"
    render_state_band("CSV loaded. Click Analyze Workbook to build the service summary and workbook preview.")

    top_left, top_right = st.columns([1.05, 0.95], gap="large")
    with top_left:
        with st.container(border=True):
            render_section_header("File Loaded", "The CSV is ready for analysis.")
            render_context_cards(
                [
                    ("Loaded File", file_name),
                    ("Approx Size", f"{file_size_kb:.1f} KB"),
                    ("Partner Detected", partner_text),
                    ("Date Range Detected", date_range or "Pending detection"),
                ]
            )

    with top_right:
        with st.container(border=True):
            render_section_header("Next Step", "Analysis will build the factual service summary, suggested review topics, and workbook preview.")
            render_list(
                [
                    "Reporting period, ticket volume, queue distribution, request type distribution, and intake channel distribution.",
                    "Observed patterns from the CSV that can support governance talking points.",
                    "Workbook sections and export options for the final deliverable.",
                ]
            )


def inspect_uploaded_csv(uploaded_csv) -> tuple[pd.DataFrame, DataValidationResult, str, str]:
    csv_bytes = uploaded_csv.getvalue()
    raw_df = pd.read_csv(BytesIO(csv_bytes))
    validation_result = validate_and_prepare_dataframe(raw_df)
    prepared_df = validation_result.dataframe
    inferred_partner_name = infer_partner_name(prepared_df)
    inferred_date_range = infer_date_range(prepared_df)
    return prepared_df, validation_result, inferred_partner_name, inferred_date_range


def analyze_uploaded_csv(uploaded_csv) -> tuple[pd.DataFrame, object, str, str, DataValidationResult]:
    prepared_df, validation_result, inferred_partner_name, inferred_date_range = inspect_uploaded_csv(uploaded_csv)
    artifacts = build_report_artifacts(prepared_df)
    return prepared_df, artifacts, inferred_partner_name, inferred_date_range, validation_result


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
    st.session_state.setdefault("detected_columns", [])
    st.session_state.setdefault("missing_required_columns", [])
    st.session_state.setdefault("pending_partner_name_autofill", "")
    st.session_state.setdefault("pending_date_range_autofill", "")
    st.session_state.setdefault("enable_pdf_snapshot", False)

    prepared_df = None
    artifacts = None
    error_message = None
    inferred_partner_name = ""
    inferred_date_range = ""
    detected_columns: list[str] = st.session_state.get("detected_columns", [])
    missing_required_columns: list[str] = st.session_state.get("missing_required_columns", [])
    preflight_file_name = ""
    preflight_file_size_kb = 0.0

    with st.sidebar:
        sidebar_artifacts = st.session_state.get("artifacts")
        st.markdown("## Report Controls")
        st.caption("Load the CSV, review the detected report context, analyze the service story, then export the workbook.")

        uploaded_logo = None
        uploaded_csv = st.file_uploader("Ticket CSV", type=["csv"], key="uploaded_csv")
        st.markdown('<div class="sidebar-actions"></div>', unsafe_allow_html=True)
        button_left, button_right = st.columns(2, gap="small")
        with button_left:
            analyze = st.button("Analyze Workbook", width="stretch")
        with button_right:
            generate = st.button(
                "Generate Workbook",
                type="primary",
                width="stretch",
                disabled=st.session_state.get("prepared_df") is None,
            )

        if uploaded_csv is not None:
            preflight_file_name = uploaded_csv.name
            preflight_file_size_kb = round(uploaded_csv.size / 1024, 1)
            try:
                prepared_preview_df, validation_result, inferred_partner_name, inferred_date_range = inspect_uploaded_csv(uploaded_csv)
                detected_columns = [str(column_name) for column_name in validation_result.column_mapping.values()]
                missing_required_columns = list(validation_result.missing_columns)
                st.session_state["detected_columns"] = detected_columns
                st.session_state["missing_required_columns"] = missing_required_columns
            except ValidationError as exc:
                error_message = str(exc)
                st.session_state["detected_columns"] = []
                st.session_state["missing_required_columns"] = []
            except Exception as exc:
                error_message = f"Could not read the CSV: {exc}"
                st.session_state["detected_columns"] = []
                st.session_state["missing_required_columns"] = []
        else:
            st.session_state["prepared_df"] = None
            st.session_state["artifacts"] = None
            st.session_state["analysis_error"] = ""
            st.session_state["analyzed_file_token"] = ""
            st.session_state["workbook_bytes"] = None
            st.session_state["workbook_name"] = ""
            st.session_state["detected_columns"] = []
            st.session_state["missing_required_columns"] = []

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
        st.markdown("### Export Options")
        report_title = st.text_input("Report Title", key="report_title")
        output_filename = st.text_input("Output Filename", key="output_filename")
        enable_pdf_snapshot = st.checkbox(
            "Enable optional executive PDF snapshot",
            key="enable_pdf_snapshot",
            help="Keeps the workbook as the main export and adds a secondary PDF snapshot option when enabled.",
        )
        workbook_download_slot = st.empty()
        render_workbook_download_control(
            workbook_download_slot,
            st.session_state.get("workbook_bytes"),
            st.session_state.get("workbook_name", ""),
        )

        if enable_pdf_snapshot:
            if sidebar_artifacts is not None:
                try:
                    logo_bytes = None
                    try:
                        logo_bytes = read_logo_bytes(uploaded_logo)
                    except ValidationError:
                        logo_bytes = None
                    pdf_snapshot_name = f"{default_filename_from_title(build_report_title(partner_name, date_range, report_title))}_Executive_Snapshot.pdf"
                    pdf_snapshot_bytes = build_pdf_snapshot_bytes(
                        artifacts=sidebar_artifacts,
                        report_title=build_report_title(partner_name, date_range, report_title),
                        logo_bytes=logo_bytes,
                        partner_name=partner_name,
                        date_range=date_range,
                    )
                    st.download_button(
                        label="Download Executive PDF Snapshot",
                        data=pdf_snapshot_bytes,
                        file_name=pdf_snapshot_name or "khd_ticket_report_executive_snapshot.pdf",
                        mime="application/pdf",
                        width="stretch",
                    )
                except PdfSnapshotGenerationError as exc:
                    st.warning(str(exc))
            else:
                st.info("Analyze a valid CSV to make the optional PDF snapshot available.")

        st.divider()
        st.markdown("### Status Log")
        status_text = "\n".join(st.session_state.get("status_log", [])) or "No workbook generated yet."
        st.markdown(
            f'<div class="status-log-label">Application version</div><div class="status-log-value">{APP_VERSION}</div>'
            f'<div class="status-log-label">Partner detected</div><div class="status-log-value">{partner_name or "Pending detection"}</div>'
            f'<div class="status-log-label">Date range detected</div><div class="status-log-value">{date_range or "Pending detection"}</div>'
            f'<div class="status-log-label">Run log</div><div class="status-box--sidebar">{html.escape(status_text)}</div>',
            unsafe_allow_html=True,
        )
        st.markdown("#### Detected Columns")
        render_status_scroll_box(detected_columns, "Upload a CSV to review detected columns.")
        if missing_required_columns:
            missing_list = ", ".join(missing_required_columns)
            st.markdown(
                f'<div class="status-log-label" style="margin-top:0.75rem;">Missing Required Fields</div>'
                f'<div class="status-note-box">{html.escape(missing_list)}<br><br>These fields were not found in the upload. '
                'The app will keep running and leave those fields blank where needed.</div>',
                unsafe_allow_html=True,
            )

        st.divider()
        with st.expander("Branding", expanded=False):
            uploaded_logo = st.file_uploader(
                "Logo PNG",
                type=["png"],
                help="Optional if `assets/hd_services_logo.png` already exists.",
                key="uploaded_logo",
            )
            st.markdown(
                f'<div class="mini-note"><strong>Partner:</strong> {partner_name or "Pending detection"}<br>'
                f'<strong>Workbook title:</strong> {report_title or "Pending detection"}<br>'
                f'<strong>Output file:</strong> {output_filename or "Pending detection"}<br>'
                f'<strong>Logo source:</strong> {uploaded_logo.name if uploaded_logo is not None else (DEFAULT_LOGO_PATH.name if DEFAULT_LOGO_PATH.exists() else "No default logo")}<br>'
                f'<strong>Logo mode:</strong> {"Uploaded logo" if uploaded_logo is not None else ("Bundled default logo" if DEFAULT_LOGO_PATH.exists() else "No logo available")}</div>',
                unsafe_allow_html=True,
            )

    file_token = f"{uploaded_csv.name}:{uploaded_csv.size}" if uploaded_csv is not None else ""
    if file_token and st.session_state.get("analyzed_file_token") and file_token != st.session_state.get("analyzed_file_token"):
        st.session_state["prepared_df"] = None
        st.session_state["artifacts"] = None
        st.session_state["analysis_error"] = ""
        st.session_state["workbook_bytes"] = None
        st.session_state["workbook_name"] = ""
        st.session_state["detected_columns"] = []
        st.session_state["missing_required_columns"] = []

    if analyze and uploaded_csv is None:
        st.session_state["analysis_error"] = "Upload a CSV before analyzing the workbook."

    if analyze and uploaded_csv is not None:
            try:
                prepared_df, artifacts, inferred_from_analysis, inferred_date_from_analysis, validation_result = analyze_uploaded_csv(uploaded_csv)
                st.session_state["prepared_df"] = prepared_df
                st.session_state["artifacts"] = artifacts
                st.session_state["analysis_error"] = ""
                st.session_state["analyzed_file_token"] = file_token
                st.session_state["detected_columns"] = [str(column_name) for column_name in validation_result.column_mapping.values()]
                st.session_state["missing_required_columns"] = list(validation_result.missing_columns)
                if inferred_from_analysis:
                    st.session_state["pending_partner_name_autofill"] = inferred_from_analysis
                if inferred_date_from_analysis:
                    st.session_state["pending_date_range_autofill"] = inferred_date_from_analysis
                push_status("Workbook analysis updated")
                if validation_result.missing_columns:
                    push_status(f"Missing fields detected: {', '.join(validation_result.missing_columns)}")
                st.rerun()
            except ValidationError as exc:
                st.session_state["prepared_df"] = None
                st.session_state["artifacts"] = None
                st.session_state["analysis_error"] = str(exc)
                st.session_state["workbook_bytes"] = None
                st.session_state["workbook_name"] = ""
                st.session_state["detected_columns"] = []
                st.session_state["missing_required_columns"] = []
            except Exception as exc:
                st.session_state["prepared_df"] = None
                st.session_state["artifacts"] = None
                st.session_state["analysis_error"] = f"Could not analyze the CSV: {exc}"
                st.session_state["workbook_bytes"] = None
                st.session_state["workbook_name"] = ""
                st.session_state["detected_columns"] = []
                st.session_state["missing_required_columns"] = []

    final_title = build_report_title(partner_name, date_range, report_title)
    render_hero(final_title, partner_name, date_range)

    prepared_df = st.session_state.get("prepared_df")
    artifacts = st.session_state.get("artifacts")
    analysis_error = st.session_state.get("analysis_error", "")

    if error_message:
        st.error(error_message)
    elif analysis_error:
        st.error(analysis_error)

    if prepared_df is None and not error_message and not analysis_error:
        if uploaded_csv is None:
            render_empty_workspace()
        else:
            render_pre_analysis_workspace(
                file_name=preflight_file_name or "Uploaded CSV",
                file_size_kb=preflight_file_size_kb,
                inferred_partner_name=inferred_partner_name,
                date_range=date_range,
            )

    if generate and prepared_df is None and not error_message and not analysis_error:
        st.warning("Analyze the workbook first so the dashboard and export are based on the current CSV.")

    if prepared_df is not None and artifacts is not None:
        with st.container(border=True):
            render_section_header("Report Context", "Detected reporting context for the current workbook run.")
            render_context_cards(
                [
                    ("Partner", partner_name or "Pending detection"),
                    ("Date Range", date_range or "Pending detection"),
                    ("Workbook Title", final_title or "Pending detection"),
                    ("Output File", output_filename or "Pending detection"),
                ]
            )

        st.markdown("")
        with st.container(border=True):
            render_section_header("Service Summary", "Factual service review points to validate before export.")
            executive_left, executive_right = st.columns([1.35, 0.85], gap="large")
            with executive_left:
                with st.container(border=True):
                    render_section_header("Executive Brief")
                    render_list(artifacts.executive_brief_points)
            with executive_right:
                with st.container(border=True):
                    render_section_header("Suggested Review Topics")
                    render_list(artifacts.priority_actions[:4])

            st.markdown("")
            with st.container(border=True):
                render_section_header("Service Snapshot")
                metric_columns = st.columns(min(len(artifacts.headline_metrics), 8))
                for index, (label, value) in enumerate(artifacts.headline_metrics[:8]):
                    with metric_columns[index]:
                        render_metric(label, value)

            st.markdown("")
            if artifacts.service_observations:
                render_pulse_band(artifacts.service_observations[0])

            summary_lines = [
                line for line in artifacts.narrative if "sub-issue type" not in str(line).lower()
            ]
            story_tab, patterns_tab, questions_tab = st.tabs(["Summary", "Patterns", "Review Topics"])
            with story_tab:
                render_list(summary_lines or artifacts.narrative)
            with patterns_tab:
                render_list(artifacts.service_observations or ["No additional observations were generated from the file."])
            with questions_tab:
                render_list(artifacts.priority_actions or ["No governance follow-up questions were generated from the file."])

        st.markdown("")
        with st.container(border=True):
            render_section_header("Detailed Review", "Internal QA and raw preview before sharing the workbook.")
            review_tab, queue_tab, escalation_tab, coverage_tab, preview_tab = st.tabs(
                ["Insights", "Queue Distribution", "Escalations", "Coverage", "Raw Preview"]
            )
            with review_tab:
                observations_col, review_items_col = st.columns(2, gap="large")
                with observations_col:
                    st.markdown("#### Observations")
                    render_list(artifacts.service_observations or ["No additional observations were generated from the file."])
                with review_items_col:
                    st.markdown("#### Items To Review")
                    render_list(artifacts.risk_flags or ["No major review items were detected from the current sample."])
            with queue_tab:
                render_table_and_chart("Queue Distribution", artifacts.queue_table, "Queue")
            with escalation_tab:
                reason_tab, category_tab = st.tabs(["Reasons", "Categories"])
                with reason_tab:
                    render_table_and_chart("Escalation Reasons", artifacts.escalation_table, "Escalation Reason")
                with category_tab:
                    if not artifacts.escalation_category_table.empty:
                        import altair as alt

                        st.markdown("#### Escalation Reason Categories")
                        st.dataframe(
                            artifacts.escalation_category_table,
                            width="stretch",
                            hide_index=True,
                            height=_table_height(len(artifacts.escalation_category_table), max_height=360),
                        )
                        category_chart = (
                            artifacts.escalation_category_table.groupby("Category", as_index=False)["Tickets"]
                            .sum()
                            .sort_values("Tickets", ascending=False)
                        )
                        category_chart["Label"] = category_chart["Category"]
                        st.altair_chart(
                            alt.Chart(category_chart)
                            .mark_bar(color="#76B4E6", cornerRadiusEnd=3)
                            .encode(
                                x=alt.X("Tickets:Q", title="Tickets"),
                                y=alt.Y("Label:N", sort="-x", title=None),
                                tooltip=[alt.Tooltip("Category:N", title="Category"), alt.Tooltip("Tickets:Q", title="Tickets")],
                            )
                            .properties(height=max(220, 44 + len(category_chart) * 40)),
                            width="stretch",
                        )
                    else:
                        st.info("No escalated tickets were found, so category reporting is empty.")
            with coverage_tab:
                coverage_left, coverage_right = st.columns(2, gap="large")
                with coverage_left:
                    render_dataframe_block(
                        "Customer Accounts",
                        artifacts.company_table,
                        "No customer account summary is available in this file.",
                        max_height=320,
                    )
                with coverage_right:
                    render_dataframe_block(
                        "Request Types",
                        artifacts.issue_type_table,
                        "No request type summary is available in this file.",
                        max_height=320,
                    )
                sub_issue_left, sub_issue_center, sub_issue_right = st.columns([0.18, 0.64, 0.18], gap="large")
                with sub_issue_center:
                    render_dataframe_block(
                        "Sub-Issue Types",
                        artifacts.sub_issue_type_table,
                        "No sub-issue summary is available in this file.",
                        max_height=320,
                    )
                st.markdown("")
                st.markdown("#### Reporting Notes")
                render_list(artifacts.data_quality_notes or ["No major data quality notes."])
            with preview_tab:
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

        st.markdown("")
        with st.container(border=True):
            render_section_header("Workbook Deliverable", "What will be generated when you export.")
            deliverable_left, deliverable_right = st.columns([1.05, 0.95], gap="large")
            with deliverable_left:
                render_deliverable_card(
                    "Primary Export",
                    "Governance Workbook",
                    "The workbook remains the main deliverable and packages the summary, ticket detail, and escalation review into one partner-ready file.",
                    "Generate and download from Export Options in the sidebar.",
                )
            with deliverable_right:
                render_list(
                    [
                        "Summary sheet for the service review.",
                        "Tickets sheet for completed-ticket review and drill-in.",
                        "Escalation sheet for escalation trends and detail.",
                        "Optional executive PDF snapshot when needed.",
                    ]
                )

        if generate:
            st.session_state["status_log"] = []
            st.session_state["workbook_bytes"] = None
            st.session_state["workbook_name"] = ""
            try:
                if prepared_df is None:
                    raise ValidationError("Analyze the workbook before generating the Excel file.")
                logo_bytes = read_logo_bytes(uploaded_logo)
                final_filename = build_output_path(".", output_filename.strip() or default_filename_from_title(final_title)).name
                push_status("Preparing workbook")
                workbook_bytes = build_workbook_bytes(
                    prepared_df=prepared_df,
                    report_title=final_title,
                    logo_bytes=logo_bytes,
                    output_filename=final_filename,
                    partner_name=partner_name,
                    date_range=date_range,
                )
                st.session_state["workbook_bytes"] = workbook_bytes
                st.session_state["workbook_name"] = final_filename
                push_status("Workbook ready for download")
                render_workbook_download_control(
                    workbook_download_slot,
                    st.session_state.get("workbook_bytes"),
                    st.session_state.get("workbook_name", ""),
                )
                st.success("Workbook generated successfully.")
            except (ValidationError, WorkbookGenerationError) as exc:
                push_status(f"Error: {exc}")
                st.error(str(exc))
            except Exception as exc:
                push_status(f"Unexpected error: {exc}")
                st.error(f"Unexpected error: {exc}")

if __name__ == "__main__":
    main()
