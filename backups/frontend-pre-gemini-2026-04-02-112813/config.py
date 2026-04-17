from __future__ import annotations

from pathlib import Path


APP_NAME = "KHD Governance Report Builder"
APP_VERSION = "1.0.0"
TITLE_PREFIX = "KHD Ticket Report"
REPORT_MODE_INTERNAL = "internal_analysis"
REPORT_MODE_CUSTOMER = "customer_deliverable"
DEFAULT_REPORT_MODE = REPORT_MODE_CUSTOMER
REPORT_MODE_LABELS = {
    REPORT_MODE_INTERNAL: "Internal Analysis Mode",
    REPORT_MODE_CUSTOMER: "Customer Deliverable Mode",
}
REPORT_MODE_DESCRIPTIONS = {
    REPORT_MODE_INTERNAL: "Richer diagnostics, QA review, raw preview, and deeper exploratory commentary for SDM preparation.",
    REPORT_MODE_CUSTOMER: "Customer-safe wording, polished governance insights, and deliverables designed for partner review.",
}

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_EXTENSION = ".xlsx"
DEFAULT_LOGO_PATH = BASE_DIR / "assets" / "hd_services_logo.png"

REQUIRED_COLUMNS = [
    "Ticket Number",
    "Nexus Ticket Number",
    "Title",
    "Company",
    "Created",
    "Complete Date",
    "Issue Type",
    "Queue",
    "Escalation Reason",
    "Source",
]

COLUMN_ALIASES: dict[str, list[str]] = {
    "Ticket Number": ["ticket #", "ticket id", "ticket", "service ticket number"],
    "Nexus Ticket Number": ["nexus ticket #", "nexus id", "nexus ticket id"],
    "External Customer Ticket Ref": ["external ticket number", "external ticket #", "external customer ticket ref", "external customer ticket reference"],
    "Title": ["summary", "ticket title", "subject"],
    "Company": ["account", "client", "customer", "organization"],
    "Parent Account": ["parentaccount", "parent acct", "parent customer", "parent client"],
    "Created": ["created date", "created on", "date created", "create date"],
    "Complete Date": ["completed", "completed date", "completion date", "closed date"],
    "Issue Type": ["type", "ticket type", "issue category"],
    "Sub-Issue Type": ["sub issue type", "sub issue", "sub-type", "subtype", "subcategory", "sub category"],
    "Queue": ["board", "team", "assignment queue"],
    "Escalation Reason": ["escalation", "escalation type", "escalation category", "reason"],
    "Source": ["ticket source", "origin", "channel"],
    "KB Used": ["kb used", "knowledge base", "kb article", "knowledge article", "kb link"],
    "Contact": ["contact name", "caller", "requester", "submitted by", "end user"],
    "Priority": ["ticket priority", "urgency", "severity"],
    "Primary Resource": ["resource", "technician", "assigned to", "tech", "agent"],
    "Total Hours Worked": ["hours worked", "total hours", "labor hours", "time spent"],
    "Status": ["ticket status", "state", "current status"],
}

VISIBLE_DETAIL_COLUMNS = [
    "Ticket Number",
    "Nexus Ticket Number",
    "External Customer Ticket Ref",
    "Title",
    "Company",
    "Created",
    "Complete Date",
    "Issue Type",
    "Sub-Issue Type",
    "Queue",
    "Escalation Reason",
    "Source",
    "KB Used",
]

VISIBLE_INTERNAL_COLUMNS = [
    "Ticket Number",
    "Nexus Ticket Number",
    "External Customer Ticket Ref",
    "Title",
    "Company",
    "Contact",
    "Created",
    "Complete Date",
    "Issue Type",
    "Sub-Issue Type",
    "Queue",
    "Escalation Reason",
    "Source",
    "Priority",
    "Primary Resource",
    "Total Hours Worked",
    "KB Used",
]

NOISE_TITLE_PATTERNS = [
    r"sync\s*error",
    r"auto[\s\-]?generated",
    r"test\s*ticket",
]

NOISE_QUEUE_PATTERNS = [
    r"spam",
]

SUMMARY_TABLE_LIMIT = 8
INSIGHT_LIMIT = 5

SHEET_SUMMARY = "Summary"
SHEET_TICKETS = "Tickets"
SHEET_ESCALATIONS = "Escalations"
SHEET_TRENDS = "Trends"
SHEET_RAW_DATA = "Raw Data"
SHEET_TECHNICIAN_REVIEW = "Technician Review"

WORKBOOK_SHEETS = [
    SHEET_SUMMARY,
    SHEET_TICKETS,
    SHEET_ESCALATIONS,
    SHEET_TRENDS,
    SHEET_RAW_DATA,
    SHEET_TECHNICIAN_REVIEW,
]

EXCLUDED_WORKBOOK_COLUMNS = {"Resource", "Primary Resource", "Description"}

ESCALATION_SCOPE_MAP: dict[str, str] = {
    "end user direct request": "Controllable",
    "extended resolution time": "Controllable",
    "insufficient itg credentials": "Controllable",
    "insufficient itg documentation": "Controllable",
    "device & peripheral management": "Uncontrollable",
    "device and peripheral management": "Uncontrollable",
    "3rd party support": "Uncontrollable",
    "third party support": "Uncontrollable",
    "billing inquiries/purchases": "Uncontrollable",
    "billing inquiries purchases": "Uncontrollable",
    "downed user": "Uncontrollable",
    "owned user": "Uncontrollable",
    "infrastructure management": "Uncontrollable",
    "scheduled services": "Uncontrollable",
    "security": "Uncontrollable",
    "unsupported company": "Uncontrollable",
    "msp direct request": "Other",
    "msp - direct request": "Other",
    "customer unresponsive": "Other",
    "out of scope": "Other",
    "spam": "Other",
    "vip": "Other",
}
