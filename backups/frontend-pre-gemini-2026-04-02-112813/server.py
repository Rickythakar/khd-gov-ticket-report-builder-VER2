from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from comparison import bucket_by_month, compute_comparison, serialize_comparison
from config import APP_NAME, APP_VERSION, DEFAULT_LOGO_PATH, REPORT_MODE_CUSTOMER, REPORT_MODE_INTERNAL
from metrics import format_minutes
from settings import load_settings, save_settings, reset_settings, MODE_CUSTOMER, MODE_INTERNAL
from utils import build_report_artifacts, build_report_title, default_filename_from_title, infer_date_range, infer_partner_name
from validators import ValidationError, validate_and_prepare_dataframe

BASE_DIR = Path(__file__).resolve().parent

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
    "prepared_df": None,
    "artifacts": None,
    "settings": load_settings(),
    "partner_name": "",
    "date_range": "",
    "report_title": "",
    "output_filename": "",
    "error": "",
    "csv_name": "",
    # Multi-month comparison
    "all_dfs": [],           # list of (filename, DataFrame) tuples
    "buckets": [],           # MonthBucket list
    "comparison": None,      # PeriodComparison
    "period": "1M",          # current period selection
    "selected_month": "",    # which month to show in 1M mode (empty = latest)
    "csv_names": [],         # list of uploaded filenames
}


def _rebuild_artifacts_for_period():
    """Rebuild main dashboard artifacts using only the selected period's data."""
    buckets = _state.get("buckets", [])
    if not buckets:
        return

    period = _state.get("period", "1M")
    selected_month = _state.get("selected_month", "")

    # Determine which buckets to use for the dashboard
    if period == "1M":
        if selected_month:
            target = [b for b in buckets if b.label == selected_month]
        else:
            target = buckets[-1:]  # latest month
    elif period == "QTR":
        target = buckets[-3:]
    elif period == "HALF":
        target = buckets[-6:]
    else:  # YR
        target = buckets[-12:]

    if not target:
        target = buckets[-1:]

    # Combine selected buckets' data
    period_df = pd.concat([b.df for b in target], ignore_index=True)

    settings = _state["settings"]
    mode = REPORT_MODE_INTERNAL if settings.get("mode") == MODE_INTERNAL else REPORT_MODE_CUSTOMER
    artifacts = build_report_artifacts(period_df, report_mode=mode, settings=settings)

    partner = infer_partner_name(period_df)
    date_range = infer_date_range(period_df)
    title = build_report_title(partner, date_range)

    _state["prepared_df"] = period_df
    _state["artifacts"] = artifacts
    _state["partner_name"] = partner
    _state["date_range"] = date_range
    _state["report_title"] = title
    _state["output_filename"] = default_filename_from_title(title)
    _state["error"] = ""


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


def _serialize_analytics(analytics) -> dict:
    """Convert AdvancedAnalytics to JSON-safe dict."""
    if analytics is None:
        return {}

    def df_to_records(df):
        if df is None or (hasattr(df, "empty") and df.empty):
            return []
        return json.loads(df.to_json(orient="records", default_handler=str))

    return {
        "complexity_summary": analytics.complexity_summary,
        "complexity_top": df_to_records(analytics.complexity_scores.head(10)),
        "keyword_categories": df_to_records(analytics.keyword_categories),
        "keyword_escalation": df_to_records(analytics.keyword_escalation),
        "workload_balance": df_to_records(analytics.workload_balance),
        "peak_heatmap": analytics.peak_heatmap,
        "kb_coverage": df_to_records(analytics.kb_coverage),
        "company_patterns": df_to_records(analytics.company_patterns.head(12)),
        "escalation_timing": df_to_records(analytics.escalation_timing),
        "description_complexity": df_to_records(analytics.description_complexity),
    }


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


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    settings = _state["settings"]
    artifacts_data = _serialize_artifacts(_state["artifacts"], _state.get("comparison"))
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
        "error": _state["error"],
        "has_data": _state["artifacts"] is not None,
        "a": artifacts_data,
        "MODE_CUSTOMER": MODE_CUSTOMER,
        "MODE_INTERNAL": MODE_INTERNAL,
        "period": _state.get("period", "1M"),
        "selected_month": _state.get("selected_month", ""),
        "available_months": [b.label for b in _state.get("buckets", [])],
        "comp": serialize_comparison(_state["comparison"]) if _state.get("comparison") else {"has_comparison": False},
        "file_count": len(_state.get("all_dfs", [])),
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

        # A fresh picker selection should replace the current working set.
        _state["all_dfs"] = []
        _state["csv_names"] = []

        for upload in uploads:
            contents = await upload.read()
            raw_df = pd.read_csv(io.BytesIO(contents))
            result = validate_and_prepare_dataframe(raw_df)
            prepared_df = result.dataframe

            fname = upload.filename or ""
            print(f"[UPLOAD] {fname}: {len(prepared_df)} rows, {len(raw_df)} raw rows")

            # Replace if same filename already exists, otherwise append
            existing_idx = next((i for i, (n, _) in enumerate(_state["all_dfs"]) if n == fname), None)
            if existing_idx is not None:
                print(f"[UPLOAD] Replacing existing {fname}")
                _state["all_dfs"][existing_idx] = (fname, prepared_df)
            else:
                print(f"[UPLOAD] New file {fname}")
                _state["all_dfs"].append((fname, prepared_df))
                _state["csv_names"].append(fname)

        # Combine all uploaded data
        total_dfs = [(n, len(df)) for n, df in _state["all_dfs"]]
        print(f"[UPLOAD] State has {len(total_dfs)} files: {total_dfs}")
        combined = pd.concat([df for _, df in _state["all_dfs"]], ignore_index=True)
        print(f"[UPLOAD] Combined: {len(combined)} rows")

        _state["csv_name"] = ", ".join(_state["csv_names"][-3:])
        if len(_state["csv_names"]) > 3:
            _state["csv_name"] = f"{len(_state['csv_names'])} files loaded"

        # Build monthly buckets and comparison
        buckets = bucket_by_month(combined)
        _state["buckets"] = buckets

        period = _state.get("period", "1M")
        comparison = compute_comparison(buckets, period=period)
        _state["comparison"] = comparison

        # Use the SELECTED PERIOD's data for the main dashboard (not all combined)
        _rebuild_artifacts_for_period()

        return JSONResponse({"status": "ok", "redirect": "/"})
    except ValidationError as e:
        _state["error"] = str(e)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)
    except Exception as e:
        _state["error"] = f"Could not read CSV: {e}"
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)


