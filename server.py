from __future__ import annotations

import copy
import io
import json
import os
import tempfile
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


def _resolve_ai_provider_config(ai_cfg: dict) -> dict[str, str]:
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

    ai_cfg = settings.get("ai", {})
    if not ai_cfg.get("enabled"):
        return {}, JSONResponse({"error": "AI is not enabled in settings"}, status_code=400)

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
        "ai": serialize_ai_results(_state.get("ai_results")),
        "ai_enabled": _state["settings"].get("ai", {}).get("enabled", False),
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
        _clear_ai_cache()

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
    result = _state.get("ai_results")
    settings = _state["settings"]
    return JSONResponse(
        {
            "enabled": settings.get("ai", {}).get("enabled", False),
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
    return JSONResponse(serialize_ai_results(_state.get("ai_results")))


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
    try:
        from codex_auth import authenticate
        authenticate()
        settings = _state["settings"]
        ai_cfg = settings.setdefault("ai", {})
        ai_cfg["provider"] = "chatgpt_oauth"
        ai_cfg["enabled"] = True
        ai_cfg["chatgpt_connected"] = True
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
            ai_results=_state.get("ai_results"),
        )
        built = builder.build_report(request)
        data = built.read_bytes()

    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{_state["output_filename"]}.xlsx"'},
    )


@app.get("/export/pdf")
async def export_pdf(include_ai: str = "1"):
    if _state["artifacts"] is None:
        return JSONResponse({"error": "No data"}, status_code=400)

    from pdf_builder import ExecutivePdfSnapshotBuilder

    logo_bytes = DEFAULT_LOGO_PATH.read_bytes() if DEFAULT_LOGO_PATH.exists() else None
    ai_results = _state.get("ai_results") if include_ai == "1" else None
    builder = ExecutivePdfSnapshotBuilder()
    pdf_bytes = builder.build_pdf_bytes(
        report_title=_state["report_title"],
        partner_name=_state["partner_name"],
        date_range=_state["date_range"],
        artifacts=_state["artifacts"],
        logo_bytes=logo_bytes,
        ai_results=ai_results,
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
    _clear_ai_cache()
    if _state["prepared_df"] is not None:
        report_mode = REPORT_MODE_INTERNAL if mode == MODE_INTERNAL else REPORT_MODE_CUSTOMER
        _state["artifacts"] = build_report_artifacts(_state["prepared_df"], report_mode=report_mode, settings=_state["settings"])
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
