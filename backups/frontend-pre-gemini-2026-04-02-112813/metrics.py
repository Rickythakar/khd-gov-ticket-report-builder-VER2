from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from config import NOISE_QUEUE_PATTERNS, NOISE_TITLE_PATTERNS


@dataclass
class ResolutionMetrics:
    mean_minutes: float = 0.0
    median_minutes: float = 0.0
    p25_minutes: float = 0.0
    p75_minutes: float = 0.0
    p90_minutes: float = 0.0
    p95_minutes: float = 0.0
    by_queue: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    by_priority: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    by_issue_type: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())


@dataclass
class SLAMetrics:
    overall_compliance: float = 0.0
    by_priority: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    breaching_tickets: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())


@dataclass
class AfterHoursMetrics:
    total_after_hours: int = 0
    after_hours_rate: float = 0.0
    weekday_after_hours: int = 0
    weekend_count: int = 0
    by_hour: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    by_day: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())


@dataclass
class NoiseMetrics:
    spam_count: int = 0
    sync_error_count: int = 0
    total_noise: int = 0
    noise_rate: float = 0.0
    noise_df: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())


def _clean_series(df: pd.DataFrame, col: str) -> pd.Series:
    return df.get(col, pd.Series(dtype=str)).fillna("").astype(str).str.strip()


def _safe_pct(num: float, denom: float) -> float:
    return round(num / max(denom, 1.0) * 100, 1)


# ---------------------------------------------------------------------------
# Resolution Time
# ---------------------------------------------------------------------------

