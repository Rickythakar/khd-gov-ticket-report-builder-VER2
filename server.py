from __future__ import annotations

"""Primary product UI entry point.

FastAPI + Jinja is the main dashboard surface for ongoing development.
Keep business logic in shared modules so the legacy Streamlit fallback can
continue to reuse validation, metrics, exports, and settings safely.
"""

import copy
import io
import json
import logging
import os
import uuid
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ai_engine import AIAnalysisResult, AIEngine, serialize_ai_results  # noqa: F401
from comparison import bucket_by_month, compute_comparison, serialize_comparison
from config import APP_NAME, APP_VERSION, DEFAULT_LOGO_PATH, REPORT_MODE_CUSTOMER, REPORT_MODE_INTERNAL
from metrics import format_minutes
from phone_artifacts import build_phone_report_artifacts, infer_phone_date_range, infer_phone_partner_name
from phone_validators import validate_and_prepare_phone_dataframe
from settings import (
    load_settings,
    save_settings,
    reset_settings,
    get_ai_settings,
    is_ai_enabled,
    MODE_CUSTOMER,
    MODE_INTERNAL,
)
from upload_validation import (
    build_unsupported_upload_message,
    validate_supported_upload_schema,
)
from utils import build_report_artifacts, build_report_title, default_filename_from_title, infer_date_range, infer_partner_name
from validators import ValidationError, validate_and_prepare_dataframe

BASE_DIR = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)

app = FastAPI(title=APP_NAME)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/assets", StaticFiles(directory=str(BASE_DIR / "assets")), name="assets")
from jinja2 import Environment, FileSystemLoader

_jinja_env = Environment(loader=FileSystemLoader(str(BASE_DIR / "templates")), auto_reload=True)


def render_template(template_name: str, context: dict) -> str:
    t = _jinja_env.get_template(template_name)
    return t.render(**context)

# In-memory state (single-user local app)
_state: dict = {
    "ticket_df": None,
    "phone_df": None,
    "prepared_df": None,
    "artifacts": None,
    "phone_artifacts": None,
    "settings": load_settings(),
    "partner_name": "",
    "date_range": "",
    "report_title": "",
    "output_filename": "",
    "error": "",
    "csv_name": "",
    "ticket_csv_names": [],
    "phone_csv_names": [],
    "source_label": "",
    "normalization_notes": [],
    "ticket_source_label": "",
    "phone_source_label": "",
    "ticket_normalization_notes": [],
    "phone_normalization_notes": [],
    "phone_partner_name": "",
    "phone_date_range": "",
    "phone_report_title": "",
    "phone_output_filename": "",
    # Multi-month comparison
    "all_dfs": [],           # list of (filename, DataFrame) tuples
    "phone_dfs": [],         # list of (filename, DataFrame) tuples
    "buckets": [],           # MonthBucket list
    "comparison": None,      # PeriodComparison
    "period": "1M",          # current period selection
    "selected_month": "",    # which month to show in 1M mode (empty = latest)
    "csv_names": [],         # list of uploaded filenames
    # AI analysis
    "ai_results": None,      # AIAnalysisResult
}


