from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from config import (
    DEFAULT_OUTPUT_EXTENSION,
    DEFAULT_REPORT_MODE,
    ESCALATION_SCOPE_MAP,
    EXCLUDED_WORKBOOK_COLUMNS,
    REPORT_MODE_CUSTOMER,
    REPORT_MODE_INTERNAL,
    SUMMARY_TABLE_LIMIT,
    TITLE_PREFIX,
)


@dataclass
class ReportArtifacts:
    report_mode: str
    normalized_df: pd.DataFrame
    workbook_df: pd.DataFrame
    tickets_view: pd.DataFrame
    escalated_df: pd.DataFrame
    queue_table: pd.DataFrame
    escalation_table: pd.DataFrame
    escalation_category_table: pd.DataFrame
    source_table: pd.DataFrame
    company_table: pd.DataFrame
    issue_type_table: pd.DataFrame
    sub_issue_type_table: pd.DataFrame
    kb_request_table: pd.DataFrame
    monthly_trend_table: pd.DataFrame
    open_ticket_table: pd.DataFrame
    headline_metrics: list[tuple[str, str]]
    narrative: list[str]
    executive_brief: str
    executive_brief_points: list[str]
    service_observations: list[str]
    priority_actions: list[str]
    risk_flags: list[str]
    data_quality_notes: list[str]


def build_output_path(save_directory: str, output_filename: str) -> Path:
    cleaned_name = output_filename.strip()
    if not cleaned_name.lower().endswith(DEFAULT_OUTPUT_EXTENSION):
        cleaned_name = f"{cleaned_name}{DEFAULT_OUTPUT_EXTENSION}"
    return Path(save_directory).expanduser().resolve() / cleaned_name


