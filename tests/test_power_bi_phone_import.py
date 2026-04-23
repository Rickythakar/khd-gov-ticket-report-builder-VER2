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

from phone_validators import validate_and_prepare_phone_dataframe
from upload_validation import validate_supported_upload_schema


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_MODULE_PATH = REPO_ROOT / "server.py"
SAMPLE_TICKET_CSV = REPO_ROOT / "sample_input.csv"


def build_phone_frame(
    *,
    call_id: str = "CALL-1001",
    call_timestamp: str = "2026-04-02 09:14:00",
    disposition: str = "Answered",
    answered: object = 1,
    abandoned: object = 0,
    wait_seconds: object = 42,
    handle_minutes: object = 5.5,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Call ID": call_id,
                "Call Timestamp": call_timestamp,
                "Campaign": "Inbound Support",
                "Disposition": disposition,
                "Skill": "Service Desk",
                "Call Type": "Inbound",
                "DNIS": "18005551212",
                "DNIS Country": "US",
                "Reseller": "Acme Holdings",
                "Client": "Acme Manufacturing",
                "Abandoned": abandoned,
                "Answered": answered,
                "Queue Wait Time (Sec)": wait_seconds,
                "Speed of Answer (Sec)": 12,
                "Hold Time (Sec)": 18,
                "Handle Time (Mins)": handle_minutes,
                "Out of Compliance Overage": "0-30 sec",
                "Service Level": 94.2,
                "Service Level Category": "Within Target",
            }
        ]
    )


