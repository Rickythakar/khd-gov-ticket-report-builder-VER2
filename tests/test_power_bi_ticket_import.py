from __future__ import annotations

import importlib.util
import sys
import unittest
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from upload_validation import build_unsupported_upload_message, validate_supported_upload_schema
from validators import validate_and_prepare_dataframe


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_MODULE_PATH = REPO_ROOT / "server.py"
SAMPLE_CSV = REPO_ROOT / "sample_input.csv"


def build_power_bi_frame(*, created_timestamp: str, created_date: str, created_hour: int, khd_ticket_number: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "My Value": "Laptop Setup",
                "KHD Ticket Number": khd_ticket_number,
                "MSP Ticket Number": "MSP-9001",
                "Partner": "Acme Holdings",
                "Timezone": "America/New_York",
                "Client": "Acme Manufacturing",
                "Source": "Phone",
                "Create Timestamp": created_timestamp,
                "Created Date": created_date,
                "Created Hour": created_hour,
                "Task Status": "Open",
                "Queue Name": "Service Desk",
                "Take Back": "No",
                "Take Back Count": 0,
                "Issue Type": "Request",
                "Sub Issue Type": "Laptop",
                "Pickup SLO Status": "Within SLO",
            }
        ]
    )


def build_autotask_created_ticket_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Task Number": "TASK-2001",
                "Task ID": "2001",
                "Parent Task Number": "MSP-2001",
                "Parent Account Name": "Acme Holdings",
                "Account Timezone": "America/New_York",
                "Account Country": "US",
                "Account Name": "Acme Manufacturing",
                "Flag Type": "",
                "Assignee Name": "Analyst One",
                "Source": "Phone",
                "Create Timestamp": "2026-03-18 09:15:00",
                "Created Date": "2026-03-18",
                "Created Hour": 9,
                "Age Bracket": "0-1 days",
                "Task Status": "Open",
                "First Queue Name": "Triage",
                "Queue Name": "Service Desk",
                "Escalation Events": 0,
                "Tickets Classification": "Operational",
                "Take Back Event": "No",
                "Take Back Count": 0,
                "Issue Type": "Request",
                "Sub Issue Type": "Laptop",
                "Reopen Count": 0,
                "Pickup Max Date": "",
                "Pickup Time (Mins)": 14,
                "Pickup SLO Status": "Within SLO",
                "L1Res Max Date": "",
                "L1Res Time (Mins)": "",
                "L1Res SLO Status": "",
                "L2Res Max Date": "",
                "L2Res Time (Mins)": "",
                "L2RES SLO Status": "",
            }
        ]
    )


