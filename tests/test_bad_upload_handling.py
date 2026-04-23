from __future__ import annotations

import importlib.util
import io
import sys
import unittest
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_MODULE_PATH = REPO_ROOT / "server.py"
SAMPLE_CSV = REPO_ROOT / "sample_input.csv"


def build_autotask_created_ticket_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Task Number": "TASK-1001",
                "Task ID": "1001",
                "Parent Task Number": "MSP-1001",
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


class BadUploadHandlingTests(unittest.TestCase):
    def load_server_module(self, module_name: str):
        spec = importlib.util.spec_from_file_location(module_name, SERVER_MODULE_PATH)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    def invalid_csv_bytes(self) -> bytes:
        frame = pd.DataFrame(
            [
                {"Agent": "A. Smith", "Call Duration": 120, "Disposition": "Answered"},
                {"Agent": "B. Jones", "Call Duration": 45, "Disposition": "Missed"},
            ]
        )
        return frame.to_csv(index=False).encode("utf-8")

    def test_wrong_csv_upload_returns_clean_validation_error_instead_of_crashing(self) -> None:
        server = self.load_server_module("bad_upload_server_invalid_only")
        client = TestClient(server.app)

        response = client.post(
            "/upload",
            files=[("file", ("wrong.csv", self.invalid_csv_bytes(), "text/csv"))],
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported upload format", response.json()["message"])
        self.assertIn("supported ticket export or phone metrics export", server._state["error"])

        page = client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("[ERR]", page.text)
        self.assertIn("supported ticket export or phone metrics export", page.text)

    def test_bad_upload_does_not_replace_existing_valid_dashboard_state(self) -> None:
        server = self.load_server_module("bad_upload_server_preserve_state")
        client = TestClient(server.app)

        valid_response = client.post(
            "/upload",
            files=[("file", (SAMPLE_CSV.name, SAMPLE_CSV.read_bytes(), "text/csv"))],
        )
        self.assertEqual(valid_response.status_code, 200)
        existing_csv_names = list(server._state["csv_names"])
        existing_report_title = server._state["report_title"]
        self.assertTrue(existing_csv_names)

        invalid_response = client.post(
            "/upload",
            files=[("file", ("wrong.csv", self.invalid_csv_bytes(), "text/csv"))],
        )

        self.assertEqual(invalid_response.status_code, 400)
        self.assertEqual(server._state["csv_names"], existing_csv_names)
        self.assertEqual(server._state["report_title"], existing_report_title)

        page = client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn(existing_report_title, page.text)

    def test_analytics_serializer_returns_safe_heatmap_defaults(self) -> None:
        server = self.load_server_module("bad_upload_server_analytics_defaults")

        payload = server._serialize_analytics(
            type(
                "BrokenAnalytics",
                (),
                {
                    "complexity_summary": {"mean": 0, "median": 0, "high_count": 0, "low_count": 0},
                    "complexity_scores": pd.DataFrame(),
                    "keyword_categories": pd.DataFrame(),
                    "keyword_escalation": pd.DataFrame(),
                    "workload_balance": pd.DataFrame(),
                    "peak_heatmap": {"grid": [], "days": [], "hours": []},
                    "kb_coverage": pd.DataFrame(),
                    "company_patterns": pd.DataFrame(),
                    "escalation_timing": pd.DataFrame(),
                    "description_complexity": pd.DataFrame(),
                },
            )()
        )

        self.assertTrue(payload["available"])
        self.assertEqual(len(payload["peak_heatmap"]["grid"]), 7)
        self.assertEqual(len(payload["peak_heatmap"]["grid"][0]), 24)
        self.assertEqual(len(payload["peak_heatmap"]["days"]), 7)
        self.assertEqual(len(payload["peak_heatmap"]["hours"]), 24)

    def test_schema_compatible_upload_is_accepted_regardless_of_filename_or_source_label(self) -> None:
        server = self.load_server_module("bad_upload_server_schema_compatible")
        client = TestClient(server.app)

        response = client.post(
            "/upload",
            files=[("file", ("powerbi_created_ticket_export.csv", SAMPLE_CSV.read_bytes(), "text/csv"))],
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(server._state["artifacts"] is not None)
        self.assertIn("powerbi_created_ticket_export.csv", server._state["csv_names"])

    def test_autotask_created_ticket_column_set_is_accepted(self) -> None:
        server = self.load_server_module("bad_upload_server_autotask_raw")
        client = TestClient(server.app)
        frame = build_autotask_created_ticket_frame()

        response = client.post(
            "/upload",
            files=[("file", ("autotask_created_ticket_export.csv", frame.to_csv(index=False).encode("utf-8"), "text/csv"))],
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(server._state["prepared_df"]["Ticket Number"].iloc[0], "TASK-1001")
        self.assertEqual(server._state["prepared_df"]["Company"].iloc[0], "Acme Manufacturing")
        self.assertEqual(server._state["prepared_df"]["Queue"].iloc[0], "Service Desk")
        self.assertEqual(server._state["ticket_source_label"], "Autotask created-ticket export")


if __name__ == "__main__":
    unittest.main()
