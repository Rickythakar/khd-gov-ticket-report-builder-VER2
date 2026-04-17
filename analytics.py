from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from metrics import add_resolution_minutes, _clean_series, _safe_pct


# ---------------------------------------------------------------------------
# 8A. Ticket Complexity Scoring
# ---------------------------------------------------------------------------

QUEUE_TIER = {
    "triage": 1, "level i": 2, "level ii": 3, "escalated to partner": 4, "spam": 0,
}

PRIORITY_WEIGHT = {
    "low": 1, "medium": 2, "high": 3, "critical": 4, "high (vip)": 4,
}


def compute_complexity_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Score each ticket 1-5 based on resolution time, hours, escalation, queue, priority."""
    if df.empty:
        return pd.DataFrame(columns=["Ticket Number", "Complexity"])

    work = df.copy()
    if "Resolution Minutes" not in work.columns:
        work = add_resolution_minutes(work)

    res = work["Resolution Minutes"].fillna(0)
    hours = pd.to_numeric(work.get("Total Hours Worked", 0), errors="coerce").fillna(0)
    esc = _clean_series(work, "Escalation Reason").ne("")
    queue = _clean_series(work, "Queue").str.lower()
    priority = _clean_series(work, "Priority").str.lower()

    # Percentile-based scoring (0-4 scale for each factor)
    res_pct = res.rank(pct=True).fillna(0)
    hrs_pct = hours.rank(pct=True).fillna(0)

    score = (
        (res_pct * 4).clip(0, 4) * 0.3 +
        (hrs_pct * 4).clip(0, 4) * 0.15 +
        esc.astype(float) * 1.0 +
        queue.map(QUEUE_TIER).fillna(1) * 0.3 +
        priority.map(PRIORITY_WEIGHT).fillna(2) * 0.25
    )

    # Normalize to 1-5
    mn, mx = score.min(), score.max()
    if mx > mn:
        normalized = 1 + (score - mn) / (mx - mn) * 4
    else:
        normalized = pd.Series(3.0, index=score.index)

    work["Complexity"] = normalized.round(1)

    cols = [c for c in ["Ticket Number", "Title", "Queue", "Priority", "Complexity"] if c in work.columns]
    return work[cols].sort_values("Complexity", ascending=False).reset_index(drop=True)


def complexity_summary(scores_df: pd.DataFrame) -> dict:
    """Summary stats from complexity scores."""
    if scores_df.empty or "Complexity" not in scores_df.columns:
        return {"mean": 0, "median": 0, "high_count": 0, "low_count": 0}
    c = scores_df["Complexity"]
    return {
        "mean": round(float(c.mean()), 1),
        "median": round(float(c.median()), 1),
        "high_count": int((c >= 4.0).sum()),
        "low_count": int((c <= 2.0).sum()),
    }


# ---------------------------------------------------------------------------
# 8B. Keyword Pattern Classification
# ---------------------------------------------------------------------------

KEYWORD_CATEGORIES = {
    "Password/Access": r"password|reset|locked|unlock|access|login|credential|mfa|2fa|authenticat",
    "Email/Outlook": r"email|outlook|mailbox|exchange|calendar|teams|o365|office\s*365",
    "Network/VPN": r"network|vpn|wifi|internet|connectivity|dns|dhcp|firewall|latency",
    "Software": r"software|update|install|citrix|application|app|patch|upgrade|license",
    "Hardware": r"computer|laptop|printer|monitor|device|peripheral|keyboard|mouse|dock",
    "Security": r"security|virus|malware|phishing|threat|breach|suspicious|compromis",
    "Account/AD": r"account|permission|group|active directory|\bad\b|user.?account|disable|enable",
    "Sync/Automated": r"sync.*error|synchronization|auto.?generated|entra connect",
}


def classify_by_keyword(df: pd.DataFrame) -> pd.DataFrame:
    """Classify tickets by title keywords into categories."""
    if df.empty:
        return pd.DataFrame(columns=["Category", "Tickets", "Share"])

    titles = _clean_series(df, "Title").str.lower()
    categories = []

    for _, title in titles.items():
        matched = "Other"
        for cat, pattern in KEYWORD_CATEGORIES.items():
            if re.search(pattern, title):
                matched = cat
                break
        categories.append(matched)

    df_out = df.copy()
    df_out["Keyword Category"] = categories

    counts = pd.Series(categories).value_counts()
    total = len(df)
    result = counts.rename_axis("Category").reset_index(name="Tickets")
    result["Share"] = (result["Tickets"] / max(total, 1) * 100).round(1)
    return result


def classify_tickets_by_keyword(df: pd.DataFrame) -> pd.DataFrame:
    """Compatibility alias for the Phase 8 public API name."""
    return classify_by_keyword(df)


def keyword_escalation_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Cross-tab: keyword category x escalation rate."""
    if df.empty:
        return pd.DataFrame()

    titles = _clean_series(df, "Title").str.lower()
    esc = _clean_series(df, "Escalation Reason").ne("")

    cats = []
    for title in titles:
        matched = "Other"
        for cat, pattern in KEYWORD_CATEGORIES.items():
            if re.search(pattern, title):
                matched = cat
                break
        cats.append(matched)

    temp = pd.DataFrame({"Category": cats, "Escalated": esc.values})
    grouped = temp.groupby("Category").agg(
        Tickets=("Escalated", "count"),
        Escalated=("Escalated", "sum"),
    ).reset_index()
    grouped["Esc Rate"] = (grouped["Escalated"] / grouped["Tickets"].clip(lower=1) * 100).round(1)
    return grouped.sort_values("Tickets", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 8C. Workload Imbalance Detection
# ---------------------------------------------------------------------------

def compute_workload_balance(df: pd.DataFrame) -> pd.DataFrame:
    """Per-tech workload vs team mean, flagging imbalance."""
    resource = _clean_series(df, "Primary Resource")
    work = df.loc[resource != ""].copy()
    work["_resource"] = resource.loc[resource != ""]
    if work.empty:
        return pd.DataFrame()

    counts = work.groupby("_resource").size().reset_index(name="Tickets")
    mean_val = counts["Tickets"].mean()
    std_val = counts["Tickets"].std()

    if std_val == 0 or pd.isna(std_val):
        counts["Deviation"] = 0.0
        counts["Status"] = "Balanced"
    else:
        counts["Deviation"] = ((counts["Tickets"] - mean_val) / std_val).round(2)
        counts["Status"] = counts["Deviation"].apply(
            lambda d: "Overloaded" if d > 1.5 else "Underutilized" if d < -1.5 else "Balanced"
        )

    counts.columns = ["Technician", "Tickets", "Deviation", "Status"]
    return counts.sort_values("Tickets", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 8D. Peak Load Heatmap
# ---------------------------------------------------------------------------

def compute_peak_heatmap(df: pd.DataFrame) -> dict:
    """7x24 grid of ticket volume by day-of-week x hour."""
    created = pd.to_datetime(df.get("Created"), errors="coerce").dropna()
    if created.empty:
        return {"grid": [], "days": [], "hours": list(range(24)), "peak_hour": 0, "peak_day": ""}

    days_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    dow = created.dt.dayofweek  # 0=Mon
    hour = created.dt.hour

    grid = []
    for d in range(7):
        row = []
        for h in range(24):
            count = int(((dow == d) & (hour == h)).sum())
            row.append(count)
        grid.append(row)

    flat = [(d, h, grid[d][h]) for d in range(7) for h in range(24)]
    peak = max(flat, key=lambda x: x[2])

    return {
        "grid": grid,
        "days": days_order,
        "hours": list(range(24)),
        "peak_hour": peak[1],
        "peak_day": days_order[peak[0]],
        "peak_count": peak[2],
        "max_val": max(max(row) for row in grid) if grid else 1,
    }


# ---------------------------------------------------------------------------
# 8E. KB Coverage Gap Analysis
# ---------------------------------------------------------------------------

def compute_kb_coverage(df: pd.DataFrame) -> pd.DataFrame:
    """Coverage % of KB Used per issue type."""
    if df.empty:
        return pd.DataFrame()

    issue = _clean_series(df, "Issue Type")
    kb = _clean_series(df, "KB Used").str.lower()

    # Valid KB = not empty, not N/A variants, not "KB Request"
    na_patterns = {"n/a", "na", "none", "no doc needed", "no doc availble", "not available", "kb request", "kb reqeust"}
    has_valid_kb = kb.apply(lambda v: v != "" and v not in na_patterns and v.startswith("http"))

    temp = pd.DataFrame({"Issue Type": issue.values, "Has KB": has_valid_kb.values})
    temp = temp.loc[temp["Issue Type"] != ""]

    grouped = temp.groupby("Issue Type").agg(
        Total=("Has KB", "count"),
        Linked=("Has KB", "sum"),
    ).reset_index()
    grouped["Coverage"] = (grouped["Linked"] / grouped["Total"].clip(lower=1) * 100).round(1)
    return grouped.sort_values("Coverage", ascending=True).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 8F. Repeat Issue Detection per Company
# ---------------------------------------------------------------------------

def compute_company_issue_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """Detect companies with recurring issues in the same keyword category."""
    if df.empty:
        return pd.DataFrame()

    companies = _clean_series(df, "Company")
    titles = _clean_series(df, "Title").str.lower()

    cats = []
    for title in titles:
        matched = "Other"
        for cat, pattern in KEYWORD_CATEGORIES.items():
            if re.search(pattern, title):
                matched = cat
                break
        cats.append(matched)

    temp = pd.DataFrame({"Company": companies.values, "Category": cats})
    temp = temp.loc[temp["Company"] != ""]

    grouped = temp.groupby(["Company", "Category"]).size().reset_index(name="Tickets")
    # Only flag combos with 3+ tickets
    flagged = grouped.loc[grouped["Tickets"] >= 3].sort_values("Tickets", ascending=False).reset_index(drop=True)
    return flagged


# ---------------------------------------------------------------------------
# 8G. Time-to-Escalation Analysis
# ---------------------------------------------------------------------------

def compute_escalation_timing(df: pd.DataFrame) -> pd.DataFrame:
    """For escalated tickets, categorize time between creation and escalation queue."""
    if "Resolution Minutes" not in df.columns:
        df = add_resolution_minutes(df)

    esc = _clean_series(df, "Escalation Reason")
    escalated = df.loc[esc != ""].copy()
    if escalated.empty:
        return pd.DataFrame(columns=["Timing", "Count", "Share"])

    res = escalated["Resolution Minutes"].fillna(0)

    def categorize(minutes):
        if minutes <= 5:
            return "Immediate (<5m)"
        elif minutes <= 30:
            return "Quick (<30m)"
        elif minutes <= 240:
            return "Delayed (<4h)"
        else:
            return "Late (4h+)"

    timing = res.apply(categorize)
    counts = timing.value_counts()
    order = ["Immediate (<5m)", "Quick (<30m)", "Delayed (<4h)", "Late (4h+)"]
    result = pd.DataFrame({"Timing": order})
    result["Count"] = result["Timing"].map(counts).fillna(0).astype(int)
    result["Share"] = (result["Count"] / max(len(escalated), 1) * 100).round(1)
    return result


# ---------------------------------------------------------------------------
# 8H. Description Complexity Scoring
# ---------------------------------------------------------------------------

def compute_description_complexity(df: pd.DataFrame) -> pd.DataFrame:
    """Categorize ticket complexity by description length."""
    desc = _clean_series(df, "Description")
    lengths = desc.str.len()

    def categorize(length):
        if length < 100:
            return "Simple"
        elif length < 500:
            return "Standard"
        elif length < 2000:
            return "Complex"
        else:
            return "Critical"

    cats = lengths.apply(categorize)
    counts = cats.value_counts()
    order = ["Simple", "Standard", "Complex", "Critical"]
    result = pd.DataFrame({"Complexity": order})
    result["Count"] = result["Complexity"].map(counts).fillna(0).astype(int)
    result["Share"] = (result["Count"] / max(len(df), 1) * 100).round(1)
    return result


# ---------------------------------------------------------------------------
# Master function
# ---------------------------------------------------------------------------

@dataclass
class AdvancedAnalytics:
    complexity_scores: pd.DataFrame = field(default_factory=pd.DataFrame)
    complexity_summary: dict = field(default_factory=dict)
    keyword_categories: pd.DataFrame = field(default_factory=pd.DataFrame)
    keyword_escalation: pd.DataFrame = field(default_factory=pd.DataFrame)
    workload_balance: pd.DataFrame = field(default_factory=pd.DataFrame)
    peak_heatmap: dict = field(default_factory=dict)
    kb_coverage: pd.DataFrame = field(default_factory=pd.DataFrame)
    company_patterns: pd.DataFrame = field(default_factory=pd.DataFrame)
    escalation_timing: pd.DataFrame = field(default_factory=pd.DataFrame)
    description_complexity: pd.DataFrame = field(default_factory=pd.DataFrame)


def compute_advanced_analytics(df: pd.DataFrame) -> AdvancedAnalytics:
    """Run all P8 analytics on a prepared DataFrame."""
    scores = compute_complexity_scores(df)
    return AdvancedAnalytics(
        complexity_scores=scores,
        complexity_summary=complexity_summary(scores),
        keyword_categories=classify_by_keyword(df),
        keyword_escalation=keyword_escalation_matrix(df),
        workload_balance=compute_workload_balance(df),
        peak_heatmap=compute_peak_heatmap(df),
        kb_coverage=compute_kb_coverage(df),
        company_patterns=compute_company_issue_patterns(df),
        escalation_timing=compute_escalation_timing(df),
        description_complexity=compute_description_complexity(df),
    )
