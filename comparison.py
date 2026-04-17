from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from metrics import (
    add_resolution_minutes,
    compute_resolution_metrics,
    compute_sla_compliance,
    compute_fcr_rate,
    classify_noise,
    format_minutes,
)


@dataclass
class MonthBucket:
    label: str  # "2026-03"
    df: pd.DataFrame
    ticket_count: int = 0
    escalation_rate: float = 0.0
    sla_compliance: float = 0.0
    median_resolution: float = 0.0
    fcr_rate: float = 0.0
    noise_count: int = 0


@dataclass
class PeriodComparison:
    current: MonthBucket | None = None
    prior: MonthBucket | None = None
    months: list[MonthBucket] = field(default_factory=list)
    deltas: dict[str, dict] = field(default_factory=dict)
    trends: dict[str, list] = field(default_factory=dict)


def _clean_series(df: pd.DataFrame, col: str) -> pd.Series:
    return df.get(col, pd.Series(dtype=str)).fillna("").astype(str).str.strip()


def bucket_by_month(df: pd.DataFrame) -> list[MonthBucket]:
    """Split a DataFrame into monthly buckets based on Created date."""
    created = pd.to_datetime(df.get("Created"), errors="coerce")
    df = df.copy()
    df["_month"] = created.dt.to_period("M")
    df = df.dropna(subset=["_month"])

    buckets = []
    for period in sorted(df["_month"].unique()):
        month_df = df[df["_month"] == period].drop(columns=["_month"]).copy()
        month_df = add_resolution_minutes(month_df)

        escalation = _clean_series(month_df, "Escalation Reason")
        esc_count = int((escalation != "").sum())
        total = len(month_df)

        sla_targets = {"Critical": 60, "High": 240, "Medium": 480, "Low": 1440, "None": 1440}
        sla = compute_sla_compliance(month_df, sla_targets)
        rm = compute_resolution_metrics(month_df)
        fcr = compute_fcr_rate(month_df)
        noise = classify_noise(month_df)

        buckets.append(MonthBucket(
            label=str(period),
            df=month_df,
            ticket_count=total,
            escalation_rate=round(esc_count / max(total, 1) * 100, 1),
            sla_compliance=sla.overall_compliance,
            median_resolution=rm.median_minutes,
            fcr_rate=fcr,
            noise_count=noise.total_noise,
        ))

    return buckets


def _compute_delta(current: float, prior: float) -> dict:
    """Compute delta between two values."""
    if prior == 0:
        return {"value": current, "prior": prior, "delta": 0.0, "pct": 0.0, "direction": "flat"}
    delta = current - prior
    pct = round(delta / max(abs(prior), 0.001) * 100, 1)
    direction = "up" if delta > 0 else "down" if delta < 0 else "flat"
    return {"value": current, "prior": prior, "delta": round(delta, 1), "pct": pct, "direction": direction}


def compute_comparison(
    buckets: list[MonthBucket],
    period: str = "1M",
) -> PeriodComparison:
    """Compute comparison metrics for the selected period.

    period: "1M" = latest month vs prior, "QTR" = last 3 months, "HALF" = last 6, "YR" = all
    """
    if not buckets:
        return PeriodComparison()

    # Select months based on period
    if period == "1M":
        selected = buckets[-1:]
        prior_selected = buckets[-2:-1] if len(buckets) > 1 else []
    elif period == "QTR":
        selected = buckets[-3:]
        prior_selected = buckets[-6:-3] if len(buckets) > 3 else []
    elif period == "HALF":
        selected = buckets[-6:]
        prior_selected = buckets[-12:-6] if len(buckets) > 6 else []
    else:  # YR
        selected = buckets[-12:]
        prior_selected = []

    if not selected:
        return PeriodComparison()

    current = _aggregate_bucket(selected)
    prior = _aggregate_bucket(prior_selected) if prior_selected else None

    # Compute deltas
    deltas = {}
    if prior:
        deltas["tickets"] = _compute_delta(current.ticket_count, prior.ticket_count)
        deltas["escalation_rate"] = _compute_delta(current.escalation_rate, prior.escalation_rate)
        deltas["sla_compliance"] = _compute_delta(current.sla_compliance, prior.sla_compliance)
        deltas["median_resolution"] = _compute_delta(current.median_resolution, prior.median_resolution)
        deltas["fcr_rate"] = _compute_delta(current.fcr_rate, prior.fcr_rate)

    # Build trend lines (all months)
    trends = {
        "labels": [b.label for b in buckets],
        "tickets": [b.ticket_count for b in buckets],
        "escalation_rate": [b.escalation_rate for b in buckets],
        "sla_compliance": [b.sla_compliance for b in buckets],
        "median_resolution": [b.median_resolution for b in buckets],
        "fcr_rate": [b.fcr_rate for b in buckets],
    }

    return PeriodComparison(
        current=current,
        prior=prior,
        months=buckets,
        deltas=deltas,
        trends=trends,
    )


def _aggregate_bucket(buckets: list[MonthBucket]) -> MonthBucket:
    """Aggregate multiple month buckets into one summary."""
    if not buckets:
        return MonthBucket(label="", df=pd.DataFrame())
    if len(buckets) == 1:
        return buckets[0]

    combined_df = pd.concat([b.df for b in buckets], ignore_index=True)
    total = sum(b.ticket_count for b in buckets)

    return MonthBucket(
        label=f"{buckets[0].label} - {buckets[-1].label}",
        df=combined_df,
        ticket_count=total,
        escalation_rate=round(sum(b.escalation_rate * b.ticket_count for b in buckets) / max(total, 1), 1),
        sla_compliance=round(sum(b.sla_compliance * b.ticket_count for b in buckets) / max(total, 1), 1),
        median_resolution=round(sum(b.median_resolution * b.ticket_count for b in buckets) / max(total, 1), 1),
        fcr_rate=round(sum(b.fcr_rate * b.ticket_count for b in buckets) / max(total, 1), 1),
        noise_count=sum(b.noise_count for b in buckets),
    )


def serialize_comparison(comp: PeriodComparison) -> dict:
    """Convert comparison to JSON-safe dict for the template."""
    if comp.current is None:
        return {"has_comparison": False}

    return {
        "has_comparison": len(comp.months) > 1,
        "month_count": len(comp.months),
        "current_label": comp.current.label if comp.current else "",
        "prior_label": comp.prior.label if comp.prior else "",
        "deltas": comp.deltas,
        "trends": comp.trends,
        "months": [
            {
                "label": b.label,
                "tickets": b.ticket_count,
                "escalation_rate": b.escalation_rate,
                "sla": b.sla_compliance,
                "median_res": b.median_resolution,
                "median_res_fmt": format_minutes(b.median_resolution),
                "fcr": b.fcr_rate,
                "noise": b.noise_count,
            }
            for b in comp.months
        ],
    }
