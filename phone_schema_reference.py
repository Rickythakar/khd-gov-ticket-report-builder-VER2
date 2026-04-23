from __future__ import annotations

"""Canonical phone schema reference and Power BI phone export mapping."""


PHONE_SOURCE_SCHEMA = "powerbi_phone_export"
PHONE_SOURCE_LABEL = "Power BI phone export"

POWER_BI_PHONE_REQUIRED_SOURCE_COLUMNS = [
    "Call ID",
    "Call Timestamp",
    "Disposition",
    "Call Type",
    "Answered",
    "Abandoned",
    "Queue Wait Time (Sec)",
]

POWER_BI_PHONE_OPTIONAL_SOURCE_COLUMNS = [
    "Campaign",
    "Skill",
    "DNIS",
    "DNIS Country",
    "Reseller",
    "Client",
    "Speed of Answer (Sec)",
    "Hold Time (Sec)",
    "Handle Time (Mins)",
    "Out of Compliance Overage",
    "Service Level",
    "Service Level Category",
]

POWER_BI_PHONE_TO_CANONICAL_MAP: dict[str, str] = {
    "Call ID": "Call ID",
    "Call Timestamp": "Call Timestamp",
    "Campaign": "Campaign",
    "Disposition": "Disposition",
    "Skill": "Queue",
    "Call Type": "Direction",
    "DNIS": "Phone Number",
    "DNIS Country": "Phone Region",
    "Reseller": "Partner",
    "Client": "Client",
    "Abandoned": "Abandoned Flag",
    "Answered": "Answered Flag",
    "Queue Wait Time (Sec)": "Wait Seconds",
    "Speed of Answer (Sec)": "Answer Seconds",
    "Hold Time (Sec)": "Hold Seconds",
    "Handle Time (Mins)": "Handle Minutes",
    "Out of Compliance Overage": "SLO Overage Bucket",
    "Service Level": "Service Level Value",
    "Service Level Category": "Service Level Category",
}

CANONICAL_PHONE_REQUIRED_FIELDS = [
    "Call ID",
    "Call Timestamp",
    "Call Date",
    "Call Hour",
    "Queue",
    "Direction",
    "Disposition",
    "Answered Flag",
    "Abandoned Flag",
    "Wait Seconds",
]

CANONICAL_PHONE_FIELDS = [
    "Call ID",
    "Call Timestamp",
    "Call Date",
    "Call Hour",
    "Campaign",
    "Disposition",
    "Queue",
    "Direction",
    "Phone Number",
    "Phone Region",
    "Partner",
    "Client",
    "Agent",
    "Abandoned Flag",
    "Answered Flag",
    "Wait Seconds",
    "Answer Seconds",
    "Hold Seconds",
    "Handle Minutes",
    "Handle Seconds",
    "SLO Overage Bucket",
    "Service Level Value",
    "Service Level Category",
]

PHONE_SCHEMA_REFERENCE: dict[str, dict[str, str]] = {
    "Call ID": {"power_bi_source": "Call ID", "mode": "direct"},
    "Call Timestamp": {"power_bi_source": "Call Timestamp", "mode": "direct"},
    "Call Date": {"power_bi_source": "Call Timestamp", "mode": "derived"},
    "Call Hour": {"power_bi_source": "Call Timestamp", "mode": "derived"},
    "Campaign": {"power_bi_source": "Campaign", "mode": "direct"},
    "Disposition": {"power_bi_source": "Disposition", "mode": "direct"},
    "Queue": {"power_bi_source": "Skill", "mode": "direct"},
    "Direction": {"power_bi_source": "Call Type", "mode": "direct"},
    "Phone Number": {"power_bi_source": "DNIS", "mode": "direct"},
    "Phone Region": {"power_bi_source": "DNIS Country", "mode": "direct"},
    "Partner": {"power_bi_source": "Reseller", "mode": "direct"},
    "Client": {"power_bi_source": "Client", "mode": "direct"},
    "Agent": {"power_bi_source": "Not present", "mode": "default_blank"},
    "Abandoned Flag": {"power_bi_source": "Abandoned", "mode": "direct"},
    "Answered Flag": {"power_bi_source": "Answered", "mode": "direct"},
    "Wait Seconds": {"power_bi_source": "Queue Wait Time (Sec)", "mode": "direct"},
    "Answer Seconds": {"power_bi_source": "Speed of Answer (Sec)", "mode": "direct"},
    "Hold Seconds": {"power_bi_source": "Hold Time (Sec)", "mode": "direct"},
    "Handle Minutes": {"power_bi_source": "Handle Time (Mins)", "mode": "direct"},
    "Handle Seconds": {"power_bi_source": "Handle Time (Mins)", "mode": "derived"},
    "SLO Overage Bucket": {"power_bi_source": "Out of Compliance Overage", "mode": "direct"},
    "Service Level Value": {"power_bi_source": "Service Level", "mode": "direct"},
    "Service Level Category": {"power_bi_source": "Service Level Category", "mode": "direct"},
}

POWER_BI_PHONE_NORMALIZATION_NOTES = [
    "Phone reporting is call-event based and should not be interpreted as ticket volume.",
]