def add_resolution_minutes(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    created = pd.to_datetime(out.get("Created"), errors="coerce")
    completed = pd.to_datetime(out.get("Complete Date"), errors="coerce")
    delta = (completed - created).dt.total_seconds() / 60.0
    out["Resolution Minutes"] = delta.where(delta > 0)
    return out


def compute_resolution_metrics(df: pd.DataFrame) -> ResolutionMetrics:
    if "Resolution Minutes" not in df.columns:
        df = add_resolution_minutes(df)
    series = df["Resolution Minutes"].dropna()
    if series.empty:
        return ResolutionMetrics()
    return ResolutionMetrics(
        mean_minutes=round(float(series.mean()), 1),
        median_minutes=round(float(series.median()), 1),
        p25_minutes=round(float(series.quantile(0.25)), 1),
        p75_minutes=round(float(series.quantile(0.75)), 1),
        p90_minutes=round(float(series.quantile(0.90)), 1),
        p95_minutes=round(float(series.quantile(0.95)), 1),
        by_queue=_resolution_breakdown(df, "Queue"),
        by_priority=_resolution_breakdown(df, "Priority"),
        by_issue_type=_resolution_breakdown(df, "Issue Type"),
    )


def compute_resolution_times(df: pd.DataFrame) -> ResolutionMetrics:
    return compute_resolution_metrics(df)


def _resolution_breakdown(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    if group_col not in df.columns or "Resolution Minutes" not in df.columns:
        return pd.DataFrame()
    series = df[[group_col, "Resolution Minutes"]].dropna(subset=["Resolution Minutes"])
    if series.empty:
        return pd.DataFrame()
    grouped = series.groupby(group_col)["Resolution Minutes"].agg(
        Tickets="count",
        Mean="mean",
        Median="median",
        P90=lambda x: x.quantile(0.90),
    ).reset_index()
    grouped.columns = [group_col, "Tickets", "Mean (min)", "Median (min)", "P90 (min)"]
    for col in ["Mean (min)", "Median (min)", "P90 (min)"]:
        grouped[col] = grouped[col].round(1)
    return grouped.sort_values("Tickets", ascending=False).reset_index(drop=True)


def format_minutes(minutes: float) -> str:
    if minutes < 60:
        return f"{minutes:.0f}m"
    hours = minutes / 60
    if hours < 24:
        return f"{hours:.1f}h"
    days = hours / 24
    return f"{days:.1f}d"


def compute_monthly_breakdown(
    df: pd.DataFrame,
    sla_targets: dict[str, int] | None = None,
    queue_overrides: dict[str, int] | None = None,
) -> pd.DataFrame:
    """Build month-level comparison metrics for workbook exports and dashboard trends."""
    if df.empty:
        return pd.DataFrame(
            columns=[
                "Month",
                "Tickets",
                "Escalation Rate",
                "SLA Compliance",
                "Median Resolution",
                "FCR Rate",
                "Noise Count",
            ]
        )

    date_source = pd.to_datetime(df.get("Created"), errors="coerce")
    if not date_source.notna().any():
        date_source = pd.to_datetime(df.get("Complete Date"), errors="coerce")

    work = df.copy()
    work["_month"] = date_source.dt.to_period("M")
    work = work.dropna(subset=["_month"])
    if work.empty:
        return pd.DataFrame(
            columns=[
                "Month",
                "Tickets",
                "Escalation Rate",
                "SLA Compliance",
                "Median Resolution",
                "FCR Rate",
                "Noise Count",
            ]
        )

    targets = sla_targets or {"Critical": 60, "High": 240, "Medium": 480, "Low": 1440, "None": 1440}
    rows: list[dict[str, float | int | str]] = []

    for month_period in sorted(work["_month"].unique()):
        month_df = work.loc[work["_month"] == month_period].drop(columns=["_month"]).copy()
        month_df = add_resolution_minutes(month_df)
        escalation = _clean_series(month_df, "Escalation Reason")
        ticket_count = len(month_df)
        sla_metrics = compute_sla_compliance(month_df, targets, queue_overrides)
        resolution_metrics = compute_resolution_metrics(month_df)
        noise_metrics = classify_noise(month_df)

        rows.append(
            {
                "Month": str(month_period),
                "Tickets": ticket_count,
                "Escalation Rate": _safe_pct(float((escalation != "").sum()), float(ticket_count)),
                "SLA Compliance": sla_metrics.overall_compliance,
                "Median Resolution": resolution_metrics.median_minutes,
                "FCR Rate": compute_fcr_rate(month_df),
                "Noise Count": noise_metrics.total_noise,
            }
        )

    return pd.DataFrame(rows)


def compute_period_deltas(monthly_breakdown: pd.DataFrame, period: str = "1M") -> dict[str, dict[str, float | str]]:
    """Compute dashboard delta indicators from month-level comparison data."""
    if monthly_breakdown.empty:
        return {}

    period_map = {"1M": 1, "QTR": 3, "HALF": 6, "YR": 12}
    window = period_map.get(period, 1)
    ordered = monthly_breakdown.sort_values("Month").reset_index(drop=True)
    current_slice = ordered.tail(window)
    prior_slice = ordered.iloc[max(len(ordered) - (window * 2), 0): max(len(ordered) - window, 0)]
    if current_slice.empty or prior_slice.empty:
        return {}

    current = _aggregate_comparison_window(current_slice)
    prior = _aggregate_comparison_window(prior_slice)

    return {
        "tickets": _comparison_delta(current["tickets"], prior["tickets"]),
        "escalation_rate": _comparison_delta(current["escalation_rate"], prior["escalation_rate"]),
        "sla_compliance": _comparison_delta(current["sla_compliance"], prior["sla_compliance"]),
        "median_resolution": _comparison_delta(current["median_resolution"], prior["median_resolution"]),
        "fcr_rate": _comparison_delta(current["fcr_rate"], prior["fcr_rate"]),
    }


def _aggregate_comparison_window(window_df: pd.DataFrame) -> dict[str, float]:
    total_tickets = float(window_df["Tickets"].sum())
    if total_tickets <= 0:
        total_tickets = 1.0

    def weighted(column: str) -> float:
        return round(float((window_df[column] * window_df["Tickets"]).sum()) / total_tickets, 1)

    return {
        "tickets": float(window_df["Tickets"].sum()),
        "escalation_rate": weighted("Escalation Rate"),
        "sla_compliance": weighted("SLA Compliance"),
        "median_resolution": weighted("Median Resolution"),
        "fcr_rate": weighted("FCR Rate"),
    }


def _comparison_delta(current: float, prior: float) -> dict[str, float | str]:
    if prior == 0:
        return {"value": current, "prior": prior, "delta": 0.0, "pct": 0.0, "direction": "flat"}
    delta = current - prior
    pct = round(delta / max(abs(prior), 0.001) * 100, 1)
    direction = "up" if delta > 0 else "down" if delta < 0 else "flat"
    return {"value": current, "prior": prior, "delta": round(delta, 1), "pct": pct, "direction": direction}


# ---------------------------------------------------------------------------
# SLA Compliance
# ---------------------------------------------------------------------------

def compute_sla_compliance(
    df: pd.DataFrame,
    sla_targets: dict[str, int],
    queue_overrides: dict[str, int] | None = None,
) -> SLAMetrics:
    if "Resolution Minutes" not in df.columns:
        df = add_resolution_minutes(df)

    work = df[["Resolution Minutes"]].copy()
    work["Priority"] = _clean_series(df, "Priority")
    work["Queue"] = _clean_series(df, "Queue")
    work = work.dropna(subset=["Resolution Minutes"])

    if work.empty:
        return SLAMetrics()

    queue_ov = queue_overrides or {}

    def get_target(row):
        if row["Queue"] in queue_ov:
            return float(queue_ov[row["Queue"]])
        return float(sla_targets.get(row["Priority"], sla_targets.get("None", 1440)))

    work["SLA Target (min)"] = work.apply(get_target, axis=1)
    work["Met SLA"] = work["Resolution Minutes"] <= work["SLA Target (min)"]

    overall = _safe_pct(float(work["Met SLA"].sum()), float(len(work)))

    by_priority = (
        work.groupby("Priority")
        .agg(Tickets=("Met SLA", "count"), Met=("Met SLA", "sum"))
        .reset_index()
    )
    by_priority["Compliance"] = (by_priority["Met"] / by_priority["Tickets"].clip(lower=1) * 100).round(1)
    by_priority["Target (min)"] = by_priority["Priority"].map(
        lambda p: sla_targets.get(p, sla_targets.get("None", 1440))
    )
    by_priority = by_priority[["Priority", "Tickets", "Target (min)", "Compliance"]].sort_values(
        "Compliance", ascending=True
    ).reset_index(drop=True)

    breaching = work.loc[~work["Met SLA"]].copy()
    breach_cols = [c for c in ["Ticket Number", "Title", "Priority", "Queue", "Resolution Minutes", "SLA Target (min)"] if c in df.columns or c in breaching.columns]
    if "Ticket Number" in df.columns:
        breaching["Ticket Number"] = df.loc[breaching.index, "Ticket Number"]
    if "Title" in df.columns:
        breaching["Title"] = df.loc[breaching.index, "Title"]
    breach_out = breaching[[c for c in breach_cols if c in breaching.columns]].head(25).reset_index(drop=True)

    return SLAMetrics(
        overall_compliance=overall,
        by_priority=by_priority,
        breaching_tickets=breach_out,
    )


# ---------------------------------------------------------------------------
# Technician Scorecards
# ---------------------------------------------------------------------------

def compute_technician_scorecards(df: pd.DataFrame) -> pd.DataFrame:
    resource_col = "Primary Resource"
    if resource_col not in df.columns:
        return pd.DataFrame()

    if "Resolution Minutes" not in df.columns:
        df = add_resolution_minutes(df)

    resources = _clean_series(df, resource_col)
    work = df.loc[resources != ""].copy()
    work["_resource"] = resources.loc[resources != ""]

    if work.empty:
        return pd.DataFrame()

    escalation = _clean_series(work, "Escalation Reason")
    hours = pd.to_numeric(work.get("Total Hours Worked"), errors="coerce")

    grouped = work.groupby("_resource").agg(
        Tickets=("_resource", "count"),
        Avg_Hours=(hours.name if hours.name in work.columns else "_resource", lambda x: 0),
        Avg_Resolution=("Resolution Minutes", lambda x: round(x.dropna().mean(), 1) if x.dropna().any() else 0),
        Median_Resolution=("Resolution Minutes", lambda x: round(x.dropna().median(), 1) if x.dropna().any() else 0),
        Escalated=(escalation.name if escalation.name in work.columns else "_resource", lambda x: 0),
    ).reset_index()

    if "Total Hours Worked" in work.columns:
        avg_hours = (
            work.assign(_hours=pd.to_numeric(work["Total Hours Worked"], errors="coerce").fillna(0.0))
            .groupby("_resource")["_hours"]
            .mean()
            .round(2)
            .reset_index(name="Avg_Hours")
        )
        grouped = grouped.drop(columns=["Avg_Hours"]).merge(avg_hours, on="_resource", how="left")
    else:
        grouped["Avg_Hours"] = 0.0

    escalation_counts = work.loc[escalation != ""].groupby("_resource").size().reset_index(name="Escalated")
    grouped = grouped.drop(columns=["Escalated"]).merge(escalation_counts, on="_resource", how="left")
    grouped["Escalated"] = grouped["Escalated"].fillna(0).astype(int)
    grouped["Escalation Rate"] = (grouped["Escalated"] / grouped["Tickets"].clip(lower=1) * 100).round(1)

    fcr_counts = (
        work.loc[
            work["Resolution Minutes"].le(30) & escalation.eq("")
        ]
        .groupby("_resource")
        .size()
        .reset_index(name="FCR")
    )
    grouped = grouped.merge(fcr_counts, on="_resource", how="left")
    grouped["FCR"] = grouped["FCR"].fillna(0).astype(int)
    grouped["FCR Rate"] = (grouped["FCR"] / grouped["Tickets"].clip(lower=1) * 100).round(1)

    grouped.columns = [
        "Technician",
        "Tickets",
        "Avg Hours",
        "Avg Resolution (min)",
        "Median Resolution (min)",
        "Escalated",
        "Escalation Rate",
        "FCR",
        "FCR Rate",
    ]
    return grouped.sort_values("Tickets", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Repeat Contacts / Danger Zone
# ---------------------------------------------------------------------------

def compute_repeat_contacts(df: pd.DataFrame, threshold: int = 3) -> pd.DataFrame:
    contacts = _clean_series(df, "Contact")
    contacts = contacts.loc[contacts != ""]
    if contacts.empty:
        return pd.DataFrame(columns=["Contact", "Tickets", "Companies"])

    counts = contacts.value_counts()
    repeats = counts.loc[counts >= threshold]
    if repeats.empty:
        return pd.DataFrame(columns=["Contact", "Tickets", "Companies"])

    rows = []
    for contact_name, ticket_count in repeats.items():
        mask = contacts == contact_name
        companies = _clean_series(df.loc[mask.index[mask]], "Company").unique()
        companies_str = ", ".join(sorted(set(c for c in companies if c)))[:80]
        rows.append({"Contact": str(contact_name), "Tickets": int(ticket_count), "Companies": companies_str})

    return pd.DataFrame(rows).sort_values("Tickets", ascending=False).reset_index(drop=True)


def compute_danger_zone_companies(df: pd.DataFrame) -> pd.DataFrame:
    companies = _clean_series(df, "Company")
    escalations = _clean_series(df, "Escalation Reason")

    company_stats = df.loc[companies != ""].groupby(companies.loc[companies != ""]).agg(
        Tickets=("Company", "count"),
    ).reset_index()
    company_stats.columns = ["Company", "Tickets"]

    esc_counts = df.loc[(companies != "") & (escalations != "")].groupby(
        companies.loc[(companies != "") & (escalations != "")]
    ).size().reset_index(name="Escalated")
    esc_counts.columns = ["Company", "Escalated"]

    merged = company_stats.merge(esc_counts, on="Company", how="left")
    merged["Escalated"] = merged["Escalated"].fillna(0).astype(int)
    merged["Escalation Rate"] = (merged["Escalated"] / merged["Tickets"].clip(lower=1) * 100).round(1)
    merged = merged.loc[merged["Tickets"] >= 2].sort_values(
        ["Escalation Rate", "Tickets"], ascending=[False, False]
    ).reset_index(drop=True)

    return merged


# ---------------------------------------------------------------------------
# After-Hours Analysis
# ---------------------------------------------------------------------------

def compute_after_hours(df: pd.DataFrame) -> AfterHoursMetrics:
    created = pd.to_datetime(df.get("Created"), errors="coerce").dropna()
    if created.empty:
        return AfterHoursMetrics()

    total = len(created)
    is_weekend = created.dt.dayofweek >= 5
    is_after_hours = ~is_weekend & ((created.dt.hour < 8) | (created.dt.hour >= 18))

    weekend_count = int(is_weekend.sum())
    weekday_ah = int(is_after_hours.sum())
    total_ah = weekend_count + weekday_ah

    by_hour = created.dt.hour.value_counts().sort_index().rename_axis("Hour").reset_index(name="Tickets")
    by_day = created.dt.day_name().value_counts().reindex(
        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    ).fillna(0).astype(int).rename_axis("Day").reset_index(name="Tickets")

    return AfterHoursMetrics(
        total_after_hours=total_ah,
        after_hours_rate=_safe_pct(total_ah, total),
        weekday_after_hours=weekday_ah,
        weekend_count=weekend_count,
        by_hour=by_hour,
        by_day=by_day,
    )


def compute_after_hours_rate(df: pd.DataFrame) -> AfterHoursMetrics:
    return compute_after_hours(df)


# ---------------------------------------------------------------------------
# First Contact Resolution
# ---------------------------------------------------------------------------

def compute_fcr_rate(df: pd.DataFrame) -> float:
    if "Resolution Minutes" not in df.columns:
        df = add_resolution_minutes(df)

    queue = _clean_series(df, "Queue").str.lower()
    escalation = _clean_series(df, "Escalation Reason")
    resolution = df.get("Resolution Minutes")

    if resolution is None:
        return 0.0

    is_level_one = queue.str.contains("level i|triage", regex=True, na=False) & ~queue.str.contains("level ii", regex=True, na=False)
    is_fast = resolution.le(30)
    is_no_escalation = escalation.eq("")

    fcr_mask = is_level_one & is_fast & is_no_escalation
    total_eligible = int(is_level_one.sum())
    if total_eligible == 0:
        return 0.0

    return _safe_pct(float(fcr_mask.sum()), float(total_eligible))


# ---------------------------------------------------------------------------
# Noise Detection
# ---------------------------------------------------------------------------

def classify_noise(df: pd.DataFrame) -> NoiseMetrics:
    titles = _clean_series(df, "Title").str.lower()
    queues = _clean_series(df, "Queue").str.lower()

    title_noise = pd.Series(False, index=df.index)
    for pattern in NOISE_TITLE_PATTERNS:
        title_noise = title_noise | titles.str.contains(pattern, regex=True, na=False)

    queue_noise = pd.Series(False, index=df.index)
    for pattern in NOISE_QUEUE_PATTERNS:
        queue_noise = queue_noise | queues.str.contains(pattern, regex=True, na=False)

    sync_mask = titles.str.contains(r"sync\s*error", regex=True, na=False)
    spam_mask = queue_noise & ~sync_mask
    noise_mask = title_noise | queue_noise

    noise_df = df.loc[noise_mask].copy()

    return NoiseMetrics(
        spam_count=int(spam_mask.sum()),
        sync_error_count=int(sync_mask.sum()),
        total_noise=int(noise_mask.sum()),
        noise_rate=_safe_pct(float(noise_mask.sum()), float(len(df))),
        noise_df=noise_df,
    )


def compute_noise_tickets(df: pd.DataFrame) -> NoiseMetrics:
    return classify_noise(df)


# ---------------------------------------------------------------------------
# KB Gap Detection
# ---------------------------------------------------------------------------

def normalize_kb_values(df: pd.DataFrame) -> pd.DataFrame:
    if "KB Used" not in df.columns:
        return df.copy()

    normalized = df.copy()
    kb = _clean_series(normalized, "KB Used").str.lower()

    replacements = {
        "n/a": "",
        "na": "",
        "not available": "",
        "none": "",
        "no doc needed": "",
        "no doc availble": "",
    }
    normalized["KB Used"] = kb.replace(replacements)
    return normalized


def compute_kb_gaps(df: pd.DataFrame) -> pd.DataFrame:
    df = normalize_kb_values(df)
    kb = _clean_series(df, "KB Used").str.lower()

    is_request = kb.str.contains(r"kb\s*req", regex=True, na=False)
    is_na_variant = kb.isin(["n/a", "na", "n/a", "not available", "no doc needed", "no doc availble", "none", ""])
    is_blank = kb.eq("")

    gap_mask = is_request | (is_na_variant & ~is_blank)

    if not gap_mask.any():
        return pd.DataFrame(columns=["Ticket Number", "Title", "Issue Type", "KB Used"])

    cols = [c for c in ["Ticket Number", "Title", "Issue Type", "Escalation Reason", "KB Used"] if c in df.columns]
    return df.loc[gap_mask, cols].head(30).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Weekly Velocity
# ---------------------------------------------------------------------------

def compute_weekly_velocity(df: pd.DataFrame) -> pd.DataFrame:
    created = pd.to_datetime(df.get("Created"), errors="coerce").dropna()
    if created.empty:
        return pd.DataFrame(columns=["Week", "Tickets"])

    weeks = created.dt.isocalendar().week.astype(str)
    years = created.dt.isocalendar().year.astype(str)
    labels = years + "-W" + weeks.str.zfill(2)

    return labels.value_counts().sort_index().rename_axis("Week").reset_index(name="Tickets")


# ---------------------------------------------------------------------------
# Phase 8 analytics wrappers
# ---------------------------------------------------------------------------

def compute_complexity_scores(df: pd.DataFrame) -> pd.DataFrame:
    from analytics import compute_complexity_scores as _compute_complexity_scores

    return _compute_complexity_scores(df)


def classify_tickets_by_keyword(df: pd.DataFrame) -> pd.DataFrame:
    from analytics import classify_tickets_by_keyword as _classify_tickets_by_keyword

    return _classify_tickets_by_keyword(df)


def compute_workload_balance(df: pd.DataFrame) -> pd.DataFrame:
    from analytics import compute_workload_balance as _compute_workload_balance

    return _compute_workload_balance(df)


def compute_peak_heatmap(df: pd.DataFrame) -> dict:
    from analytics import compute_peak_heatmap as _compute_peak_heatmap

    return _compute_peak_heatmap(df)