@app.post("/period/{period}")
async def set_period(period: str):
    if period not in ("1M", "QTR", "HALF", "YR"):
        return JSONResponse({"error": "Invalid period"}, status_code=400)
    _state["period"] = period
    _state["selected_month"] = ""  # reset month picker
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
    _state["comparison"] = compute_comparison(_state["buckets"], period="1M")
    _rebuild_artifacts_for_period()
    return JSONResponse({"status": "ok"})


@app.post("/clear")
async def clear_data():
    _state["all_dfs"] = []
    _state["csv_names"] = []
    _state["buckets"] = []
    _state["comparison"] = None
    _state["prepared_df"] = None
    _state["artifacts"] = None
    _state["csv_name"] = ""
    _state["partner_name"] = ""
    _state["date_range"] = ""
    _state["error"] = ""
    return JSONResponse({"status": "ok"})


@app.post("/settings")
async def update_settings(request: Request):
    data = await request.json()
    settings = _state["settings"]
    settings.update(data)
    save_settings(settings)
    _state["settings"] = settings

    # Re-analyze if we have data
    if _state["prepared_df"] is not None:
        mode = REPORT_MODE_INTERNAL if settings.get("mode") == MODE_INTERNAL else REPORT_MODE_CUSTOMER
        _state["artifacts"] = build_report_artifacts(_state["prepared_df"], report_mode=mode, settings=settings)

    return JSONResponse({"status": "ok"})


@app.post("/settings/reset")
async def reset_settings_endpoint():
    settings = reset_settings()
    _state["settings"] = settings
    if _state["prepared_df"] is not None:
        mode = REPORT_MODE_INTERNAL if settings.get("mode") == MODE_INTERNAL else REPORT_MODE_CUSTOMER
        _state["artifacts"] = build_report_artifacts(_state["prepared_df"], report_mode=mode, settings=settings)
    return JSONResponse({"status": "ok"})


@app.get("/export/workbook")
async def export_workbook():
    if _state["prepared_df"] is None:
        return JSONResponse({"error": "No data"}, status_code=400)

    from excel_builder import ExcelReportBuilder, ReportRequest
    settings = _state.get("settings") or load_settings()
    report_mode = REPORT_MODE_INTERNAL if settings.get("mode") == MODE_INTERNAL else REPORT_MODE_CUSTOMER

    with tempfile.TemporaryDirectory() as tmp:
        logo_path = DEFAULT_LOGO_PATH
        out_path = Path(tmp) / f"{_state['output_filename']}.xlsx"

        builder = ExcelReportBuilder()
        request = ReportRequest(
            dataframe=_state["prepared_df"],
            report_title=_state["report_title"],
            logo_path=logo_path,
            output_path=out_path,
            partner_name=_state["partner_name"],
            date_range=_state["date_range"],
            report_mode=report_mode,
            settings=settings,
        )
        built = builder.build_report(request)
        data = built.read_bytes()

    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{_state["output_filename"]}.xlsx"'},
    )


@app.get("/export/pdf")
async def export_pdf():
    if _state["artifacts"] is None:
        return JSONResponse({"error": "No data"}, status_code=400)

    from pdf_builder import ExecutivePdfSnapshotBuilder

    logo_bytes = DEFAULT_LOGO_PATH.read_bytes() if DEFAULT_LOGO_PATH.exists() else None
    builder = ExecutivePdfSnapshotBuilder()
    pdf_bytes = builder.build_pdf_bytes(
        report_title=_state["report_title"],
        partner_name=_state["partner_name"],
        date_range=_state["date_range"],
        artifacts=_state["artifacts"],
        logo_bytes=logo_bytes,
    )

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{_state["output_filename"]}_Executive_Snapshot.pdf"'},
    )


@app.post("/mode/{mode}")
async def switch_mode(mode: str):
    if mode not in (MODE_CUSTOMER, MODE_INTERNAL):
        return JSONResponse({"error": "Invalid mode"}, status_code=400)
    _state["settings"]["mode"] = mode
    save_settings(_state["settings"])
    if _state["prepared_df"] is not None:
        report_mode = REPORT_MODE_INTERNAL if mode == MODE_INTERNAL else REPORT_MODE_CUSTOMER
        _state["artifacts"] = build_report_artifacts(_state["prepared_df"], report_mode=report_mode, settings=_state["settings"])
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