def default_filename_from_title(report_title: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", report_title.strip()).strip("_")
    return cleaned or "khd_ticket_report"


def build_report_title(partner_name: str, date_range: str, custom_title: str = "") -> str:
    custom = custom_title.strip()
    if custom:
        return custom

    partner = partner_name.strip()
    range_text = date_range.strip()

    if partner and range_text:
        return f"{TITLE_PREFIX} {range_text} - {partner}"
    if range_text:
        return f"{TITLE_PREFIX} {range_text}"
    if partner:
        return f"{TITLE_PREFIX} - {partner}"
    return TITLE_PREFIX


def ensure_parent_directory(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def dataframe_for_excel(dataframe: pd.DataFrame) -> pd.DataFrame:
    export_df = dataframe.copy()
    for column_name in export_df.columns:
        if pd.api.types.is_datetime64_any_dtype(export_df[column_name]):
            export_df[column_name] = export_df[column_name].apply(
                lambda value: value.to_pydatetime() if pd.notna(value) else None
            )
        else:
            export_df[column_name] = export_df[column_name].fillna("")
    return export_df


def filter_workbook_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    keep_columns = [column for column in dataframe.columns if str(column).strip() not in EXCLUDED_WORKBOOK_COLUMNS]
    return dataframe[keep_columns].copy()


def select_reference_ticket_column(dataframe: pd.DataFrame) -> pd.DataFrame:
    export_df = dataframe.copy()
    nexus_column = "Nexus Ticket Number"
    external_column = "External Customer Ticket Ref"

    if nexus_column not in export_df.columns and external_column not in export_df.columns:
        return export_df

    nexus_series = _clean_text_series(export_df, nexus_column) if nexus_column in export_df.columns else pd.Series(dtype=str)
    external_series = _clean_text_series(export_df, external_column) if external_column in export_df.columns else pd.Series(dtype=str)

    nexus_has_values = nexus_column in export_df.columns and nexus_series.ne("").any()
    external_has_values = external_column in export_df.columns and external_series.ne("").any()

    if nexus_has_values:
        if external_column in export_df.columns:
            export_df = export_df.drop(columns=[external_column])
        return export_df

    if external_has_values:
        export_df[external_column] = external_series
        if nexus_column in export_df.columns:
            export_df = export_df.drop(columns=[nexus_column])
        columns = list(export_df.columns)
        external_index = columns.index(external_column)
        columns[external_index] = nexus_column
        export_df.columns = columns
    else:
        if external_column in export_df.columns:
            export_df = export_df.drop(columns=[external_column])
    return export_df


def write_dataframe_to_excel_sheet(
    worksheet,
    dataframe: pd.DataFrame,
    workbook,
    table_name: str,
    column_width_overrides: dict[str, float] | None = None,
    start_row: int = 0,
    start_col: int = 0,
    freeze_header: bool = False,
) -> None:
    safe_df = dataframe_for_excel(dataframe)
    rows = len(safe_df)
    columns = list(safe_df.columns)

    if not columns:
        worksheet.write(start_row, start_col, "No data available")
        return

    header_format = workbook.add_format(
        {
            "bold": True,
            "font_color": "#FFFFFF",
            "bg_color": "#144A75",
            "border": 1,
            "border_color": "#D8E4EF",
            "valign": "vcenter",
        }
    )
    body_format = workbook.add_format(
        {
            "border": 1,
            "border_color": "#E3EBF3",
            "valign": "vcenter",
        }
    )
    wrapped_body_format = workbook.add_format(
        {
            "border": 1,
            "border_color": "#E3EBF3",
            "valign": "top",
            "text_wrap": True,
        }
    )
    date_format = workbook.add_format(
        {
            "num_format": "m/d/yyyy h:mm",
            "border": 1,
            "border_color": "#E3EBF3",
            "valign": "vcenter",
        }
    )

    overrides = column_width_overrides or {}
    column_widths: dict[str, float] = {}
    wrap_columns = {
        "Title",
        "Escalation Reason",
        "Queue",
        "Issue Type",
        "Sub-Issue Type",
        "Company",
        "Parent Account",
        "Escalation Category",
    }

    for col_index, column_name in enumerate(columns):
        worksheet.write(start_row, start_col + col_index, column_name, header_format)
        series = safe_df[column_name]
        max_len = max([len(str(column_name))] + [len(str(value)) for value in series.head(250).tolist()])
        computed_width = min(max(max_len + 2, 12), 56)
        width = overrides.get(column_name, computed_width)
        column_widths[column_name] = width
        worksheet.set_column(start_col + col_index, start_col + col_index, width)

    for row_index, row in enumerate(safe_df.itertuples(index=False, name=None), start=1):
        estimated_height = 20
        for col_index, value in enumerate(row):
            column_name = columns[col_index]
            if isinstance(value, pd.Timestamp):
                value = value.to_pydatetime()
            if pd.isna(value) if not isinstance(value, str) else False:
                value = None
            if pd.api.types.is_datetime64_any_dtype(safe_df[column_name]):
                cell_format = date_format
            elif column_name in wrap_columns:
                cell_format = wrapped_body_format
                text_value = str(value or "")
                visible_width = max(int(column_widths.get(column_name, 18)) - 1, 8)
                estimated_lines = max(1, min(4, (len(text_value) // visible_width) + 1))
                estimated_height = max(estimated_height, 18 * estimated_lines)
            else:
                cell_format = body_format
            worksheet.write(start_row + row_index, start_col + col_index, value, cell_format)
        worksheet.set_row(start_row + row_index, estimated_height)

    worksheet.add_table(
        start_row,
        start_col,
        start_row + max(rows, 1),
        start_col + len(columns) - 1,
        {
            "name": table_name,
            "columns": [{"header": column_name} for column_name in columns],
            "style": "Table Style Light 8",
            "autofilter": True,
        },
    )
    if freeze_header:
        worksheet.freeze_panes(start_row + 1, start_col)


def _clean_text_series(dataframe: pd.DataFrame, column_name: str) -> pd.Series:
    return dataframe.get(column_name, pd.Series(dtype=str)).fillna("").astype(str).str.strip()


def normalize_lookup_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().lower()).strip()


NORMALIZED_ESCALATION_SCOPE_MAP = {
    normalize_lookup_key(reason): scope
    for reason, scope in ESCALATION_SCOPE_MAP.items()
}


def classify_escalation_scope(reason: str) -> str:
    cleaned_reason = str(reason or "").strip()
    if not cleaned_reason:
        return "Other"
    return NORMALIZED_ESCALATION_SCOPE_MAP.get(normalize_lookup_key(cleaned_reason), "Other")


def infer_partner_name(dataframe: pd.DataFrame) -> str:
    parent_account_series = _clean_text_series(dataframe, "Parent Account")
    parent_account_series = parent_account_series.loc[parent_account_series != ""]
    if not parent_account_series.empty:
        return str(parent_account_series.value_counts().idxmax()).strip()
    return ""


def infer_date_range(dataframe: pd.DataFrame) -> str:
    completion_dates = pd.to_datetime(dataframe.get("Complete Date"), errors="coerce")
    source_dates = completion_dates if completion_dates.notna().any() else pd.to_datetime(dataframe.get("Created"), errors="coerce")
    source_dates = source_dates.dropna()
    if source_dates.empty:
        return ""

    start_date = source_dates.min()
    end_date = source_dates.max()

    if start_date.year == end_date.year and start_date.month == end_date.month:
        return start_date.strftime("%B %Y")
    return f"{start_date.strftime('%b %Y')} - {end_date.strftime('%b %Y')}"


def _find_repeat_patterns(dataframe: pd.DataFrame) -> list[tuple[str, int]]:
    title_series = _clean_text_series(dataframe, "Title").str.lower()
    title_series = (
        title_series.str.replace(r"\s+", " ", regex=True)
        .str.replace(r"\d+", "", regex=True)
        .str.strip(" -_:")
    )
    counts = title_series.loc[title_series != ""].value_counts()
    repeats = [(str(title), int(count)) for title, count in counts.items() if int(count) >= 2]
    return repeats[:3]


def _safe_share(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) / max(float(denominator), 1.0) * 100, 1)


def _is_partner_escalation_queue(value: str) -> bool:
    normalized = normalize_lookup_key(value)
    return "escalated to partner" in normalized


def _kb_request_table(dataframe: pd.DataFrame) -> pd.DataFrame:
    if "KB Used" not in dataframe.columns:
        return pd.DataFrame(columns=["Ticket Number", "Nexus Ticket Number", "Title"])

    kb_series = _clean_text_series(dataframe, "KB Used")
    kb_rows = dataframe.loc[kb_series != ""].copy()
    if kb_rows.empty:
        return pd.DataFrame(columns=["Ticket Number", "Nexus Ticket Number", "Title"])

    preferred_columns = [column for column in ["Ticket Number", "Nexus Ticket Number", "Title", "KB Used"] if column in kb_rows.columns]
    return kb_rows[preferred_columns].head(8).reset_index(drop=True)


def _reference_ticket_column(dataframe: pd.DataFrame) -> str:
    for column_name in ["Nexus Ticket Number", "Ticket Number"]:
        if column_name in dataframe.columns:
            return column_name
    return dataframe.columns[0] if len(dataframe.columns) else "Ticket Number"


def _format_named_shares(dataframe: pd.DataFrame, label_column: str, *, limit: int = 2) -> str:
    if dataframe.empty or label_column not in dataframe.columns:
        return ""
    snippets: list[str] = []
    for _, row in dataframe.head(limit).iterrows():
        snippets.append(f"{row[label_column]} ({row['Share']}%)")
    return ", ".join(snippets)


def build_top_table(
    dataframe: pd.DataFrame,
    column_name: str,
    label: str,
    *,
    include_blank_row: bool = False,
    limit: int = SUMMARY_TABLE_LIMIT,
) -> pd.DataFrame:
    series = _clean_text_series(dataframe, column_name)
    counts = series.value_counts(dropna=False)
    blank_count = int(counts.get("", 0))
    counts = counts.drop(labels=[""], errors="ignore")

    top = counts.head(limit)
    frame = top.rename_axis(label).reset_index(name="Tickets")
    if not frame.empty:
        frame["Share"] = (frame["Tickets"] / max(len(dataframe), 1) * 100).round(1)

    if include_blank_row and blank_count:
        blank_frame = pd.DataFrame([{label: "Missing / Blank", "Tickets": blank_count, "Share": round(blank_count / max(len(dataframe), 1) * 100, 1)}])
        frame = pd.concat([frame, blank_frame], ignore_index=True)

    return frame


def build_report_artifacts(dataframe: pd.DataFrame, report_mode: str = DEFAULT_REPORT_MODE) -> ReportArtifacts:
    if report_mode not in {REPORT_MODE_INTERNAL, REPORT_MODE_CUSTOMER}:
        report_mode = DEFAULT_REPORT_MODE

    normalized_df = dataframe.copy()
    completion_dates = pd.to_datetime(normalized_df.get("Complete Date"), errors="coerce")
    report_df = normalized_df.loc[completion_dates.notna()].copy()
    workbook_df = select_reference_ticket_column(filter_workbook_columns(report_df))
    tickets_view = workbook_df.copy()

    escalation_series = _clean_text_series(report_df, "Escalation Reason")
    queue_series = _clean_text_series(report_df, "Queue")
    unexpected_blank_escalations = report_df.loc[
        escalation_series.eq("") & queue_series.apply(_is_partner_escalation_queue)
    ].copy()
    escalated_df = workbook_df.loc[escalation_series != ""].copy()
    if not escalated_df.empty:
        escalated_df["Escalation Category"] = escalated_df["Escalation Reason"].apply(classify_escalation_scope)

    queue_table = build_top_table(report_df, "Queue", "Queue")
    escalation_table = build_top_table(report_df.loc[escalation_series != ""], "Escalation Reason", "Escalation Reason")
    escalation_category_table = pd.DataFrame(columns=["Category", "Escalation Reason", "Tickets", "Share"])
    if not escalated_df.empty:
        category_counts = (
            escalated_df.groupby(["Escalation Category", "Escalation Reason"], dropna=False)
            .size()
            .reset_index(name="Tickets")
            .sort_values(["Escalation Category", "Tickets", "Escalation Reason"], ascending=[True, False, True])
        )
        category_counts.rename(columns={"Escalation Category": "Category"}, inplace=True)
        category_counts["Share"] = (category_counts["Tickets"] / max(len(escalated_df), 1) * 100).round(1)
        category_counts["Category Rank"] = category_counts["Category"].map({"Controllable": 0, "Uncontrollable": 1, "Other": 2}).fillna(3)
        escalation_category_table = (
            category_counts.sort_values(["Category Rank", "Tickets", "Escalation Reason"], ascending=[True, False, True])
            .drop(columns=["Category Rank"])
            .reset_index(drop=True)
        )
    source_table = build_top_table(report_df, "Source", "Source")
    company_table = build_top_table(report_df, "Company", "Company")
    issue_type_table = build_top_table(report_df, "Issue Type", "Issue Type")
    sub_issue_type_table = build_top_table(report_df, "Sub-Issue Type", "Sub-Issue Type")
    kb_request_table = _kb_request_table(workbook_df)
    created_dates = pd.to_datetime(report_df.get("Created"), errors="coerce")
    monthly_trend_table = pd.DataFrame(columns=["Month", "Tickets"])
    if created_dates.notna().any():
        monthly_trend_table = (
            created_dates.dropna()
            .dt.to_period("M")
            .astype(str)
            .value_counts()
            .sort_index()
            .rename_axis("Month")
            .reset_index(name="Tickets")
        )
    open_ticket_table = pd.DataFrame()

    total_tickets = len(report_df)
    escalated_count = len(escalated_df)
    escalation_rate = round((escalated_count / max(total_tickets, 1)) * 100, 1)
    unique_companies = int(_clean_text_series(report_df, "Company").replace("", pd.NA).dropna().nunique())
    top_issue = issue_type_table.iloc[0]["Issue Type"] if not issue_type_table.empty else "N/A"
    top_source = source_table.iloc[0]["Source"] if not source_table.empty else "N/A"

    undefined_share = 0.0
    if not escalation_category_table.empty:
        undefined_tickets = int(
            escalation_category_table.loc[escalation_category_table["Category"] == "Other", "Tickets"].sum()
        )
        undefined_share = round(undefined_tickets / max(len(escalated_df), 1) * 100, 1)

    controllable_share = 0.0
    if not escalated_df.empty:
        controllable_share = round(
            float((escalated_df["Escalation Category"] == "Controllable").sum()) / max(len(escalated_df), 1) * 100,
            1,
        )

    top_queue_share = float(queue_table.iloc[0]["Share"]) if not queue_table.empty else 0.0

    headline_metrics = [
        ("Total Tickets", str(total_tickets)),
        ("Escalated Tickets", str(escalated_count)),
        ("Escalation Rate", f"{escalation_rate}%"),
        ("Customer Accounts", str(unique_companies)),
        ("Leading Request Type", str(top_issue)),
        ("Primary Intake Channel", str(top_source)),
    ]

    top_source_row = source_table.iloc[0] if not source_table.empty else None
    second_source_row = source_table.iloc[1] if len(source_table) > 1 else None
    top_issue_row = issue_type_table.iloc[0] if not issue_type_table.empty else None
    top_company_row = company_table.iloc[0] if not company_table.empty else None
    second_company_row = company_table.iloc[1] if len(company_table) > 1 else None
    repeat_patterns = _find_repeat_patterns(report_df)
    top_escalation = escalation_table.copy()
    top_escalation_row = top_escalation.iloc[0] if not top_escalation.empty else None
    second_escalation_row = top_escalation.iloc[1] if len(top_escalation) > 1 else None
    second_issue_row = issue_type_table.iloc[1] if len(issue_type_table) > 1 else None

    source_gap_share = 0.0
    if top_source_row is not None and second_source_row is not None:
        source_gap_share = round(float(top_source_row["Share"]) - float(second_source_row["Share"]), 1)

    company_concentration_share = float(top_company_row["Share"]) if top_company_row is not None else 0.0
    reference_column = _reference_ticket_column(kb_request_table) if not kb_request_table.empty else "Ticket Number"
    kb_count = int(_clean_text_series(report_df, "KB Used").ne("").sum()) if "KB Used" in report_df.columns else 0
    escalated_kb_count = int(_clean_text_series(escalated_df, "KB Used").ne("").sum()) if "KB Used" in escalated_df.columns else 0

    narrative: list[str] = []
    if created_dates.notna().any():
        narrative.append(
            f"The report covers completed tickets created from {created_dates.min().strftime('%b %d, %Y')} to {created_dates.max().strftime('%b %d, %Y')}."
        )
    narrative.append(
        f"{total_tickets} completed tickets were delivered across {unique_companies} customer accounts during the reporting period."
    )
    if top_issue_row is not None:
        if second_issue_row is not None:
            narrative.append(
                f"Leading request types were {top_issue_row['Issue Type']} ({top_issue_row['Tickets']}/{max(total_tickets, 1)}, {top_issue_row['Share']}%) and {second_issue_row['Issue Type']} ({second_issue_row['Tickets']}/{max(total_tickets, 1)}, {second_issue_row['Share']}%)."
            )
        else:
            narrative.append(
                f"{top_issue_row['Issue Type']} was the most common request type at {top_issue_row['Tickets']}/{max(total_tickets, 1)} ({top_issue_row['Share']}%)."
            )
    if top_source_row is not None:
        narrative.append(
            f"{top_source_row['Source']} was the leading intake channel at {top_source_row['Tickets']}/{max(total_tickets, 1)} ({top_source_row['Share']}%)."
        )
    if top_escalation_row is not None:
        narrative.append(
            f"Escalations were driven most often by {top_escalation_row['Escalation Reason']}, which accounted for {top_escalation_row['Tickets']}/{max(escalated_count, 1)} ({top_escalation_row['Share']}%) of escalated tickets."
        )
    if kb_count:
        narrative.append(f"KB Used was populated on {kb_count}/{max(total_tickets, 1)} tickets ({round(kb_count / max(total_tickets, 1) * 100, 1)}%).")
    if not monthly_trend_table.empty and len(monthly_trend_table) > 1:
        narrative.append(
            f"The CSV supports month-by-month ticket volume review across {len(monthly_trend_table)} months."
        )

    summary_parts: list[str] = [
        f"This service review is based on {total_tickets} completed tickets across {unique_companies} customer accounts."
    ]
    if escalated_count:
        summary_parts.append(f"Escalation reasons were present on {escalation_rate}% of completed tickets.")
    if top_issue_row is not None:
        if second_issue_row is not None:
            summary_parts.append(f"Leading request types were {top_issue_row['Issue Type']} and {second_issue_row['Issue Type']}.")
        else:
            summary_parts.append(f"{top_issue_row['Issue Type']} was the leading request type.")
    if kb_count:
        summary_parts.append(f"KB Used was populated on {kb_count}/{max(total_tickets, 1)} tickets ({round(kb_count / max(total_tickets, 1) * 100, 1)}%).")
    executive_brief_points = summary_parts[:5]
    executive_brief = " ".join(executive_brief_points)

    service_observations: list[str] = []
    if top_escalation_row is not None:
        escalation_line = f"Escalation rate was {escalation_rate}% for the completed-ticket sample."
        escalation_line += f" The leading escalation reason was {top_escalation_row['Escalation Reason']}"
        if second_escalation_row is not None:
            escalation_line += f", followed by {second_escalation_row['Escalation Reason']}"
        escalation_line += "."
        service_observations.append(escalation_line)
    if top_source_row is not None:
        if top_source_row["Share"] >= 60:
            service_observations.append(
                f"{top_source_row['Source']} represented {top_source_row['Share']}% of intake volume, so channel mix may be shaping how work enters the desk."
            )
        elif source_gap_share >= 15:
            service_observations.append(
                f"{top_source_row['Source']} remained the primary intake path, running {source_gap_share} points ahead of the next channel."
            )
    if repeat_patterns:
        repeat_title, repeat_count = repeat_patterns[0]
        service_observations.append(
            f"The title pattern '{repeat_title[:60]}' appeared {repeat_count} times, which may be worth checking for repeat demand or documentation opportunities."
        )
    if top_company_row is not None:
        if company_concentration_share >= 25:
            service_observations.append(
                f"{top_company_row['Company']} represented {top_company_row['Share']}% of completed volume, so account concentration is visible in the current file."
            )
        elif second_company_row is not None:
            service_observations.append(
                f"Customer account coverage was spread across {unique_companies} accounts, led by {top_company_row['Company']} and {second_company_row['Company']}."
            )
    if top_issue_row is not None and top_issue_row["Share"] >= 25:
        service_observations.append(
            f"{top_issue_row['Issue Type']} accounted for {top_issue_row['Share']}% of completed ticket volume."
        )
    if kb_count:
        service_observations.append(
            f"KB Used was populated on {kb_count}/{max(total_tickets, 1)} completed tickets ({round(kb_count / max(total_tickets, 1) * 100, 1)}%)."
        )
    if escalated_kb_count:
        service_observations.append(
            f"Within escalated work, KB Used was populated on {escalated_kb_count}/{max(escalated_count, 1)} tickets ({round(escalated_kb_count / max(escalated_count, 1) * 100, 1)}%)."
        )
    if not unexpected_blank_escalations.empty:
        partner_blank_preview = ", ".join(
            [
                str(value).strip()
                for value in unexpected_blank_escalations.get(reference_column, pd.Series(dtype=str)).head(5).tolist()
                if str(value).strip()
            ]
        )
        detail_text = f" Sample ticket number(s): {partner_blank_preview}." if partner_blank_preview else ""
        service_observations.append(
            f"{len(unexpected_blank_escalations)} partner-escalated ticket(s) do not have an escalation reason recorded.{detail_text}"
        )
    if not monthly_trend_table.empty and len(monthly_trend_table) > 1:
        latest_month = monthly_trend_table.iloc[-1]
        prior_month = monthly_trend_table.iloc[-2]
        change = int(latest_month["Tickets"]) - int(prior_month["Tickets"])
        direction = "up" if change > 0 else "down" if change < 0 else "flat"
        service_observations.append(
            f"Month-over-month ticket volume was {direction} by {abs(change)} tickets from {prior_month['Month']} to {latest_month['Month']}."
        )

    risk_flags: list[str] = []
    if escalation_rate >= 25:
        risk_flags.append(
            f"The CSV shows escalation reasons on {escalation_rate}% of completed tickets, which is a useful governance discussion point."
        )
    if controllable_share >= 30:
        risk_flags.append(
            f"{controllable_share}% of escalated tickets fall into controllable categories, which may support a process or documentation discussion."
        )
    if undefined_share >= 15:
        risk_flags.append(
            f"{undefined_share}% of escalated tickets are classified as Other, which may make trend reporting less precise."
        )
    if repeat_patterns:
        repeat_title, repeat_count = repeat_patterns[0]
        risk_flags.append(
            f"The repeated title pattern '{repeat_title[:50]}' appeared {repeat_count} times in the period."
        )
    if not unexpected_blank_escalations.empty:
        risk_flags.append(
            f"{len(unexpected_blank_escalations)} ticket(s) were routed to an escalated-to-partner queue without an escalation reason."
        )
    if top_company_row is not None and company_concentration_share >= 25:
        risk_flags.append(
            f"{top_company_row['Company']} generated {top_company_row['Share']}% of completed tickets, which may be useful context for account-level review."
        )

    priority_actions: list[str] = []
    if top_escalation_row is not None:
        priority_actions.append(
            f"Discuss the leading escalation reason, {top_escalation_row['Escalation Reason']}, and confirm whether it matches what the partner expected to see this month."
        )
    if top_source_row is not None and top_source_row["Share"] >= 60:
        priority_actions.append(
            f"Confirm whether the current intake mix through {top_source_row['Source']} aligns with how the partner wants requests to enter the desk."
        )
    if repeat_patterns:
        repeat_title, _ = repeat_patterns[0]
        priority_actions.append(
            f"Review the repeated '{repeat_title[:50]}' pattern and decide whether it suggests repeat demand, a known issue, or a documentation gap."
        )
    if top_company_row is not None and company_concentration_share >= 25:
        priority_actions.append(
            f"Use the review to ask whether the volume from {top_company_row['Company']} reflects a temporary event or a broader support pattern."
        )
    if not unexpected_blank_escalations.empty:
        priority_actions.append(
            "Validate partner-escalated tickets with blank escalation reasons so future reviews can trend escalation drivers accurately."
        )
    if undefined_share >= 15:
        priority_actions.append(
            "Consider tightening escalation classification so future monthly reviews can compare reasons more consistently."
        )
    if not priority_actions:
        priority_actions.append(
            "Use this month’s report as a baseline and confirm whether queue mix, escalation volume, and intake patterns are trending in the direction the partner expects."
        )

    data_quality_notes: list[str] = []
    blank_companies = int((_clean_text_series(report_df, "Company") == "").sum())
    if blank_companies:
        data_quality_notes.append(f"{blank_companies} tickets are missing a customer account value.")
    if not unexpected_blank_escalations.empty:
        blank_reference_values = [
            str(value).strip()
            for value in unexpected_blank_escalations.get(reference_column, pd.Series(dtype=str)).head(5).tolist()
            if str(value).strip()
        ]
        preview = f" Sample ticket number(s): {', '.join(blank_reference_values)}." if blank_reference_values else ""
        data_quality_notes.append(
            f"{len(unexpected_blank_escalations)} ticket(s) were in an escalated-to-partner queue without an escalation reason.{preview}"
        )
    excluded_open_tickets = int(len(normalized_df) - len(report_df))
    if excluded_open_tickets > 0:
        data_quality_notes.append(
            f"{excluded_open_tickets} tickets were excluded from the partner workbook because they did not have a completion date."
        )

    return ReportArtifacts(
        report_mode=report_mode,
        normalized_df=normalized_df,
        workbook_df=workbook_df,
        tickets_view=tickets_view,
        escalated_df=escalated_df,
        queue_table=queue_table,
        escalation_table=escalation_table,
        escalation_category_table=escalation_category_table,
        source_table=source_table,
        company_table=company_table,
        issue_type_table=issue_type_table,
        sub_issue_type_table=sub_issue_type_table,
        kb_request_table=kb_request_table,
        monthly_trend_table=monthly_trend_table,
        open_ticket_table=open_ticket_table,
        headline_metrics=headline_metrics,
        narrative=narrative,
        executive_brief=executive_brief,
        executive_brief_points=executive_brief_points,
        service_observations=service_observations,
        priority_actions=priority_actions,
        risk_flags=risk_flags,
        data_quality_notes=data_quality_notes,
    )