class PowerBiTicketImportTests(unittest.TestCase):
    def load_server_module(self, module_name: str):
        spec = importlib.util.spec_from_file_location(module_name, SERVER_MODULE_PATH)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    def workbook_sheet_names(self, workbook_bytes: bytes) -> list[str]:
        with zipfile.ZipFile(BytesIO(workbook_bytes)) as workbook_zip:
            workbook_xml = ET.fromstring(workbook_zip.read("xl/workbook.xml"))
        namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        return [sheet.attrib["name"] for sheet in workbook_xml.findall("main:sheets/main:sheet", namespace)]

    def test_valid_power_bi_upload_is_accepted(self) -> None:
        server = self.load_server_module("power_bi_ticket_server_valid_upload")
        client = TestClient(server.app)
        frame = build_power_bi_frame(
            created_timestamp="2026-03-18 09:15:00",
            created_date="2026-03-18",
            created_hour=9,
            khd_ticket_number="KHD-1001",
        )

        response = client.post(
            "/upload",
            files=[("file", ("powerbi_ticket_export.csv", frame.to_csv(index=False).encode("utf-8"), "text/csv"))],
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(server._state["prepared_df"]["Ticket Number"].iloc[0], "KHD-1001")
        self.assertIn("powerbi_ticket_export.csv", server._state["csv_names"])
        self.assertEqual(server._state["source_label"], "Power BI ticket export")

    def test_power_bi_export_is_transformed_into_canonical_schema(self) -> None:
        raw_df = build_power_bi_frame(
            created_timestamp="2026-03-18 09:15:00",
            created_date="2026-03-18",
            created_hour=9,
            khd_ticket_number="KHD-1002",
        )

        schema_result = validate_supported_upload_schema(raw_df)
        self.assertTrue(schema_result.is_supported)
        self.assertEqual(schema_result.accepted_schema, "power_bi_ticket_export")

        result = validate_and_prepare_dataframe(raw_df)
        prepared = result.dataframe

        self.assertEqual(result.source_schema, "power_bi_ticket_export")
        self.assertEqual(prepared.loc[0, "Ticket Number"], "KHD-1002")
        self.assertEqual(prepared.loc[0, "Nexus Ticket Number"], "MSP-9001")
        self.assertEqual(prepared.loc[0, "Title"], "Laptop Setup")
        self.assertEqual(prepared.loc[0, "Company"], "Acme Manufacturing")
        self.assertEqual(prepared.loc[0, "Parent Account"], "Acme Holdings")
        self.assertEqual(prepared.loc[0, "Queue"], "Service Desk")
        self.assertEqual(prepared.loc[0, "Status"], "Open")
        self.assertEqual(prepared.loc[0, "Sub-Issue Type"], "Laptop")
        self.assertEqual(prepared.loc[0, "Escalation Reason"], "")
        self.assertTrue(pd.notna(prepared.loc[0, "Created"]))
        self.assertTrue(pd.isna(prepared.loc[0, "Complete Date"]))
        self.assertTrue(any("completion timestamp" in note.lower() for note in result.normalization_notes))
        self.assertTrue(any("completion-based metrics" in note.lower() for note in result.normalization_notes))

    def test_missing_power_bi_required_columns_are_rejected_cleanly(self) -> None:
        raw_df = build_power_bi_frame(
            created_timestamp="2026-03-18 09:15:00",
            created_date="2026-03-18",
            created_hour=9,
            khd_ticket_number="KHD-1003",
        ).drop(columns=["Queue Name", "Create Timestamp"])

        schema_result = validate_supported_upload_schema(raw_df)

        self.assertFalse(schema_result.is_supported)
        self.assertIn("Queue Name", schema_result.schema_candidates["power_bi_ticket_export"])
        self.assertIn("Create Timestamp", schema_result.schema_candidates["power_bi_ticket_export"])
        self.assertIn("Unsupported upload format", build_unsupported_upload_message(schema_result))

    def test_autotask_created_ticket_column_set_is_detected_before_power_bi(self) -> None:
        raw_df = build_autotask_created_ticket_frame()

        schema_result = validate_supported_upload_schema(raw_df)
        self.assertTrue(schema_result.is_supported)
        self.assertEqual(schema_result.accepted_schema, "canonical_created_ticket")

        result = validate_and_prepare_dataframe(raw_df)
        prepared = result.dataframe

        self.assertEqual(result.source_schema, "canonical_created_ticket")
        self.assertEqual(prepared.loc[0, "Ticket Number"], "TASK-2001")
        self.assertEqual(prepared.loc[0, "Nexus Ticket Number"], "MSP-2001")
        self.assertEqual(prepared.loc[0, "Company"], "Acme Manufacturing")
        self.assertEqual(prepared.loc[0, "Parent Account"], "Acme Holdings")
        self.assertEqual(prepared.loc[0, "Queue"], "Service Desk")
        self.assertEqual(prepared.loc[0, "Status"], "Open")
        self.assertTrue(pd.notna(prepared.loc[0, "Created"]))

    def test_monthly_mode_works_for_transformed_power_bi_uploads(self) -> None:
        server = self.load_server_module("power_bi_ticket_server_monthly_mode")
        client = TestClient(server.app)
        february = build_power_bi_frame(
            created_timestamp="2026-02-12 08:00:00",
            created_date="2026-02-12",
            created_hour=8,
            khd_ticket_number="KHD-2001",
        )
        march = build_power_bi_frame(
            created_timestamp="2026-03-14 11:30:00",
            created_date="2026-03-14",
            created_hour=11,
            khd_ticket_number="KHD-2002",
        )

        upload = client.post(
            "/upload",
            files=[
                ("file", ("powerbi_feb.csv", february.to_csv(index=False).encode("utf-8"), "text/csv")),
                ("file", ("powerbi_mar.csv", march.to_csv(index=False).encode("utf-8"), "text/csv")),
            ],
        )

        self.assertEqual(upload.status_code, 200)

        workbook_response = client.get("/export/workbook?monthly_ticket_report_mode=1")

        self.assertEqual(workbook_response.status_code, 200)
        sheet_names = self.workbook_sheet_names(workbook_response.content)
        self.assertEqual(sheet_names[0], "Monthly Snapshot")
        self.assertIn("Feb 2026 Summary", sheet_names)
        self.assertIn("Mar 2026 Summary", sheet_names)

    def test_dashboard_shows_detected_source_and_limitation_banner_for_power_bi_uploads(self) -> None:
        server = self.load_server_module("power_bi_ticket_server_banner")
        client = TestClient(server.app)
        frame = build_power_bi_frame(
            created_timestamp="2026-03-18 09:15:00",
            created_date="2026-03-18",
            created_hour=9,
            khd_ticket_number="KHD-3001",
        )

        upload = client.post(
            "/upload",
            files=[("file", ("powerbi_ticket_export.csv", frame.to_csv(index=False).encode("utf-8"), "text/csv"))],
        )

        self.assertEqual(upload.status_code, 200)
        page = client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Detected source: Power BI ticket export", page.text)
        self.assertIn("completion timestamp is not present in the source export", page.text.lower())

    def test_dashboard_shows_autotask_source_label_for_canonical_uploads(self) -> None:
        server = self.load_server_module("power_bi_ticket_server_autotask_label")
        client = TestClient(server.app)

        upload = client.post(
            "/upload",
            files=[("file", (SAMPLE_CSV.name, SAMPLE_CSV.read_bytes(), "text/csv"))],
        )

        self.assertEqual(upload.status_code, 200)
        page = client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Detected source: Autotask created-ticket export", page.text)


if __name__ == "__main__":
    unittest.main()