class PowerBiPhoneImportTests(unittest.TestCase):
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

    def test_valid_phone_schema_is_detected_and_normalized(self) -> None:
        raw_df = build_phone_frame()

        schema_result = validate_supported_upload_schema(raw_df)
        self.assertTrue(schema_result.is_supported)
        self.assertEqual(schema_result.accepted_schema, "powerbi_phone_export")

        result = validate_and_prepare_phone_dataframe(raw_df)
        prepared = result.dataframe

        self.assertEqual(result.source_schema, "powerbi_phone_export")
        self.assertEqual(result.source_label, "Power BI phone export")
        self.assertEqual(prepared.loc[0, "Call ID"], "CALL-1001")
        self.assertEqual(prepared.loc[0, "Queue"], "Service Desk")
        self.assertEqual(prepared.loc[0, "Direction"], "Inbound")
        self.assertEqual(prepared.loc[0, "Partner"], "Acme Holdings")
        self.assertEqual(prepared.loc[0, "Client"], "Acme Manufacturing")
        self.assertEqual(prepared.loc[0, "Phone Number"], "18005551212")
        self.assertEqual(prepared.loc[0, "Phone Region"], "US")
        self.assertEqual(prepared.loc[0, "Answered Flag"], 1)
        self.assertEqual(prepared.loc[0, "Abandoned Flag"], 0)
        self.assertEqual(float(prepared.loc[0, "Wait Seconds"]), 42.0)
        self.assertEqual(float(prepared.loc[0, "Handle Minutes"]), 5.5)
        self.assertEqual(float(prepared.loc[0, "Handle Seconds"]), 330.0)
        self.assertEqual(int(prepared.loc[0, "Call Hour"]), 9)
        self.assertTrue(pd.notna(prepared.loc[0, "Call Date"]))
        self.assertTrue(any("call-event based" in note.lower() for note in result.normalization_notes))

    def test_phone_only_upload_succeeds_and_exposes_phone_export_surface(self) -> None:
        server = self.load_server_module("power_bi_phone_server_phone_only")
        client = TestClient(server.app)
        frame = build_phone_frame()

        response = client.post(
            "/upload",
            files=[("file", ("powerbi_phone_export.csv", frame.to_csv(index=False).encode("utf-8"), "text/csv"))],
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(server._state["phone_df"])
        self.assertIsNotNone(server._state["phone_artifacts"])
        self.assertIsNone(server._state["prepared_df"])
        self.assertIsNone(server._state["artifacts"])

        page = client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Phone Data Loaded", page.text)
        self.assertIn("Detected source: Power BI phone export", page.text)
        self.assertNotIn("EXPORT TICKET WORKBOOK", page.text)
        self.assertIn("package phone metrics inside the main ticket workbook", page.text)

    def test_bad_phone_upload_fails_gracefully(self) -> None:
        server = self.load_server_module("power_bi_phone_server_invalid")
        client = TestClient(server.app)
        invalid_frame = pd.DataFrame(
            [
                {
                    "Call ID": "CALL-404",
                    "Call Timestamp": "2026-04-02 09:14:00",
                    "Disposition": "Answered",
                    "Answered": 1,
                    "Abandoned": 0,
                }
            ]
        )

        response = client.post(
            "/upload",
            files=[("file", ("bad_phone.csv", invalid_frame.to_csv(index=False).encode("utf-8"), "text/csv"))],
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported upload format", response.json()["message"])

        page = client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("[ERR]", page.text)
        self.assertIn("supported ticket export or phone metrics export", page.text)

    def test_ticket_and_phone_states_can_coexist_and_export_with_optional_phone_metrics_tab(self) -> None:
        server = self.load_server_module("power_bi_phone_server_coexist")
        client = TestClient(server.app)

        ticket_upload = client.post(
            "/upload",
            files=[("file", (SAMPLE_TICKET_CSV.name, SAMPLE_TICKET_CSV.read_bytes(), "text/csv"))],
        )
        self.assertEqual(ticket_upload.status_code, 200)

        phone_upload = client.post(
            "/upload",
            files=[("file", ("powerbi_phone_export.csv", build_phone_frame().to_csv(index=False).encode("utf-8"), "text/csv"))],
        )
        self.assertEqual(phone_upload.status_code, 200)

        self.assertIsNotNone(server._state["prepared_df"])
        self.assertIsNotNone(server._state["artifacts"])
        self.assertIsNotNone(server._state["phone_df"])
        self.assertIsNotNone(server._state["phone_artifacts"])

        page = client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Ticket Data Loaded", page.text)
        self.assertIn("Phone Data Loaded", page.text)
        self.assertIn("EXPORT TICKET WORKBOOK", page.text)
        self.assertIn("EXPORT MONTHLY TICKET WORKBOOK", page.text)
        self.assertIn("Include Phone Metrics Tab", page.text)
        self.assertNotIn("EXPORT PHONE WORKBOOK", page.text)

        standard_without_phone = client.get("/export/workbook?include_phone_metrics=0")
        self.assertEqual(standard_without_phone.status_code, 200)
        sheet_names_without_phone = self.workbook_sheet_names(standard_without_phone.content)
        self.assertNotIn("Phone Metrics", sheet_names_without_phone)

        standard_with_phone = client.get("/export/workbook?include_phone_metrics=1")
        self.assertEqual(standard_with_phone.status_code, 200)
        standard_sheet_names = self.workbook_sheet_names(standard_with_phone.content)
        self.assertIn("Phone Metrics", standard_sheet_names)
        self.assertEqual(standard_sheet_names[:4], ["Summary", "Tickets", "Phone Metrics", "Escalations"])

        ticket_workbook = client.get("/export/workbook?monthly_ticket_report_mode=1&include_phone_metrics=1")
        self.assertEqual(ticket_workbook.status_code, 200)
        self.assertIn("Monthly_Ticket_Report.xlsx", ticket_workbook.headers.get("content-disposition", ""))
        monthly_sheet_names = self.workbook_sheet_names(ticket_workbook.content)
        self.assertEqual(monthly_sheet_names[0], "Monthly Snapshot")
        self.assertEqual(monthly_sheet_names[1], "Phone Metrics")
        self.assertIn("Phone Metrics", monthly_sheet_names)


if __name__ == "__main__":
    unittest.main()