def _deep_merge(base: dict, updates: dict) -> dict:
    merged = copy.deepcopy(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _clear_ai_cache() -> None:
    _state["ai_results"] = None


def _ai_disabled_response() -> JSONResponse:
    return JSONResponse({"error": "AI features are currently disabled."}, status_code=400)


def _resolve_ai_provider_config(ai_cfg: dict) -> dict[str, str]:
    ai_cfg = get_ai_settings({"ai": ai_cfg})
    provider = ai_cfg.get("provider", "azure_openai")
    if provider == "azure_openai":
        return {
            "endpoint": (ai_cfg.get("endpoint") or os.getenv("AZURE_OPENAI_ENDPOINT", "")).strip(),
            "api_key": (ai_cfg.get("api_key") or os.getenv("AZURE_OPENAI_API_KEY", "")).strip(),
        }

    if provider == "openai":
        return {
            "api_key": (ai_cfg.get("api_key") or os.getenv("OPENAI_API_KEY", "")).strip(),
        }

    return {}


def _ensure_ai_context() -> tuple[dict, JSONResponse | None]:
    if _state["prepared_df"] is None or _state["artifacts"] is None:
        return {}, JSONResponse({"error": "No data loaded"}, status_code=400)

    settings = _state["settings"]
    if settings.get("mode") != MODE_INTERNAL:
        return {}, JSONResponse({"error": "AI analysis is only available in internal mode"}, status_code=400)

    if not is_ai_enabled(settings):
        return {}, _ai_disabled_response()

    ai_cfg = get_ai_settings(settings)
    provider = ai_cfg.get("provider", "azure_openai")
    resolved = _resolve_ai_provider_config(ai_cfg)
    if provider == "azure_openai":
        if not resolved.get("endpoint") or not resolved.get("api_key"):
            return {}, JSONResponse(
                {
                    "error": (
                        "Azure OpenAI requires both an endpoint and API key, "
                        "either in settings or via AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_KEY."
                    )
                },
                status_code=400,
            )
    elif provider == "openai":
        if not resolved.get("api_key"):
            return {}, JSONResponse(
                {"error": "OpenAI API requires an API key, either in settings or via OPENAI_API_KEY."},
                status_code=400,
            )
    elif provider == "chatgpt_oauth":
        pass  # codex_auth handles auth via cached tokens
    else:
        return {}, JSONResponse({"error": f"Unsupported AI provider: {provider}"}, status_code=400)

    return ai_cfg, None


def _rebuild_artifacts_for_period():
    """Rebuild main dashboard artifacts using only the selected period's data."""
    buckets = _state.get("buckets", [])
    if not buckets:
        return

    payload = _build_period_dashboard_payload(
        buckets,
        period=_state.get("period", "1M"),
        selected_month=_state.get("selected_month", ""),
        settings=_state["settings"],
    )
    _state.update(payload)
    _state["error"] = ""


def _select_target_buckets(buckets, *, period: str, selected_month: str):
    if period == "1M":
        if selected_month:
            target = [b for b in buckets if b.label == selected_month]
        else:
            target = buckets[-1:]
    elif period == "QTR":
        target = buckets[-3:]
    elif period == "HALF":
        target = buckets[-6:]
    else:
        target = buckets[-12:]

    if not target:
        target = buckets[-1:]
    return target


def _build_period_dashboard_payload(buckets, *, period: str, selected_month: str, settings: dict) -> dict:
    """Build dashboard state for the selected period without mutating global state."""
    if not buckets:
        raise ValidationError("No valid ticket data was available after upload.")

    target = _select_target_buckets(buckets, period=period, selected_month=selected_month)
    period_df = pd.concat([b.df for b in target], ignore_index=True)
    mode = REPORT_MODE_INTERNAL if settings.get("mode") == MODE_INTERNAL else REPORT_MODE_CUSTOMER
    artifacts = build_report_artifacts(period_df, report_mode=mode, settings=settings)

    partner = infer_partner_name(period_df)
    date_range = infer_date_range(period_df)
    title = build_report_title(partner, date_range)

    return {
        "prepared_df": period_df,
        "artifacts": artifacts,
        "partner_name": partner,
        "date_range": date_range,
        "report_title": title,
        "output_filename": default_filename_from_title(title),
    }


def _serialize_artifacts(artifacts, comparison=None) -> dict:
    """Convert ReportArtifacts to JSON-safe dict for the template."""
    if artifacts is None:
        return {}

    def df_to_records(df):
        if df is None or (hasattr(df, "empty") and df.empty):
            return []
        return json.loads(df.to_json(orient="records", date_format="iso", default_handler=str))

    def df_to_cols(df):
        if df is None or (hasattr(df, "empty") and df.empty):
            return []
        return list(df.columns)

    rm = artifacts.resolution_metrics
    sla = artifacts.sla_metrics
    ah = artifacts.after_hours_metrics
    noise = artifacts.noise_metrics

    return {
        "report_mode": artifacts.report_mode,
        "report_basis": artifacts.report_basis,
        "completion_metrics_available": artifacts.completion_metrics_available,
        "headline_metrics": artifacts.headline_metrics,
        "narrative": artifacts.narrative,
        "executive_brief": artifacts.executive_brief,
        "executive_brief_points": artifacts.executive_brief_points,
        "service_observations": artifacts.service_observations,
        "priority_actions": artifacts.priority_actions,
        "risk_flags": artifacts.risk_flags,
        "data_quality_notes": artifacts.data_quality_notes,
        "fcr_rate": artifacts.fcr_rate,
        # Tables
        "queue_table": df_to_records(artifacts.queue_table),
        "queue_cols": df_to_cols(artifacts.queue_table),
        "escalation_table": df_to_records(artifacts.escalation_table),
        "escalation_cols": df_to_cols(artifacts.escalation_table),
        "escalation_category_table": df_to_records(artifacts.escalation_category_table),
        "source_table": df_to_records(artifacts.source_table),
        "company_table": df_to_records(artifacts.company_table),
        "issue_type_table": df_to_records(artifacts.issue_type_table),
        "sub_issue_type_table": df_to_records(artifacts.sub_issue_type_table),
        "repeat_contacts": df_to_records(artifacts.repeat_contacts),
        "danger_zone_companies": df_to_records(artifacts.danger_zone_companies),
        "technician_scorecards": df_to_records(artifacts.technician_scorecards),
        "kb_gaps": df_to_records(artifacts.kb_gaps),
        "weekly_velocity": df_to_records(artifacts.weekly_velocity),
        "tickets_count": len(artifacts.workbook_df) if artifacts.workbook_df is not None else 0,
        "escalated_count": len(artifacts.escalated_df) if artifacts.escalated_df is not None else 0,
        # Resolution
        "resolution": {
            "mean": rm.mean_minutes if rm else 0,
            "median": rm.median_minutes if rm else 0,
            "p90": rm.p90_minutes if rm else 0,
            "p95": rm.p95_minutes if rm else 0,
            "mean_fmt": format_minutes(rm.mean_minutes) if rm else "—",
            "median_fmt": format_minutes(rm.median_minutes) if rm else "—",
            "p90_fmt": format_minutes(rm.p90_minutes) if rm else "—",
            "p95_fmt": format_minutes(rm.p95_minutes) if rm else "—",
            "by_queue": df_to_records(rm.by_queue) if rm else [],
            "by_priority": df_to_records(rm.by_priority) if rm else [],
            "by_issue_type": df_to_records(rm.by_issue_type) if rm else [],
        },
        # SLA
        "sla": {
            "overall": sla.overall_compliance if sla else 0,
            "by_priority": df_to_records(sla.by_priority) if sla else [],
            "breaching": df_to_records(sla.breaching_tickets) if sla else [],
            "breach_count": len(sla.breaching_tickets) if sla and sla.breaching_tickets is not None else 0,
        },
        # After hours
        "after_hours": {
            "total": ah.total_after_hours if ah else 0,
            "rate": ah.after_hours_rate if ah else 0,
            "weekend": ah.weekend_count if ah else 0,
            "weekday_ah": ah.weekday_after_hours if ah else 0,
            "by_hour": df_to_records(ah.by_hour) if ah else [],
            "by_day": df_to_records(ah.by_day) if ah else [],
        },
        # Noise
        "noise": {
            "spam": noise.spam_count if noise else 0,
            "sync": noise.sync_error_count if noise else 0,
            "total": noise.total_noise if noise else 0,
            "rate": noise.noise_rate if noise else 0,
        },
        # Per-metric sparkline data (list of ints for mini bar charts)
        "sparks": _build_sparklines(artifacts, comparison),
        # P8: Advanced analytics (internal mode only)
        "analytics": _serialize_analytics(artifacts.advanced_analytics),
    }


def _serialize_phone_artifacts(artifacts) -> dict:
    if artifacts is None:
        return {}

    def df_to_records(df):
        if df is None or (hasattr(df, "empty") and df.empty):
            return []
        return json.loads(df.to_json(orient="records", date_format="iso", default_handler=str))

    return {
        "headline_metrics": artifacts.headline_metrics,
        "narrative": artifacts.narrative,
        "data_quality_notes": artifacts.data_quality_notes,
        "queue_table": df_to_records(artifacts.queue_table),
        "disposition_table": df_to_records(artifacts.disposition_table),
        "campaign_table": df_to_records(artifacts.campaign_table),
        "hourly_volume_table": df_to_records(artifacts.hourly_volume_table),
        "daily_volume_table": df_to_records(artifacts.daily_volume_table),
        "service_level_table": df_to_records(artifacts.service_level_table),
    }


def _serialize_analytics(analytics) -> dict:
    """Convert AdvancedAnalytics to JSON-safe dict."""
    def empty_payload() -> dict:
        return {
            "available": False,
            "complexity_summary": {"mean": 0, "median": 0, "high_count": 0, "low_count": 0},
            "complexity_top": [],
            "keyword_categories": [],
            "keyword_escalation": [],
            "workload_balance": [],
            "peak_heatmap": {
                "grid": [[0 for _ in range(24)] for _ in range(7)],
                "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                "hours": list(range(24)),
                "peak_hour": 0,
                "peak_day": "",
                "peak_count": 0,
                "max_val": 0,
            },
            "kb_coverage": [],
            "company_patterns": [],
            "escalation_timing": [],
            "description_complexity": [],
        }

    if analytics is None:
        return empty_payload()

    def df_to_records(df):
        if df is None or (hasattr(df, "empty") and df.empty):
            return []
        return json.loads(df.to_json(orient="records", default_handler=str))

    payload = empty_payload()
    try:
        peak_heatmap = getattr(analytics, "peak_heatmap", {}) or {}
        grid = peak_heatmap.get("grid") if isinstance(peak_heatmap, dict) else []
        normalized_grid = []
        for day_index in range(7):
            source_row = grid[day_index] if isinstance(grid, list) and day_index < len(grid) and isinstance(grid[day_index], list) else []
            normalized_row = []
            for hour_index in range(24):
                value = source_row[hour_index] if hour_index < len(source_row) else 0
                try:
                    normalized_row.append(int(value))
                except (TypeError, ValueError):
                    normalized_row.append(0)
            normalized_grid.append(normalized_row)

        payload.update(
            {
                "available": True,
                "complexity_summary": getattr(analytics, "complexity_summary", payload["complexity_summary"]),
                "complexity_top": df_to_records(getattr(analytics, "complexity_scores", pd.DataFrame()).head(10)),
                "keyword_categories": df_to_records(getattr(analytics, "keyword_categories", pd.DataFrame())),
                "keyword_escalation": df_to_records(getattr(analytics, "keyword_escalation", pd.DataFrame())),
                "workload_balance": df_to_records(getattr(analytics, "workload_balance", pd.DataFrame())),
                "peak_heatmap": {
                    "grid": normalized_grid,
                    "days": peak_heatmap.get("days") if isinstance(peak_heatmap.get("days"), list) and len(peak_heatmap.get("days")) == 7 else payload["peak_heatmap"]["days"],
                    "hours": peak_heatmap.get("hours") if isinstance(peak_heatmap.get("hours"), list) and len(peak_heatmap.get("hours")) == 24 else payload["peak_heatmap"]["hours"],
                    "peak_hour": int(peak_heatmap.get("peak_hour", 0) or 0),
                    "peak_day": str(peak_heatmap.get("peak_day", "") or ""),
                    "peak_count": int(peak_heatmap.get("peak_count", 0) or 0),
                    "max_val": int(peak_heatmap.get("max_val", 0) or 0),
                },
                "kb_coverage": df_to_records(getattr(analytics, "kb_coverage", pd.DataFrame())),
                "company_patterns": df_to_records(getattr(analytics, "company_patterns", pd.DataFrame()).head(12)),
                "escalation_timing": df_to_records(getattr(analytics, "escalation_timing", pd.DataFrame())),
                "description_complexity": df_to_records(getattr(analytics, "description_complexity", pd.DataFrame())),
            }
        )
    except Exception:
        logger.exception("Analytics serialization failed; returning safe defaults to keep the dashboard responsive.")
        return empty_payload()

    return payload


def _build_sparklines(artifacts, comparison=None) -> dict[str, list[int]]:
    """Build per-metric sparkline arrays from actual data."""
    sparks = {}

    if comparison is not None and getattr(comparison, "months", None) and len(comparison.months) > 1:
        trends = getattr(comparison, "trends", {}) or {}
        if trends.get("tickets"):
            sparks["Total Tickets"] = trends["tickets"]
            sparks["Escalated Tickets"] = [
                int(round(ticket_count * escalation_rate / 100.0))
                for ticket_count, escalation_rate in zip(
                    trends.get("tickets", []),
                    trends.get("escalation_rate", []),
                )
            ]
        if trends.get("escalation_rate"):
            sparks["Escalation Rate"] = [round(value, 1) for value in trends["escalation_rate"]]
        if trends.get("median_resolution"):
            sparks["Median Resolution"] = [int(round(value)) for value in trends["median_resolution"]]
        if trends.get("sla_compliance"):
            sparks["SLA Compliance"] = [round(value, 1) for value in trends["sla_compliance"]]
        if trends.get("fcr_rate"):
            sparks["First Contact Resolution"] = [round(value, 1) for value in trends["fcr_rate"]]

    # Weekly velocity for total tickets
    wv = artifacts.weekly_velocity
    if "Total Tickets" not in sparks and wv is not None and not wv.empty:
        sparks["Total Tickets"] = wv["Tickets"].tolist()[-8:]

    # Escalated by week (from escalated_df)
    if "Escalated Tickets" not in sparks and artifacts.escalated_df is not None and not artifacts.escalated_df.empty:
        esc_dates = pd.to_datetime(artifacts.escalated_df.get("Created"), errors="coerce").dropna()
        if not esc_dates.empty:
            sparks["Escalated Tickets"] = esc_dates.dt.isocalendar().week.value_counts().sort_index().tolist()[-8:]

    # Queue distribution as bars
    if "Escalation Rate" not in sparks and artifacts.queue_table is not None and not artifacts.queue_table.empty:
        sparks["Escalation Rate"] = artifacts.queue_table["Tickets"].tolist()[:8]

    # Source distribution
    if artifacts.source_table is not None and not artifacts.source_table.empty:
        sparks["Primary Intake Channel"] = artifacts.source_table["Tickets"].tolist()[:6]

    # Issue type distribution
    if artifacts.issue_type_table is not None and not artifacts.issue_type_table.empty:
        sparks["Leading Request Type"] = artifacts.issue_type_table["Tickets"].tolist()[:6]

    # Company distribution for Customer Accounts
    if artifacts.company_table is not None and not artifacts.company_table.empty:
        sparks["Customer Accounts"] = artifacts.company_table["Tickets"].tolist()[:8]

    # Resolution by hour approximation
    rm = artifacts.resolution_metrics
    if "Median Resolution" not in sparks and rm and rm.by_queue is not None and not rm.by_queue.empty:
        sparks["Median Resolution"] = [int(x) for x in rm.by_queue["Median (min)"].tolist()[:6]]

    # SLA by priority
    sla = artifacts.sla_metrics
    if "SLA Compliance" not in sparks and sla and sla.by_priority is not None and not sla.by_priority.empty:
        sparks["SLA Compliance"] = [int(x) for x in sla.by_priority["Compliance"].tolist()]

    # FCR - no sparkline, use a simple bar
    if "First Contact Resolution" not in sparks:
        sparks["First Contact Resolution"] = [artifacts.fcr_rate, 100 - artifacts.fcr_rate]

    return sparks


def _build_partner_email_message(partner_name: str, date_range: str, report_title: str) -> str:
    period = str(date_range or "").strip()
    if period:
        return (
            f"Attached is your {APP_NAME} report for {period}. Please take a look ahead of our "
            "governance call, and let me know if there is anything specific you would like us to review."
        )

    return (
        f"Attached is your {APP_NAME} report. Please take a look ahead of our governance call, "
        "and let me know if there is anything specific you would like us to review."
    )


def _build_phone_report_title(partner_name: str, date_range: str) -> str:
    partner = str(partner_name or "").strip()
    period = str(date_range or "").strip()
    if partner and period:
        return f"{APP_NAME} Phone Report {period} - {partner}"
    if period:
        return f"{APP_NAME} Phone Report {period}"
    if partner:
        return f"{APP_NAME} Phone Report - {partner}"
    return f"{APP_NAME} Phone Report"


def _resolve_export_overrides(
    *,
    default_title: str,
    default_filename: str,
    requested_title: str = "",
    requested_filename: str = "",
) -> tuple[str, str]:
    export_title = str(requested_title or "").strip() or str(default_title or "").strip()
    requested_name = str(requested_filename or "").strip()
    if requested_name:
        requested_name = Path(requested_name).stem.strip()
    export_filename = default_filename_from_title(requested_name or export_title or default_filename)
    return export_title or default_title, export_filename or default_filename


def _default_include_trends_tab() -> bool:
    return False


def _default_include_heatmap_tab() -> bool:
    return False


def _default_include_daily_volume_tab() -> bool:
    return False


def _default_include_slo_tab() -> bool:
    return False


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    settings = _state["settings"]
    ai_enabled = is_ai_enabled(settings)
    artifacts_data = _serialize_artifacts(_state["artifacts"], _state.get("comparison"))
    phone_data = _serialize_phone_artifacts(_state.get("phone_artifacts"))
    has_ticket_data = _state.get("prepared_df") is not None and _state.get("artifacts") is not None
    has_phone_data = _state.get("phone_df") is not None and _state.get("phone_artifacts") is not None
    html_content = render_template("dashboard.html", {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "settings": settings,
        "mode": settings.get("mode", MODE_CUSTOMER),
        "partner_name": _state["partner_name"],
        "date_range": _state["date_range"],
        "report_title": _state["report_title"],
        "output_filename": _state["output_filename"],
        "csv_name": _state["csv_name"],
        "source_label": _state.get("source_label", ""),
        "normalization_notes": _state.get("normalization_notes", []),
        "ticket_source_label": _state.get("ticket_source_label", ""),
        "phone_source_label": _state.get("phone_source_label", ""),
        "ticket_normalization_notes": _state.get("ticket_normalization_notes", []),
        "phone_normalization_notes": _state.get("phone_normalization_notes", []),
        "partner_email_message": _build_partner_email_message(
            _state["partner_name"],
            _state["date_range"],
            _state["report_title"],
        ),
        "include_trends_default": _default_include_trends_tab(),
        "include_heatmap_default": _default_include_heatmap_tab(),
        "include_daily_volume_default": _default_include_daily_volume_tab(),
        "include_slo_default": _default_include_slo_tab(),
        "error": _state["error"],
        "has_data": has_ticket_data,
        "has_ticket_data": has_ticket_data,
        "has_phone_data": has_phone_data,
        "has_any_data": has_ticket_data or has_phone_data,
        "ticket_completion_metrics_available": bool(getattr(_state.get("artifacts"), "completion_metrics_available", False)),
        "combined_export_available": False,
        "a": artifacts_data,
        "phone": phone_data,
        "MODE_CUSTOMER": MODE_CUSTOMER,
        "MODE_INTERNAL": MODE_INTERNAL,
        "period": _state.get("period", "1M"),
        "selected_month": _state.get("selected_month", ""),
        "available_months": [b.label for b in _state.get("buckets", [])],
        "comp": serialize_comparison(_state["comparison"]) if _state.get("comparison") else {"has_comparison": False},
        "file_count": len(_state.get("all_dfs", [])),
        "phone_file_count": len(_state.get("phone_dfs", [])),
        "ai": serialize_ai_results(_state.get("ai_results") if ai_enabled else None),
        "ai_enabled": ai_enabled,
    })
    return HTMLResponse(content=html_content)


@app.post("/upload")
async def upload_csv(file: list[UploadFile] = File(...)):
    try:
        uploads = list(file or [])
        if not uploads:
            return JSONResponse({"status": "error", "message": "No CSV files uploaded."}, status_code=400)
        if len(uploads) > 12:
            return JSONResponse(
                {"status": "error", "message": "Phase 7 upload is limited to 12 CSV files."},
                status_code=400,
            )

        staged_ticket_dfs: list[tuple[str, pd.DataFrame]] = []
        staged_ticket_csv_names: list[str] = []
        staged_phone_dfs: list[tuple[str, pd.DataFrame]] = []
        staged_phone_csv_names: list[str] = []
        ticket_labels: set[str] = set()
        phone_labels: set[str] = set()
        ticket_notes: list[str] = []
        phone_notes: list[str] = []
        last_ticket_result = None
        last_phone_result = None

        for upload in uploads:
            contents = await upload.read()
            fname = upload.filename or ""
            raw_df = pd.read_csv(io.BytesIO(contents))
            schema_result = validate_supported_upload_schema(raw_df)
            if not schema_result.is_supported:
                logger.warning(
                    "Upload rejected for %s because it does not match a supported reporting export format. Canonical missing: %s. Power BI ticket missing: %s. Power BI phone missing: %s. Source hint: %s",
                    fname or "<unknown>",
                    schema_result.schema_candidates.get("canonical_created_ticket", []),
                    schema_result.schema_candidates.get("power_bi_ticket_export", []),
                    schema_result.schema_candidates.get("powerbi_phone_export", []),
                    schema_result.source_hint,
                )
                raise ValidationError(build_unsupported_upload_message(schema_result))

            if schema_result.accepted_schema == "powerbi_phone_export":
                result = validate_and_prepare_phone_dataframe(raw_df)
                prepared_df = result.dataframe
                staged_phone_dfs.append((fname, prepared_df))
                staged_phone_csv_names.append(fname)
                phone_labels.add(result.source_label)
                for note in result.normalization_notes:
                    if note not in phone_notes:
                        phone_notes.append(note)
                last_phone_result = result
            else:
                result = validate_and_prepare_dataframe(raw_df)
                prepared_df = result.dataframe
                staged_ticket_dfs.append((fname, prepared_df))
                staged_ticket_csv_names.append(fname)
                ticket_labels.add(result.source_label)
                for note in result.normalization_notes:
                    if note not in ticket_notes:
                        ticket_notes.append(note)
                last_ticket_result = result

            logger.info(
                "Accepted upload %s using %s normalization path (%s).",
                fname or "<unknown>",
                result.source_schema,
                result.source_label,
            )

            print(f"[UPLOAD] {fname}: {len(prepared_df)} rows, {len(raw_df)} raw rows")

        if staged_ticket_dfs:
            total_ticket_dfs = [(n, len(df)) for n, df in staged_ticket_dfs]
            print(f"[UPLOAD] Ticket lane has {len(total_ticket_dfs)} files: {total_ticket_dfs}")
            combined_ticket = pd.concat([df for _, df in staged_ticket_dfs], ignore_index=True)
            print(f"[UPLOAD] Ticket lane combined: {len(combined_ticket)} rows")

            ticket_csv_name = ", ".join(staged_ticket_csv_names[-3:])
            if len(staged_ticket_csv_names) > 3:
                ticket_csv_name = f"{len(staged_ticket_csv_names)} ticket files loaded"

            buckets = bucket_by_month(combined_ticket)
            period = _state.get("period", "1M")
            comparison = compute_comparison(buckets, period=period)
            period_payload = _build_period_dashboard_payload(
                buckets,
                period=period,
                selected_month=_state.get("selected_month", ""),
                settings=_state["settings"],
            )

            _state["ticket_df"] = combined_ticket
            _state["all_dfs"] = staged_ticket_dfs
            _state["csv_names"] = staged_ticket_csv_names
            _state["ticket_csv_names"] = staged_ticket_csv_names
            _state["csv_name"] = ticket_csv_name
            _state["buckets"] = buckets
            _state["comparison"] = comparison
            _state.update(period_payload)
            _state["ticket_source_label"] = list(ticket_labels)[0] if len(ticket_labels) == 1 else "Multiple ticket sources"
            _state["ticket_normalization_notes"] = ticket_notes
            _state["source_label"] = _state["ticket_source_label"]
            _state["normalization_notes"] = ticket_notes

        if staged_phone_dfs:
            total_phone_dfs = [(n, len(df)) for n, df in staged_phone_dfs]
            print(f"[UPLOAD] Phone lane has {len(total_phone_dfs)} files: {total_phone_dfs}")
            combined_phone = pd.concat([df for _, df in staged_phone_dfs], ignore_index=True)
            print(f"[UPLOAD] Phone lane combined: {len(combined_phone)} rows")

            _state["phone_df"] = combined_phone
            _state["phone_dfs"] = staged_phone_dfs
            _state["phone_csv_names"] = staged_phone_csv_names
            _state["phone_artifacts"] = build_phone_report_artifacts(combined_phone)
            _state["phone_source_label"] = list(phone_labels)[0] if len(phone_labels) == 1 else "Multiple phone sources"
            _state["phone_normalization_notes"] = phone_notes
            _state["phone_partner_name"] = infer_phone_partner_name(combined_phone)
            _state["phone_date_range"] = infer_phone_date_range(combined_phone)
            _state["phone_report_title"] = _build_phone_report_title(_state["phone_partner_name"], _state["phone_date_range"])
            _state["phone_output_filename"] = default_filename_from_title(_state["phone_report_title"])
            if not staged_ticket_dfs and _state.get("prepared_df") is None:
                _state["partner_name"] = _state["phone_partner_name"]
                _state["date_range"] = _state["phone_date_range"]
                _state["report_title"] = _state["phone_report_title"]
                _state["output_filename"] = _state["phone_output_filename"]
                _state["csv_name"] = ", ".join(staged_phone_csv_names[-3:]) if staged_phone_csv_names else ""
                _state["source_label"] = _state["phone_source_label"]
                _state["normalization_notes"] = phone_notes

        _state["error"] = ""
        _clear_ai_cache()

        return JSONResponse({"status": "ok", "redirect": "/"})
    except ValidationError as e:
        logger.warning("Upload validation failed: %s", e)
        _state["error"] = str(e)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)
    except Exception as e:
        logger.exception("Unexpected upload failure while reading CSV.")
        _state["error"] = (
            "The uploaded CSV does not match a supported reporting export format. "
            "Supported uploads are canonical ticket exports, mapped Power BI ticket exports, or Power BI phone exports."
        )
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)


