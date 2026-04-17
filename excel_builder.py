from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import xlsxwriter

from config import (
    APP_NAME,
    DEFAULT_REPORT_MODE,
    REPORT_MODE_INTERNAL,
    SHEET_ESCALATIONS,
    SHEET_RAW_DATA,
    SHEET_SUMMARY,
    SHEET_TECHNICIAN_REVIEW,
    SHEET_TICKETS,
    SHEET_TRENDS,
)
from metrics import compute_monthly_breakdown, compute_period_deltas, format_minutes
from utils import build_report_artifacts, build_top_table, ensure_parent_directory, write_dataframe_to_excel_sheet


StatusCallback = Callable[[str], None]


class ExcelBuilderError(Exception):
    """Raised when workbook generation fails."""


@dataclass
class ReportRequest:
    dataframe: pd.DataFrame
    report_title: str
    logo_path: Path
    output_path: Path
    partner_name: str = ""
    date_range: str = ""
    report_mode: str = DEFAULT_REPORT_MODE
    settings: dict | None = None
    ai_results: Any | None = None


class ExcelReportBuilder:
    def __init__(self, status_callback: StatusCallback | None = None) -> None:
        self.status_callback = status_callback or (lambda message: None)

    def build_report(self, request: ReportRequest) -> Path:
        workbook = None
        try:
            self.status_callback("Preparing report data")
            artifacts = build_report_artifacts(
                request.dataframe,
                report_mode=request.report_mode,
                settings=request.settings,
            )

            ensure_parent_directory(request.output_path)
            workbook = xlsxwriter.Workbook(str(request.output_path))
            workbook.set_properties(
                {
                    "title": request.report_title,
                    "subject": "KHD governance service review workbook",
                    "author": APP_NAME,
                    "company": "KHD",
                }
            )

            self.status_callback("Building dashboard sheet")
            dashboard_sheet = workbook.add_worksheet(SHEET_SUMMARY)
            self._build_dashboard_sheet(workbook, dashboard_sheet, request, artifacts)
            dashboard_sheet.set_tab_color("#1D6FA7")

            self.status_callback("Building tickets sheet")
            tickets_sheet = workbook.add_worksheet(SHEET_TICKETS)
            self._build_tickets_sheet(workbook, tickets_sheet, request, artifacts)
            tickets_sheet.set_tab_color("#2F7EAA")

            self.status_callback("Building escalations sheet")
            escalations_sheet = workbook.add_worksheet(SHEET_ESCALATIONS)
            self._build_escalations_sheet(workbook, escalations_sheet, request, artifacts)
            escalations_sheet.set_tab_color("#3A8B70")

            self.status_callback("Building trends sheet")
            trends_sheet = workbook.add_worksheet(SHEET_TRENDS)
            self._build_trends_sheet(workbook, trends_sheet, request, artifacts)
            trends_sheet.set_tab_color("#4B78B6")

            self.status_callback("Building SLA compliance sheet")
            sla_sheet = workbook.add_worksheet("SLA Compliance")
            self._build_sla_sheet(workbook, sla_sheet, request, artifacts)
            sla_sheet.set_tab_color("#D4A830")

            self.status_callback("Writing raw data sheet")
            raw_sheet = workbook.add_worksheet(SHEET_RAW_DATA)
            write_dataframe_to_excel_sheet(raw_sheet, artifacts.workbook_df, workbook, "RawTicketData")
            raw_sheet.hide()

            if request.report_mode == REPORT_MODE_INTERNAL:
                self.status_callback("Building technician review sheet")
                technician_sheet = workbook.add_worksheet(SHEET_TECHNICIAN_REVIEW)
                self._build_technician_review_sheet(workbook, technician_sheet, request, artifacts)
                technician_sheet.hide()

            workbook.close()
            workbook = None
            self.status_callback("Workbook ready")
            return request.output_path
        except Exception as exc:
            raise ExcelBuilderError(f"Failed to build the workbook: {exc}") from exc
        finally:
            if workbook is not None:
                try:
                    workbook.close()
                except Exception:
                    pass

    def _base_formats(self, workbook: xlsxwriter.Workbook) -> dict[str, xlsxwriter.format.Format]:
        return {
            "sheet_bg": workbook.add_format({"bg_color": "#F3F7FB"}),
            "hero": workbook.add_format(
                {
                    "bold": True,
                    "font_color": "#FFFFFF",
                    "font_size": 22,
                    "bg_color": "#103F67",
                    "valign": "vcenter",
                    "left": 1,
                    "left_color": "#103F67",
                    "right": 1,
                    "right_color": "#103F67",
                }
            ),
            "hero_subtitle": workbook.add_format(
                {
                    "font_color": "#D7E7F3",
                    "font_size": 11,
                    "bg_color": "#103F67",
                    "valign": "vcenter",
                    "left": 1,
                    "left_color": "#103F67",
                    "right": 1,
                    "right_color": "#103F67",
                }
            ),
            "hero_panel": workbook.add_format(
                {
                    "bold": True,
                    "font_color": "#FFFFFF",
                    "font_size": 13,
                    "align": "center",
                    "valign": "vcenter",
                    "bg_color": "#1D6FA7",
                    "border": 1,
                    "border_color": "#3B8EC4",
                }
            ),
            "hero_note": workbook.add_format(
                {
                    "font_color": "#47657E",
                    "font_size": 9,
                    "italic": True,
                    "bg_color": "#F5F9FC",
                    "border": 1,
                    "border_color": "#D9E4EE",
                    "valign": "vcenter",
                }
            ),
            "jump_link": workbook.add_format(
                {
                    "bold": True,
                    "font_color": "#103F67",
                    "bg_color": "#EAF2F8",
                    "border": 1,
                    "border_color": "#D8E4EF",
                    "align": "center",
                    "valign": "vcenter",
                }
            ),
            "section_title": workbook.add_format(
                {
                    "bold": True,
                    "font_size": 12,
                    "font_color": "#123D62",
                    "bg_color": "#E8F0F7",
                    "border": 1,
                    "border_color": "#D9E4EE",
                    "valign": "vcenter",
                }
            ),
            "section_title_dark": workbook.add_format(
                {
                    "bold": True,
                    "font_size": 12,
                    "font_color": "#FFFFFF",
                    "bg_color": "#174C79",
                    "border": 1,
                    "border_color": "#174C79",
                    "valign": "vcenter",
                }
            ),
            "metric_label": workbook.add_format(
                {
                    "font_color": "#5D7385",
                    "font_size": 9,
                    "border": 1,
                    "border_color": "#D9E4EE",
                    "bg_color": "#F8FBFD",
                    "align": "center",
                    "valign": "vcenter",
                }
            ),
            "metric_value": workbook.add_format(
                {
                    "font_color": "#123D62",
                    "font_size": 15,
                    "bold": True,
                    "border": 1,
                    "border_color": "#D9E4EE",
                    "bg_color": "#FFFFFF",
                    "align": "center",
                    "valign": "vcenter",
                }
            ),
            "label": workbook.add_format(
                {
                    "font_color": "#4B647A",
                    "font_size": 9,
                    "bold": True,
                    "bg_color": "#F8FBFD",
                    "border": 1,
                    "border_color": "#D9E4EE",
                    "valign": "vcenter",
                }
            ),
            "body": workbook.add_format(
                {
                    "font_color": "#17324D",
                    "bg_color": "#FFFFFF",
                    "border": 1,
                    "border_color": "#E3EBF3",
                    "align": "left",
                    "valign": "vcenter",
                }
            ),
            "body_right": workbook.add_format(
                {
                    "font_color": "#17324D",
                    "bg_color": "#FFFFFF",
                    "border": 1,
                    "border_color": "#E3EBF3",
                    "align": "right",
                    "valign": "vcenter",
                }
            ),
            "body_alt": workbook.add_format(
                {
                    "font_color": "#17324D",
                    "bg_color": "#F7FAFD",
                    "border": 1,
                    "border_color": "#E3EBF3",
                    "text_wrap": True,
                    "valign": "top",
                }
            ),
            "body_wrap": workbook.add_format(
                {
                    "font_color": "#17324D",
                    "bg_color": "#FFFFFF",
                    "border": 1,
                    "border_color": "#E3EBF3",
                    "text_wrap": True,
                    "valign": "top",
                }
            ),
            "percent": workbook.add_format(
                {
                    "font_color": "#17324D",
                    "bg_color": "#FFFFFF",
                    "border": 1,
                    "border_color": "#E3EBF3",
                    "num_format": '0.0"%"',
                    "align": "right",
                    "valign": "vcenter",
                }
            ),
            "note": workbook.add_format(
                {
                    "font_color": "#52697D",
                    "bg_color": "#F7FAFD",
                    "text_wrap": True,
                    "border": 1,
                    "border_color": "#E3EBF3",
                    "valign": "top",
                }
            ),
            "panel_value": workbook.add_format(
                {
                    "font_color": "#17324D",
                    "bg_color": "#FFFFFF",
                    "border": 1,
                    "border_color": "#E3EBF3",
                    "text_wrap": True,
                    "valign": "vcenter",
                }
            ),
        }

    def _configure_sheet_for_presentation(self, sheet) -> None:
        sheet.set_landscape()
        sheet.fit_to_pages(1, 0)
        sheet.set_margins(0.35, 0.35, 0.45, 0.45)
        sheet.repeat_rows(0, 4)

    def _build_dashboard_sheet(self, workbook, sheet, request: ReportRequest, artifacts) -> None:
        formats = self._base_formats(workbook)
        self._configure_sheet_for_presentation(sheet)
        sheet.hide_gridlines(2)
        sheet.set_zoom(90)
        sheet.set_default_row(22)
        sheet.set_tab_color("#1D6FA7")
        for column_ref, width in [
            ("A:A", 18),
            ("B:B", 18),
            ("C:C", 18),
            ("D:D", 18),
            ("E:E", 18),
            ("F:F", 18),
            ("G:G", 18),
            ("H:H", 18),
            ("I:I", 18),
            ("J:J", 18),
            ("K:K", 18),
            ("L:L", 18),
            ("M:M", 18),
            ("N:N", 18),
            ("O:O", 18),
            ("P:P", 18),
        ]:
            sheet.set_column(column_ref, width)
        for row in range(0, 60):
            sheet.set_row(row, None, formats["sheet_bg"])
        sheet.set_row(0, 28)
        sheet.set_row(1, 28)
        sheet.set_row(2, 24)
        sheet.set_row(4, 18)
        sheet.set_row(6, 20)
        sheet.set_row(7, 24)
        sheet.set_row(8, 24)

        self._write_sheet_header(
            sheet,
            request=request,
            panel_title="Monthly Service Review",
            note="This sheet presents the high-level monthly service review prepared for partner-facing governance conversations.",
            formats=formats,
        )
        sheet.write_url("M1", f"internal:'{SHEET_TICKETS}'!A1", formats["jump_link"], string="Tickets Sheet")
        sheet.write_url("N1", f"internal:'{SHEET_ESCALATIONS}'!A1", formats["jump_link"], string="Escalations Sheet")

        metric_map = dict(artifacts.headline_metrics)
        summary_metrics = [
            ("Total Tickets", metric_map.get("Total Tickets", "0")),
            ("Customer Accounts", metric_map.get("Customer Accounts", "0")),
            ("Escalation Rate", metric_map.get("Escalation Rate", "0%")),
            ("Leading Request Type", metric_map.get("Leading Request Type", "N/A")),
            ("Primary Intake Channel", metric_map.get("Primary Intake Channel", "N/A")),
        ]
        metric_row = 6
        for index, (label, value) in enumerate(summary_metrics):
            col = index * 2
            sheet.merge_range(metric_row, col, metric_row, col + 1, label, formats["metric_label"])
            sheet.merge_range(metric_row + 1, col, metric_row + 2, col + 1, value, formats["metric_value"])

        summary_lines = self._build_summary_sheet_lines(artifacts)

        self._write_bullet_block(sheet, 11, 0, 5, "Service Review Summary", summary_lines, formats, title_style="dark")
        self._write_small_table(sheet, 11, 6, "Queue Distribution", artifacts.queue_table.head(6), formats, title_style="dark")
        self._write_small_table(sheet, 11, 9, "Request Type Distribution", artifacts.issue_type_table.head(6), formats)
        self._write_small_table(sheet, 11, 13, "Intake Channel Distribution", artifacts.source_table.head(6), formats)
        self._write_small_table(sheet, 20, 0, "Top Escalation Reasons", artifacts.escalation_table.head(6), formats, title_style="dark")
        self._write_small_table(sheet, 20, 4, "Customer Account Coverage", artifacts.company_table.head(6), formats)
        ai_summary_lines = self._build_ai_summary_lines(request.ai_results)
        if ai_summary_lines:
            self._write_bullet_block(
                sheet,
                29,
                0,
                13,
                "AI-Generated Executive Summary",
                ai_summary_lines,
                formats,
                title_style="dark",
            )

        chart_data = artifacts.queue_table.head(6)[["Queue", "Tickets"]].copy() if not artifacts.queue_table.empty else pd.DataFrame()
        self._write_chart_data(sheet, 40, 16, chart_data)
        sheet.set_column(16, 17, None, None, {"hidden": True})
        if not chart_data.empty:
            self._insert_chart(
                workbook,
                sheet,
                SHEET_SUMMARY,
                "Queue Distribution",
                40,
                16,
                len(chart_data),
                "I20",
                "bar",
                width=470,
                height=255,
            )

    def _build_tickets_sheet(self, workbook, sheet, request: ReportRequest, artifacts) -> None:
        formats = self._base_formats(workbook)
        self._configure_sheet_for_presentation(sheet)
        sheet.hide_gridlines(2)
        sheet.set_zoom(90)
        sheet.set_default_row(22)
        sheet.set_tab_color("#2F7EAA")
        for column_ref, width in [
            ("A:A", 16),
            ("B:B", 18),
            ("C:C", 54),
            ("D:D", 28),
            ("E:E", 28),
            ("F:F", 20),
            ("G:G", 20),
            ("H:H", 24),
            ("I:I", 24),
            ("J:J", 18),
            ("K:K", 18),
            ("L:L", 18),
            ("M:M", 18),
            ("N:N", 18),
            ("O:Z", 16),
        ]:
            sheet.set_column(column_ref, width)

        self._write_sheet_header(
            sheet,
            request=request,
            panel_title="Tickets Review",
            note="Use this sheet to review where completed work landed, which request types led the month, and the ticket detail that supports the governance discussion.",
            formats=formats,
        )

        ticket_story = self._build_ticket_story_lines(artifacts)
        metric_map = dict(artifacts.headline_metrics)
        self._write_bullet_block(sheet, 6, 0, 6, "Ticket Summary", ticket_story, formats, title_style="dark")
        self._write_key_value_panel(
            sheet,
            6,
            8,
            12,
            "Review Context",
            [
                ("Total Tickets", metric_map.get("Total Tickets", "0")),
                ("Customer Accounts", metric_map.get("Customer Accounts", "0")),
                ("Primary Intake", metric_map.get("Primary Intake Channel", "N/A")),
                ("KB Used", self._kb_usage_ratio(artifacts.tickets_view)),
            ],
            formats,
            title_style="dark",
        )

        self._write_small_table(sheet, 14, 0, "Queue Distribution", artifacts.queue_table.head(6), formats, title_style="dark")
        self._write_small_table(sheet, 14, 4, "Request Type Distribution", artifacts.issue_type_table.head(6), formats)
        self._write_small_table(sheet, 14, 8, "Intake Channel Distribution", artifacts.source_table.head(6), formats)
        self._write_small_table(sheet, 14, 12, "Customer Account Coverage", artifacts.company_table.head(6), formats)

        sheet.merge_range("A24:R24", "Ticket Detail", formats["section_title_dark"])
        sheet.merge_range(
            "A25:R25",
            "Review the detailed ticket table below for queue assignment, request type, intake channel, customer account coverage, and ticket-level examples behind the monthly service summary.",
            formats["note"],
        )
        ticket_export_df = self._augment_ticket_export_with_ai(artifacts.tickets_view, request.ai_results)
        write_dataframe_to_excel_sheet(
            sheet,
            ticket_export_df,
            workbook,
            "TicketsView",
            {
                "Ticket Number": 16,
                "Nexus Ticket Number": 18,
                "External Customer Ticket Ref": 20,
                "Title": 42,
                "Company": 24,
                "Parent Account": 24,
                "Created": 20,
                "Complete Date": 20,
                "Issue Type": 18,
                "Sub-Issue Type": 24,
                "Queue": 24,
                "Escalation Reason": 28,
                "Source": 16,
                "KB Used": 24,
                "AI Sentiment": 14,
                "AI Suggested Category": 22,
                "AI Risk Level": 16,
            },
            start_row=26,
        )

    def _build_escalations_sheet(self, workbook, sheet, request: ReportRequest, artifacts) -> None:
        formats = self._base_formats(workbook)
        self._configure_sheet_for_presentation(sheet)
        sheet.hide_gridlines(2)
        sheet.set_zoom(90)
        sheet.set_default_row(22)
        sheet.set_tab_color("#3A8B70")
        for column_ref, width in [
            ("A:A", 20),
            ("B:B", 24),
            ("C:C", 34),
            ("D:D", 14),
            ("E:E", 14),
            ("F:F", 26),
            ("G:G", 22),
            ("H:H", 20),
            ("I:I", 20),
            ("J:J", 18),
            ("K:K", 18),
            ("L:Z", 16),
        ]:
            sheet.set_column(column_ref, width)

        self._write_sheet_header(
            sheet,
            request=request,
            panel_title="Escalation Review",
            note="This sheet shows where escalations concentrated, which categories led the month, how work entered the desk, and which records warrant drill-in during governance review.",
            formats=formats,
        )

        if artifacts.escalated_df.empty:
            placeholder = pd.DataFrame([{"Status": "No escalated tickets were found in the selected file."}])
            write_dataframe_to_excel_sheet(sheet, placeholder, workbook, "EscalationPlaceholder", start_row=6)
            return

        category_summary = (
            artifacts.escalation_category_table.groupby("Category", as_index=False)["Tickets"].sum()
            if not artifacts.escalation_category_table.empty
            else pd.DataFrame(columns=["Category", "Tickets"])
        )
        if not category_summary.empty:
            category_summary["Share"] = (category_summary["Tickets"] / max(len(artifacts.escalated_df), 1) * 100).round(1)
            category_summary = category_summary.sort_values(["Tickets", "Category"], ascending=[False, True], kind="mergesort").reset_index(drop=True)
        escalation_source_table = build_top_table(artifacts.escalated_df, "Source", "Source", limit=6)
        escalation_story = self._build_escalation_story_lines(artifacts, category_summary, escalation_source_table)
        metric_map = dict(artifacts.headline_metrics)

        self._write_bullet_block(sheet, 6, 0, 6, "Escalation Summary", escalation_story, formats, title_style="dark")
        self._write_key_value_panel(
            sheet,
            6,
            8,
            12,
            "Review Context",
            [
                ("Escalated Tickets", metric_map.get("Escalated Tickets", "0")),
                ("Escalation Rate", metric_map.get("Escalation Rate", "0%")),
                ("Lead Escalation Type", str(category_summary.iloc[0]["Category"]) if not category_summary.empty else "N/A"),
                ("Top Escalation Reason", str(artifacts.escalation_table.iloc[0]["Escalation Reason"]) if not artifacts.escalation_table.empty else "N/A"),
                ("KB Used", self._kb_usage_ratio(artifacts.tickets_view)),
            ],
            formats,
            title_style="dark",
        )

        self._write_small_table(sheet, 14, 0, "Escalation Type Summary", category_summary, formats, title_style="dark")
        self._write_small_table(sheet, 14, 4, "Escalation Intake Summary", escalation_source_table, formats)
        self._write_small_table(
            sheet,
            14,
            8,
            "Escalation Reason Breakdown",
            artifacts.escalation_category_table.head(10),
            formats,
            title_style="dark",
        )

        detail_columns = ["Escalation Category", *[column for column in artifacts.escalated_df.columns if column != "Escalation Category"]]
        escalation_detail = artifacts.escalated_df[detail_columns].copy()
        sort_columns = [column for column in ["Escalation Category", "Escalation Reason", "Source", "Company", "Created"] if column in escalation_detail.columns]
        if sort_columns:
            ascending = [True, True, True, True, False][: len(sort_columns)]
            escalation_detail = escalation_detail.sort_values(sort_columns, ascending=ascending, kind="mergesort")

        sheet.merge_range("A24:R24", "Escalation Detail", formats["section_title_dark"])
        sheet.merge_range(
            "A25:R25",
            "Review the detailed escalation table below to drill into category, reason, intake path, and customer account detail behind the monthly escalation summary.",
            formats["note"],
        )
        write_dataframe_to_excel_sheet(
            sheet,
            escalation_detail,
            workbook,
            "EscalatedTickets",
            {
                "Escalation Category": 20,
                "Company": 24,
                "Parent Account": 24,
                "Nexus Ticket Number": 18,
                "External Customer Ticket Ref": 20,
                "Escalation Reason": 28,
                "Title": 44,
                "Ticket Number": 16,
                "Source": 16,
                "Created": 20,
                "Complete Date": 20,
                "Sub-Issue Type": 24,
                "KB Used": 24,
            },
            start_row=26,
        )

    def _build_sla_sheet(self, workbook, sheet, request: ReportRequest, artifacts) -> None:
        formats = self._base_formats(workbook)
        self._configure_sheet_for_presentation(sheet)
        sheet.hide_gridlines(2)
        sheet.set_zoom(90)
        sheet.set_default_row(22)
        for col_ref, width in [("A:A", 18), ("B:B", 14), ("C:C", 16), ("D:D", 16), ("E:E", 18), ("F:F", 20), ("G:G", 18), ("H:Z", 16)]:
            sheet.set_column(col_ref, width)

        self._write_sheet_header(
            sheet,
            request=request,
            panel_title="SLA Compliance",
            note="SLA compliance metrics based on configured targets per priority level.",
            formats=formats,
        )

        sla = artifacts.sla_metrics
        rm = artifacts.resolution_metrics
        from metrics import format_minutes

        metric_map = dict(artifacts.headline_metrics)
        self._write_key_value_panel(
            sheet, 6, 0, 5, "Performance Overview",
            [
                ("Overall SLA Compliance", f"{sla.overall_compliance}%" if sla else "N/A"),
                ("Median Resolution", format_minutes(rm.median_minutes) if rm else "N/A"),
                ("P90 Resolution", format_minutes(rm.p90_minutes) if rm else "N/A"),
                ("First Contact Resolution", metric_map.get("First Contact Resolution", "N/A")),
            ],
            formats,
            title_style="dark",
        )

        # SLA by priority table
        sla_by_priority = sla.by_priority if sla and sla.by_priority is not None and not sla.by_priority.empty else pd.DataFrame()
        self._write_small_table(sheet, 6, 7, "Compliance by Priority", sla_by_priority, formats, title_style="dark")

        sla_targets_table = pd.DataFrame()
        if request.settings:
            sla_targets = request.settings.get("sla_targets", {})
            if sla_targets:
                sla_targets_table = pd.DataFrame(
                    [(priority, target_minutes) for priority, target_minutes in sla_targets.items()],
                    columns=["Priority", "Target (min)"],
                )
        elif sla_by_priority is not None and not sla_by_priority.empty and {"Priority", "Target (min)"}.issubset(sla_by_priority.columns):
            sla_targets_table = sla_by_priority[["Priority", "Target (min)"]].copy()

        self._write_small_table(sheet, 6, 12, "SLA Targets", sla_targets_table, formats)

        # Breaching tickets detail
        breaching = sla.breaching_tickets if sla and sla.breaching_tickets is not None and not sla.breaching_tickets.empty else pd.DataFrame()
        if breaching.empty:
            breaching = pd.DataFrame([{"Status": "All tickets met their SLA targets."}])

        sheet.merge_range("A18:H18", "SLA Breaches", formats["section_title_dark"])
        sheet.merge_range("A19:H19", "Tickets that exceeded configured SLA resolution targets.", formats["note"])
        write_dataframe_to_excel_sheet(
            sheet, breaching, workbook, "SLABreaches",
            {"Ticket Number": 18, "Title": 40, "Priority": 14, "Queue": 20, "Resolution Minutes": 18, "SLA Target (min)": 16, "Status": 44},
            start_row=20,
        )

    def _build_trends_sheet(self, workbook, sheet, request: ReportRequest, artifacts) -> None:
        formats = self._base_formats(workbook)
        self._configure_sheet_for_presentation(sheet)
        sheet.hide_gridlines(2)
        sheet.set_zoom(90)
        sheet.set_default_row(22)
        for col_ref, width in [
            ("A:A", 18),
            ("B:B", 14),
            ("C:C", 16),
            ("D:D", 16),
            ("E:E", 18),
            ("F:F", 14),
            ("G:G", 14),
            ("H:Z", 16),
        ]:
            sheet.set_column(col_ref, width)

        self._write_sheet_header(
            sheet,
            request=request,
            panel_title="Trends",
            note="Month-level comparison export for uploaded reporting periods, including SLA, escalation, and resolution movement.",
            formats=formats,
        )

        settings = request.settings or {}
        monthly_breakdown = compute_monthly_breakdown(
            request.dataframe,
            settings.get("sla_targets"),
            settings.get("sla_queue_overrides"),
        )
        if monthly_breakdown.empty:
            monthly_breakdown = artifacts.monthly_trend_table.copy()

        if monthly_breakdown.empty:
            monthly_breakdown = pd.DataFrame([{"Status": "No monthly trend data was available for this export."}])
            self._write_small_table(sheet, 6, 0, "Trend Status", monthly_breakdown, formats, title_style="dark")
            return

        deltas = compute_period_deltas(monthly_breakdown, period="1M")
        latest_month = monthly_breakdown.iloc[-1]
        overview_pairs = [
            ("Months Included", str(len(monthly_breakdown))),
            ("Latest Month", str(latest_month["Month"])),
            ("Latest Tickets", str(int(latest_month["Tickets"]))),
            ("Latest SLA", f"{float(latest_month['SLA Compliance']):.1f}%"),
            ("Latest Median", format_minutes(float(latest_month["Median Resolution"]))),
        ]
        self._write_key_value_panel(
            sheet,
            6,
            0,
            5,
            "Comparison Overview",
            overview_pairs,
            formats,
            title_style="dark",
        )

        delta_rows: list[dict[str, str]] = []
        metric_labels = {
            "tickets": "Tickets",
            "escalation_rate": "Escalation Rate",
            "sla_compliance": "SLA Compliance",
            "median_resolution": "Median Resolution",
            "fcr_rate": "FCR Rate",
        }
        for key, label in metric_labels.items():
            if key not in deltas:
                continue
            metric_delta = deltas[key]
            current_value = metric_delta["value"]
            prior_value = metric_delta["prior"]
            if key == "median_resolution":
                current_display = format_minutes(float(current_value))
                prior_display = format_minutes(float(prior_value)) if float(prior_value) > 0 else "—"
            elif key == "tickets":
                current_display = f"{int(round(float(current_value)))}"
                prior_display = f"{int(round(float(prior_value)))}"
            else:
                current_display = f"{float(current_value):.1f}%"
                prior_display = f"{float(prior_value):.1f}%"
            delta_rows.append(
                {
                    "Metric": label,
                    "Current": current_display,
                    "Prior": prior_display,
                    "Delta": f"{float(metric_delta['delta']):+.1f}",
                    "Delta %": f"{float(metric_delta['pct']):+.1f}%",
                }
            )

        delta_frame = pd.DataFrame(delta_rows)
        self._write_small_table(sheet, 6, 7, "Latest vs Prior", delta_frame, formats, title_style="dark")

        detail = monthly_breakdown.copy()
        detail["Escalation Rate"] = detail["Escalation Rate"].map(lambda value: f"{float(value):.1f}%")
        detail["SLA Compliance"] = detail["SLA Compliance"].map(lambda value: f"{float(value):.1f}%")
        detail["Median Resolution"] = detail["Median Resolution"].map(lambda value: format_minutes(float(value)))
        detail["FCR Rate"] = detail["FCR Rate"].map(lambda value: f"{float(value):.1f}%")

        sheet.merge_range("A18:G18", "Monthly Comparison Detail", formats["section_title_dark"])
        sheet.merge_range(
            "A19:G19",
            "Trend rows show the monthly ticket baseline used for dashboard deltas and comparison exports.",
            formats["note"],
        )
        write_dataframe_to_excel_sheet(
            sheet,
            detail,
            workbook,
            "MonthlyTrends",
            {
                "Month": 16,
                "Tickets": 12,
                "Escalation Rate": 16,
                "SLA Compliance": 16,
                "Median Resolution": 18,
                "FCR Rate": 14,
                "Noise Count": 14,
            },
            start_row=20,
        )

    def _build_technician_review_sheet(self, workbook, sheet, request: ReportRequest, artifacts) -> None:
        formats = self._base_formats(workbook)
        self._configure_sheet_for_presentation(sheet)
        sheet.hide_gridlines(2)
        sheet.set_zoom(90)
        sheet.set_default_row(22)
        sheet.set_tab_color("#7B5AA6")
        for column_ref, width in [
            ("A:A", 20),
            ("B:B", 12),
            ("C:C", 14),
            ("D:D", 18),
            ("E:E", 18),
            ("F:F", 12),
            ("G:G", 14),
            ("H:H", 10),
            ("I:I", 12),
            ("J:J", 18),
            ("K:K", 18),
            ("L:L", 16),
            ("M:Z", 16),
        ]:
            sheet.set_column(column_ref, width)

        self._write_sheet_header(
            sheet,
            request=request,
            panel_title="Technician Review",
            note="Internal-only QA sheet for technician scorecards, after-hours diagnostics, and repeat-contact follow-up.",
            formats=formats,
        )

        after_hours = artifacts.after_hours_metrics
        noise = artifacts.noise_metrics
        metric_map = dict(artifacts.headline_metrics)
        self._write_key_value_panel(
            sheet,
            6,
            0,
            5,
            "Internal Metrics",
            [
                ("Median Resolution", metric_map.get("Median Resolution", "N/A")),
                ("SLA Compliance", metric_map.get("SLA Compliance", "0%")),
                ("First Contact Resolution", metric_map.get("First Contact Resolution", "0%")),
                ("After-Hours Rate", f"{getattr(after_hours, 'after_hours_rate', 0.0)}%"),
                ("Noise Rate", f"{getattr(noise, 'noise_rate', 0.0)}%"),
            ],
            formats,
            title_style="dark",
        )

        after_hours_table = pd.DataFrame(
            [
                ("After-Hours Tickets", getattr(after_hours, "total_after_hours", 0)),
                ("Weekday After-Hours", getattr(after_hours, "weekday_after_hours", 0)),
                ("Weekend Tickets", getattr(after_hours, "weekend_count", 0)),
            ],
            columns=["Metric", "Value"],
        )
        noise_table = pd.DataFrame(
            [
                ("Spam Tickets", getattr(noise, "spam_count", 0)),
                ("Sync Errors", getattr(noise, "sync_error_count", 0)),
                ("Total Noise", getattr(noise, "total_noise", 0)),
            ],
            columns=["Metric", "Value"],
        )
        repeat_contacts = artifacts.repeat_contacts if artifacts.repeat_contacts is not None else pd.DataFrame()
        self._write_small_table(sheet, 6, 7, "After-Hours Summary", after_hours_table, formats, title_style="dark")
        self._write_small_table(sheet, 6, 10, "Noise Diagnostics", noise_table, formats)
        self._write_small_table(sheet, 6, 13, "Repeat Contacts", repeat_contacts.head(6), formats)

        scorecards = artifacts.technician_scorecards if artifacts.technician_scorecards is not None else pd.DataFrame()
        if scorecards.empty:
            scorecards = pd.DataFrame([{"Status": "No technician scorecards were generated for this report."}])
        sheet.merge_range("A16:J16", "Technician Scorecards", formats["section_title_dark"])
        sheet.merge_range(
            "A17:J17",
            "Use this hidden internal sheet for coaching, escalation review, and follow-up before partner distribution.",
            formats["note"],
        )
        write_dataframe_to_excel_sheet(
            sheet,
            scorecards,
            workbook,
            "TechnicianScorecards",
            {
                "Technician": 20,
                "Tickets": 12,
                "Avg Hours": 14,
                "Avg Resolution (min)": 18,
                "Median Resolution (min)": 18,
                "Escalated": 12,
                "Escalation Rate": 14,
                "FCR": 10,
                "FCR Rate": 12,
                "Status": 44,
            },
            start_row=18,
        )

    def _write_sheet_header(self, sheet, request: ReportRequest, panel_title: str, note: str, formats) -> None:
        subtitle_parts = [part for part in [request.partner_name.strip(), request.date_range.strip()] if part]
        subtitle = " | ".join(subtitle_parts) if subtitle_parts else "Governance service review"

        sheet.merge_range("A1:H2", request.report_title, formats["hero"])
        sheet.merge_range("A3:H3", subtitle, formats["hero_subtitle"])
        sheet.merge_range("I1:L2", panel_title, formats["hero_panel"])
        sheet.merge_range("A5:L5", note, formats["hero_note"])
        sheet.set_row(4, 28)
        if request.logo_path.exists():
            sheet.insert_image("I3", str(request.logo_path), {"x_scale": 0.72, "y_scale": 0.72, "object_position": 1})

    def _write_key_value_panel(
        self,
        sheet,
        start_row: int,
        start_col: int,
        end_col: int,
        title: str,
        items: list[tuple[str, str]],
        formats,
        title_style: str = "standard",
    ) -> None:
        title_format = formats["section_title_dark"] if title_style == "dark" else formats["section_title"]
        sheet.merge_range(start_row, start_col, start_row, end_col, title, title_format)
        for row_offset, (label, value) in enumerate(items, start=1):
            sheet.write(start_row + row_offset, start_col, label, formats["label"])
            sheet.merge_range(start_row + row_offset, start_col + 1, start_row + row_offset, end_col, value, formats["panel_value"])
            sheet.set_row(start_row + row_offset, 24)

    def _build_ticket_story_lines(self, artifacts) -> list[str]:
        lines: list[str] = []
        metric_map = dict(artifacts.headline_metrics)
        lines.append(
            f"The completed-ticket sample includes {metric_map.get('Total Tickets', '0')} tickets across {metric_map.get('Customer Accounts', '0')} customer accounts."
        )
        request_line = self._leading_request_types_line(artifacts.issue_type_table, int(metric_map.get("Total Tickets", "0") or 0))
        if request_line:
            lines.append(request_line)
        if not artifacts.source_table.empty:
            top_source = artifacts.source_table.iloc[0]
            lines.append(f"{top_source['Source']} was the primary intake channel at {self._ratio_text(int(top_source['Tickets']), int(metric_map.get('Total Tickets', '0') or 0), float(top_source['Share']))}.")
        kb_line = self._kb_usage_line(artifacts.tickets_view, "KB Used was populated on")
        if kb_line:
            lines.append(kb_line)
        return lines or ["No ticket-level summary was generated from the completed-ticket sample."]

    def _build_escalation_story_lines(self, artifacts, category_summary: pd.DataFrame, source_table: pd.DataFrame) -> list[str]:
        lines: list[str] = []
        if not artifacts.headline_metrics:
            return ["No escalation summary was generated from the completed-ticket sample."]
        escalation_rate = next((value for label, value in artifacts.headline_metrics if label == "Escalation Rate"), "0%")
        escalated_tickets = next((value for label, value in artifacts.headline_metrics if label == "Escalated Tickets"), "0")
        lines.append(f"{escalated_tickets} completed tickets carried an escalation reason, representing {escalation_rate} of the monthly ticket sample.")
        if not category_summary.empty:
            top_category = category_summary.iloc[0]
            lines.append(f"{top_category['Category']} was the largest escalation type at {int(top_category['Tickets'])}/{max(int(escalated_tickets or 0), 1)} ({top_category['Share']}%) of escalated tickets.")
        if not artifacts.escalation_table.empty:
            top_reason = artifacts.escalation_table.iloc[0]
            lines.append(f"{top_reason['Escalation Reason']} was the top escalation reason at {int(top_reason['Tickets'])}/{max(int(escalated_tickets or 0), 1)} ({top_reason['Share']}%) of escalated tickets.")
        if not source_table.empty:
            top_source = source_table.iloc[0]
            lines.append(f"{top_source['Source']} was the leading intake path for escalated work at {self._ratio_text(int(top_source['Tickets']), int(escalated_tickets or 0), float(top_source['Share']))}.")
        kb_line = self._kb_usage_line(artifacts.tickets_view, "KB Used was populated on")
        if kb_line:
            lines.append(kb_line)
        return lines or ["No escalation-level summary was generated from the completed-ticket sample."]

    def _build_ai_summary_lines(self, ai_results: Any | None) -> list[str]:
        summary = str(getattr(ai_results, "executive_summary", "") or "").strip()
        if not summary:
            return []

        chunks = [part.strip() for part in summary.replace("\n", " ").split(". ") if part.strip()]
        lines: list[str] = []
        for chunk in chunks[:4]:
            normalized = chunk if chunk.endswith(".") else f"{chunk}."
            lines.append(normalized)

        if not lines:
            lines.append(summary[:220])
        return lines

    def _augment_ticket_export_with_ai(self, ticket_df: pd.DataFrame, ai_results: Any | None) -> pd.DataFrame:
        export_df = ticket_df.copy()
        if export_df.empty or ai_results is None or "Ticket Number" not in export_df.columns:
            return export_df

        def normalize_ticket_id(value: object) -> str:
            text = str(value or "").strip()
            if text.endswith(".0") and text[:-2].isdigit():
                return text[:-2]
            return text

        sentiment_map = {
            normalize_ticket_id(getattr(result, "ticket_id", "")): getattr(result, "sentiment", "")
            for result in getattr(ai_results, "sentiment", []) or []
        }
        category_map = {
            normalize_ticket_id(getattr(result, "ticket_id", "")): getattr(result, "suggested_issue_type", "")
            for result in getattr(ai_results, "category_suggestions", []) or []
        }
        ticket_ids = export_df["Ticket Number"].apply(normalize_ticket_id)
        export_df["AI Sentiment"] = ticket_ids.map(sentiment_map).fillna("")
        export_df["AI Suggested Category"] = ticket_ids.map(category_map).fillna("")
        return export_df

    def _write_bullet_block(
        self,
        sheet,
        start_row: int,
        start_col: int,
        width: int,
        title: str,
        lines: list[str],
        formats,
        alt: bool = False,
        title_style: str = "standard",
    ) -> None:
        end_col = start_col + width
        body_format = formats["body_alt"] if alt else formats["body_wrap"]
        title_format = formats["section_title_dark"] if title_style == "dark" else formats["section_title"]
        sheet.merge_range(start_row, start_col, start_row, end_col, title, title_format)
        bullet_lines = lines[:5] if lines else ["No narrative available."]
        for offset, line in enumerate(bullet_lines, start=1):
            sheet.merge_range(start_row + offset, start_col, start_row + offset, end_col, f"- {line}", body_format)
            sheet.set_row(start_row + offset, 32)

    def _write_small_table(self, sheet, start_row: int, start_col: int, title: str, dataframe: pd.DataFrame, formats, title_style: str = "standard") -> None:
        end_col = start_col + max(len(dataframe.columns), 1) - 1
        title_format = formats["section_title_dark"] if title_style == "dark" else formats["section_title"]
        if start_col == end_col:
            sheet.write(start_row, start_col, title, title_format)
        else:
            sheet.merge_range(start_row, start_col, start_row, end_col, title, title_format)

        if dataframe.empty:
            if start_col == end_col:
                sheet.write(start_row + 1, start_col, "No data available", formats["note"])
            else:
                sheet.merge_range(start_row + 1, start_col, start_row + 1, end_col, "No data available", formats["note"])
            return

        headers = list(dataframe.columns)
        for col_offset, header in enumerate(headers):
            sheet.write(start_row + 1, start_col + col_offset, header, formats["label"])
            sample_values = [str(header)] + [str(value) for value in dataframe.iloc[:, col_offset].tolist()]
            max_len = max(len(value) for value in sample_values)
            if header == "Queue":
                preferred_width = min(max(max_len + 3, 24), 34)
            elif header in {"Issue Type", "Escalation Reason", "Company", "Category", "Sub-Issue Type"}:
                preferred_width = min(max(max_len + 3, 22), 34)
            elif header == "Tickets":
                preferred_width = max(max_len + 2, 10)
            elif header == "Share":
                preferred_width = max(max_len + 2, 10)
            else:
                preferred_width = min(max(max_len + 2, 14), 20)
            sheet.set_column(start_col + col_offset, start_col + col_offset, preferred_width)

        for row_offset, row in enumerate(dataframe.itertuples(index=False, name=None), start=2):
            row_height = 20
            for col_offset, value in enumerate(row):
                header = headers[col_offset]
                if header == "Share":
                    cell_format = formats["percent"]
                elif header == "Tickets":
                    cell_format = formats["body_right"]
                elif header in {"Queue", "Issue Type", "Escalation Reason", "Company", "Category", "Sub-Issue Type"}:
                    cell_format = formats["body_wrap"]
                    row_height = 34
                else:
                    cell_format = formats["body"]
                sheet.write(start_row + row_offset, start_col + col_offset, value, cell_format)
            sheet.set_row(start_row + row_offset, row_height)

    def _unique_lines(self, lines: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for line in lines:
            cleaned = str(line).strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                ordered.append(cleaned)
        return ordered

    def _ratio_text(self, count: int, total: int, share: float | None = None) -> str:
        safe_total = max(int(total), 1)
        pct = share if share is not None else round(count / safe_total * 100, 1)
        return f"{count}/{safe_total} ({pct:.1f}%)"

    def _kb_usage_count(self, dataframe: pd.DataFrame) -> int:
        if "KB Used" not in dataframe.columns or dataframe.empty:
            return 0
        return int(dataframe["KB Used"].fillna("").astype(str).str.strip().ne("").sum())

    def _kb_usage_ratio(self, dataframe: pd.DataFrame) -> str:
        if dataframe.empty:
            return "0/0 (0.0%)"
        kb_count = self._kb_usage_count(dataframe)
        return self._ratio_text(kb_count, len(dataframe))

    def _kb_usage_line(self, dataframe: pd.DataFrame, prefix: str) -> str:
        if dataframe.empty:
            return ""
        kb_count = self._kb_usage_count(dataframe)
        return f"{prefix} {self._ratio_text(kb_count, len(dataframe))} tickets."

    def _leading_request_types_line(self, issue_type_table: pd.DataFrame, total_tickets: int) -> str:
        if issue_type_table.empty or total_tickets <= 0:
            return ""
        top_issue = issue_type_table.iloc[0]
        if len(issue_type_table) > 1:
            second_issue = issue_type_table.iloc[1]
            return (
                "Leading request types were "
                f"{top_issue['Issue Type']} at {self._ratio_text(int(top_issue['Tickets']), total_tickets, float(top_issue['Share']))} "
                f"and {second_issue['Issue Type']} at {self._ratio_text(int(second_issue['Tickets']), total_tickets, float(second_issue['Share']))}."
            )
        return (
            f"{top_issue['Issue Type']} was the leading request type at "
            f"{self._ratio_text(int(top_issue['Tickets']), total_tickets, float(top_issue['Share']))}."
        )

    def _build_summary_sheet_lines(self, artifacts) -> list[str]:
        metric_map = dict(artifacts.headline_metrics)
        total_tickets = int(metric_map.get("Total Tickets", "0") or 0)
        lines = [
            f"This service review is based on {total_tickets} completed tickets across {metric_map.get('Customer Accounts', '0')} customer accounts.",
            f"Escalation reasons were present on {metric_map.get('Escalation Rate', '0%')} of completed tickets.",
        ]
        request_line = self._leading_request_types_line(artifacts.issue_type_table, total_tickets)
        if request_line:
            lines.append(request_line)
        if not artifacts.source_table.empty:
            top_source = artifacts.source_table.iloc[0]
            lines.append(
                f"{top_source['Source']} was the primary intake channel at {self._ratio_text(int(top_source['Tickets']), total_tickets, float(top_source['Share']))}."
            )
        if not artifacts.escalation_table.empty:
            top_reason = artifacts.escalation_table.iloc[0]
            lines.append(
                f"Top escalation reason was {top_reason['Escalation Reason']} at {self._ratio_text(int(top_reason['Tickets']), len(artifacts.escalated_df), float(top_reason['Share']))} of escalated tickets."
            )
        kb_line = self._kb_usage_line(artifacts.tickets_view, "KB Used was populated on")
        if kb_line:
            lines.append(kb_line)
        return self._unique_lines(lines[:5])

    def _write_chart_data(self, sheet, start_row: int, start_col: int, dataframe: pd.DataFrame) -> None:
        if dataframe.empty:
            return
        for col_offset, column_name in enumerate(dataframe.columns):
            sheet.write(start_row, start_col + col_offset, column_name)
        for row_offset, row in enumerate(dataframe.itertuples(index=False, name=None), start=1):
            for col_offset, value in enumerate(row):
                sheet.write(start_row + row_offset, start_col + col_offset, value)

    def _insert_chart(
        self,
        workbook,
        sheet,
        sheet_name: str,
        title: str,
        data_row: int,
        data_col: int,
        data_count: int,
        anchor_cell: str,
        chart_type: str,
        series_color: str = "#2F7EAA",
        width: int = 500,
        height: int = 255,
    ) -> None:
        if data_count <= 0:
            return
        chart = workbook.add_chart({"type": chart_type})
        first_data_row = data_row + 1
        last_data_row = data_row + data_count
        chart.add_series(
            {
                "categories": [sheet_name, first_data_row, data_col, last_data_row, data_col],
                "values": [sheet_name, first_data_row, data_col + 1, last_data_row, data_col + 1],
                "fill": {"color": series_color},
                "border": {"color": series_color},
                "data_labels": {"value": True},
            }
        )
        chart.set_title({"name": title})
        chart.set_legend({"none": True})
        chart.set_plotarea({"fill": {"color": "#FFFFFF"}, "border": {"color": "#D9E4EE"}})
        chart.set_chartarea({"fill": {"color": "#FFFFFF"}, "border": {"none": True}})
        chart.set_x_axis({"major_gridlines": {"visible": False}})
        if chart_type == "bar":
            chart.set_y_axis({"reverse": True})
        chart.set_size({"width": width, "height": height})
        sheet.insert_chart(anchor_cell, chart)