@app.post("/period/{period}")
async def set_period(period: str):
    if period not in ("1M", "QTR", "HALF", "YR"):
        return JSONResponse({"error": "Invalid period"}, status_code=400)
    _state["period"] = period
    _state["selected_month"] = ""  # reset month picker
    _clear_ai_cache()
    if _state["buckets"]:
        _state["comparison"] = compute_comparison(_state["buckets"], period=period)
        _rebuild_artifacts_for_period()
    return JSONResponse({"status": "ok"})


@app.post("/month/{month}")
async def set_month(month: str):
    valid = [b.label for b in _state.get("buckets", [])]
    if month not in valid:
        return JSONResponse({"error": f"Invalid month. Available: {valid}"}, status_code=400)
    _state["period"] = "1M"
    _state["selected_month"] = month
    _clear_ai_cache()
    _state["comparison"] = compute_comparison(_state["buckets"], period="1M")
    _rebuild_artifacts_for_period()
    return JSONResponse({"status": "ok"})


@app.post("/clear")
async def clear_data():
    _state["ticket_df"] = None
    _state["phone_df"] = None
    _state["all_dfs"] = []
    _state["phone_dfs"] = []
    _state["csv_names"] = []
    _state["ticket_csv_names"] = []
    _state["phone_csv_names"] = []
    _state["buckets"] = []
    _state["comparison"] = None
    _state["prepared_df"] = None
    _state["artifacts"] = None
    _state["phone_artifacts"] = None
    _state["csv_name"] = ""
    _state["partner_name"] = ""
    _state["date_range"] = ""
    _state["error"] = ""
    _state["source_label"] = ""
    _state["normalization_notes"] = []
    _state["ticket_source_label"] = ""
    _state["phone_source_label"] = ""
    _state["ticket_normalization_notes"] = []
    _state["phone_normalization_notes"] = []
    _state["phone_partner_name"] = ""
    _state["phone_date_range"] = ""
    _state["phone_report_title"] = ""
    _state["phone_output_filename"] = ""
    _clear_ai_cache()
    return JSONResponse({"status": "ok"})


@app.post("/settings")
async def update_settings(request: Request):
    data = await request.json()
    settings = _deep_merge(_state["settings"], data)
    save_settings(settings)
    _state["settings"] = settings
    _clear_ai_cache()

    # Re-analyze if we have data
    if _state["prepared_df"] is not None:
        mode = REPORT_MODE_INTERNAL if settings.get("mode") == MODE_INTERNAL else REPORT_MODE_CUSTOMER
        _state["artifacts"] = build_report_artifacts(_state["prepared_df"], report_mode=mode, settings=settings)

    return JSONResponse({"status": "ok"})


@app.post("/settings/reset")
async def reset_settings_endpoint():
    settings = reset_settings()
    _state["settings"] = settings
    _clear_ai_cache()
    if _state["prepared_df"] is not None:
        mode = REPORT_MODE_INTERNAL if settings.get("mode") == MODE_INTERNAL else REPORT_MODE_CUSTOMER
        _state["artifacts"] = build_report_artifacts(_state["prepared_df"], report_mode=mode, settings=settings)
    return JSONResponse({"status": "ok"})


@app.get("/ai/run-stream")
async def run_ai_stream():
    """SSE endpoint that streams AI analysis progress in real-time."""
    import asyncio
    import queue

    _, error = _ensure_ai_context()
    if error is not None:
        return error

    settings = _state["settings"]
    engine = AIEngine(settings)
    comp = _state.get("comparison")
    deltas = comp.deltas if comp else {}

    progress_queue: queue.Queue = queue.Queue()

    def on_progress(event):
        progress_queue.put(event)

    engine.set_progress_callback(on_progress)

    def _run():
        return engine.run_full_analysis(
            df=_state["prepared_df"],
            artifacts=_state["artifacts"],
            comparison_deltas=deltas,
        )

    # Start in thread
    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(None, _run)

    async def generate():
        while not future.done():
            try:
                event = progress_queue.get_nowait()
                yield f"data: {json.dumps(event)}\n\n"
            except queue.Empty:
                await asyncio.sleep(0.3)
        # Drain remaining events
        while not progress_queue.empty():
            event = progress_queue.get_nowait()
            yield f"data: {json.dumps(event)}\n\n"
        # Get result and store
        try:
            result = future.result()
            _state["ai_results"] = result
            yield f"data: {json.dumps({'type': 'done', 'message': 'Analysis complete', 'calls': result.calls_made, 'tokens': result.tokens_used})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)[:200]})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/ai/run")
async def run_ai_analysis():
    import asyncio

    _, error = _ensure_ai_context()
    if error is not None:
        return error

    settings = _state["settings"]
    engine = AIEngine(settings)
    comp = _state.get("comparison")
    deltas = comp.deltas if comp else {}

    def _run():
        return engine.run_full_analysis(
            df=_state["prepared_df"],
            artifacts=_state["artifacts"],
            comparison_deltas=deltas,
        )

    try:
        result = await asyncio.get_event_loop().run_in_executor(None, _run)
        _state["ai_results"] = result
        return JSONResponse({
            "status": "ok",
            "calls_made": result.calls_made,
            "tokens_used": result.tokens_used,
            "errors": result.errors,
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/ai/status")
async def ai_status():
    settings = _state["settings"]
    enabled = is_ai_enabled(settings)
    result = _state.get("ai_results") if enabled else None
    return JSONResponse(
        {
            "enabled": enabled,
            "mode": settings.get("mode", MODE_CUSTOMER),
            "running": False,
            "has_results": result is not None,
            "calls_made": getattr(result, "calls_made", 0),
            "tokens_used": getattr(result, "tokens_used", 0),
            "errors": getattr(result, "errors", []),
        }
    )


@app.get("/ai/results")
async def ai_results():
    result = _state.get("ai_results") if is_ai_enabled(_state["settings"]) else None
    return JSONResponse(serialize_ai_results(result))


@app.post("/ai/summary")
async def ai_summary():
    _, error = _ensure_ai_context()
    if error is not None:
        return error

    settings = _state["settings"]
    engine = AIEngine(settings)

    try:
        custom_instructions = settings.get("ai", {}).get("custom_instructions", "")
        summary = engine.generate_executive_summary(
            dict(_state["artifacts"].headline_metrics),
            _state["artifacts"].service_observations,
            _state["artifacts"].priority_actions,
            custom_instructions=custom_instructions,
        )
        existing = _state.get("ai_results") or AIAnalysisResult()
        existing.executive_summary = summary
        existing.calls_made = engine._calls_made
        existing.tokens_used = engine._tokens_used
        existing.errors = list(engine._errors)
        _state["ai_results"] = existing
        return JSONResponse({"status": "ok", "summary": summary})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/ai/connect-chatgpt")
async def connect_chatgpt():
    if not is_ai_enabled(_state["settings"]):
        return _ai_disabled_response()
    try:
        from codex_auth import authenticate
        authenticate()
        settings = _state["settings"]
        ai_cfg = get_ai_settings(settings)
        ai_cfg["provider"] = "chatgpt_oauth"
        ai_cfg["chatgpt_connected"] = True
        settings["ai"] = ai_cfg
        save_settings(settings)
        _state["settings"] = settings
        return JSONResponse({"status": "ok", "message": "ChatGPT connected via OAuth"})
    except ImportError:
        return JSONResponse({"error": "codex-auth not installed. Run: pip install codex-auth"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": f"OAuth login failed: {e}"}, status_code=500)


@app.post("/ai/ask")
async def ask_ai(request: Request):
    """Ask AI a question with optional widget context."""
    import asyncio

    _, error = _ensure_ai_context()
    if error is not None:
        return error

    data = await request.json()
    question = data.get("question", "").strip()
    context_type = data.get("context", "")  # e.g., "sentiment", "escalation", "coverage"
    if not question:
        return JSONResponse({"error": "Question required"}, status_code=400)

    fast_mode = data.get("fast_mode", False)
    settings = _state["settings"]

    # For fast mode (explain), use lighter model with no reasoning
    if fast_mode:
        fast_settings = copy.deepcopy(settings)
        fast_settings["ai"]["deployment"] = "gpt-4o-mini"
        fast_settings["ai"]["reasoning_effort"] = "none"
        engine = AIEngine(fast_settings)
    else:
        engine = AIEngine(settings)

    # Build context from artifacts
    artifacts = _state["artifacts"]
    context_parts = [f"Metrics: {dict(artifacts.headline_metrics)}"]
    if context_type == "sentiment" and _state.get("ai_results"):
        context_parts.append(f"Sentiment data: {_state['ai_results'].sentiment_summary}")
    elif context_type == "escalation":
        context_parts.append(f"Escalation data: {artifacts.escalation_table.head(10).to_dict('records') if artifacts.escalation_table is not None else []}")
    elif context_type == "coverage":
        context_parts.append(f"Company data: {artifacts.company_table.head(10).to_dict('records') if artifacts.company_table is not None else []}")
    elif context_type == "sla":
        sla = artifacts.sla_metrics
        context_parts.append(f"SLA: overall={sla.overall_compliance}%" if sla else "No SLA data")
    context_parts.append(f"Observations: {artifacts.service_observations[:5]}")

    system = (
        "You are an MSP governance analyst assistant. Answer questions about the ticket data concisely. "
        "Use specific numbers and ticket references when possible.\n\n"
        f"Context:\n{chr(10).join(context_parts)}"
    )

    def _ask():
        return engine._call(system, question)

    try:
        result = await asyncio.get_event_loop().run_in_executor(None, _ask)
        answer = result.get("answer", result.get("response", json.dumps(result)))
        return JSONResponse({"answer": answer})
    except Exception as e:
        return JSONResponse({"error": str(e)[:200]}, status_code=500)


@app.post("/ai/clear")
async def clear_ai():
    _clear_ai_cache()
    return JSONResponse({"status": "ok"})


@app.get("/export/workbook")
async def export_workbook(
    include_trends: str = "0",
    include_heatmap: str = "0",
    include_daily_volume: str = "0",
    include_slo: str = "0",
    include_phone_metrics: str = "0",
    monthly_ticket_report_mode: str = "0",
    report_title: str = "",
    filename: str = "",
):
    if _state["prepared_df"] is None:
        return JSONResponse({"error": "No data"}, status_code=400)

    from excel_builder import ExcelReportBuilder, ReportRequest
    settings = _state.get("settings") or load_settings()
    report_mode = REPORT_MODE_INTERNAL if settings.get("mode") == MODE_INTERNAL else REPORT_MODE_CUSTOMER
    ai_results = _state.get("ai_results") if is_ai_enabled(settings) else None
    include_trends_tab = include_trends == "1"
    include_heatmap_tab = include_heatmap == "1"
    include_daily_volume_tab = include_daily_volume == "1"
    include_slo_tab = include_slo == "1" and bool(getattr(_state.get("artifacts"), "completion_metrics_available", False))
    include_phone_metrics_tab = include_phone_metrics == "1" and _state.get("phone_df") is not None
    monthly_mode_enabled = monthly_ticket_report_mode == "1"

    export_df = _state["prepared_df"]
    export_partner = _state["partner_name"]
    export_date_range = _state["date_range"]
    export_report_title = _state["report_title"]
    export_filename = _state["output_filename"]

    if monthly_mode_enabled:
        if _state.get("all_dfs"):
            export_df = pd.concat([df for _, df in _state["all_dfs"]], ignore_index=True)
        elif _state.get("buckets"):
            export_df = pd.concat([bucket.df for bucket in _state["buckets"]], ignore_index=True)

        inferred_partner = infer_partner_name(export_df)
        inferred_date_range = infer_date_range(export_df)
        export_partner = inferred_partner or export_partner
        export_date_range = inferred_date_range or export_date_range
        export_report_title = build_report_title(export_partner, export_date_range)
        base_filename = default_filename_from_title(export_report_title)[:72].rstrip("_") or "khd_ticket_report"
        export_filename = f"{base_filename}_Monthly_Ticket_Report"

    export_report_title, export_filename = _resolve_export_overrides(
        default_title=export_report_title,
        default_filename=export_filename,
        requested_title=report_title,
        requested_filename=filename,
    )
    if monthly_mode_enabled:
        export_filename = f"{export_filename}_Monthly_Ticket_Report" if not export_filename.endswith("_Monthly_Ticket_Report") else export_filename

    export_dir = BASE_DIR / ".tmp_exports"
    export_dir.mkdir(exist_ok=True)
    logo_path = DEFAULT_LOGO_PATH
    out_path = export_dir / f"{export_filename}_{uuid.uuid4().hex}.xlsx"

    builder = ExcelReportBuilder()
    request = ReportRequest(
        dataframe=export_df,
        report_title=export_report_title,
        logo_path=logo_path,
        output_path=out_path,
        partner_name=export_partner,
        date_range=export_date_range,
        report_mode=report_mode,
        settings=settings,
        ai_results=ai_results,
        include_trends=include_trends_tab,
        include_heatmap=include_heatmap_tab,
        include_daily_volume=include_daily_volume_tab,
        include_slo=include_slo_tab,
        monthly_ticket_report_mode=monthly_mode_enabled,
        phone_dataframe=_state.get("phone_df") if include_phone_metrics_tab else None,
        include_phone_metrics=include_phone_metrics_tab,
    )
    built = builder.build_report(request)
    try:
        data = built.read_bytes()
    finally:
        built.unlink(missing_ok=True)

    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{export_filename}.xlsx"'},
    )


@app.get("/export/pdf")
async def export_pdf(include_ai: str = "1", report_title: str = "", filename: str = ""):
    if _state["artifacts"] is None:
        return JSONResponse({"error": "No data"}, status_code=400)

    from pdf_builder import ExecutivePdfSnapshotBuilder

    logo_bytes = DEFAULT_LOGO_PATH.read_bytes() if DEFAULT_LOGO_PATH.exists() else None
    ai_results = _state.get("ai_results") if include_ai == "1" and is_ai_enabled(_state.get("settings")) else None
    export_report_title, export_filename = _resolve_export_overrides(
        default_title=_state["report_title"],
        default_filename=_state["output_filename"],
        requested_title=report_title,
        requested_filename=filename,
    )
    builder = ExecutivePdfSnapshotBuilder()
    pdf_bytes = builder.build_pdf_bytes(
        report_title=export_report_title,
        partner_name=_state["partner_name"],
        date_range=_state["date_range"],
        artifacts=_state["artifacts"],
        logo_bytes=logo_bytes,
        ai_results=ai_results,
    )

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{export_filename}_Executive_Snapshot.pdf"'},
    )


@app.post("/mode/{mode}")
async def switch_mode(mode: str):
    if mode not in (MODE_CUSTOMER, MODE_INTERNAL):
        return JSONResponse({"error": "Invalid mode"}, status_code=400)
    _state["settings"]["mode"] = mode
    save_settings(_state["settings"])
    _clear_ai_cache()
    if _state["prepared_df"] is not None:
        report_mode = REPORT_MODE_INTERNAL if mode == MODE_INTERNAL else REPORT_MODE_CUSTOMER
        _state["artifacts"] = build_report_artifacts(_state["prepared_df"], report_mode=report_mode, settings=_state["settings"])
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
