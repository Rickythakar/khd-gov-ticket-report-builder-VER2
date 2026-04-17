from __future__ import annotations

import importlib.util
import inspect
import os
import sys
import unittest
from pathlib import Path

import pandas as pd

from validators import validate_and_prepare_dataframe


RUN_PHASE3_PREP = os.getenv("RUN_PHASE3_PREP") == "1"
REPO_ROOT = Path(__file__).resolve().parents[1]
METRICS_MODULE_PATH = REPO_ROOT / "metrics.py"
UTILS_MODULE_PATH = REPO_ROOT / "utils.py"
SETTINGS_MODULE_PATH = REPO_ROOT / "settings.py"
SAMPLE_CSV = REPO_ROOT / "sample_input.csv"


@unittest.skipUnless(RUN_PHASE3_PREP, "Phase 3 prep suite; set RUN_PHASE3_PREP=1 to activate during metrics work.")
class Phase3MetricsPrepTests(unittest.TestCase):
    """Red-suite prep for the Phase 3 metrics engine."""

    def load_module(self, module_path: Path, module_name: str):
        self.assertTrue(module_path.exists(), f"Expected module at {module_path}")
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    def build_repeat_contact_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "Ticket Number": "T-1",
                    "Nexus Ticket Number": "N-1",
                    "Title": "Password reset",
                    "Company": "Alpha",
                    "Contact": "Alice",
                    "Created": "2026-03-01 09:00:00",
                    "Complete Date": "2026-03-01 09:10:00",
                    "Issue Type": "Access",
                    "Sub-Issue Type": "Password",
                    "Status": "Complete",
                    "Queue": "KHD - Level I",
                    "Escalation Reason": "",
                    "Source": "Phone",
                    "Priority": "High",
                    "KB Used": "",
                    "Primary Resource": "Tech A",
                    "Total Hours Worked": 0.2,
                },
                {
                    "Ticket Number": "T-2",
                    "Nexus Ticket Number": "N-2",
                    "Title": "VPN issue",
                    "Company": "Alpha",
                    "Contact": "Alice",
                    "Created": "2026-03-02 10:00:00",
                    "Complete Date": "2026-03-02 10:50:00",
                    "Issue Type": "Network",
                    "Sub-Issue Type": "VPN",
                    "Status": "Complete",
                    "Queue": "KHD - Level I",
                    "Escalation Reason": "",
                    "Source": "Email",
                    "Priority": "Medium",
                    "KB Used": "KB Request",
                    "Primary Resource": "Tech A",
                    "Total Hours Worked": 0.5,
                },
                {
                    "Ticket Number": "T-3",
                    "Nexus Ticket Number": "N-3",
                    "Title": "Outlook issue",
                    "Company": "Alpha",
                    "Contact": "Alice",
                    "Created": "2026-03-03 11:00:00",
                    "Complete Date": "2026-03-03 11:20:00",
                    "Issue Type": "Email",
                    "Sub-Issue Type": "Outlook",
                    "Status": "Complete",
                    "Queue": "KHD - Level I",
                    "Escalation Reason": "",
                    "Source": "Phone",
                    "Priority": "Low",
                    "KB Used": "",
                    "Primary Resource": "Tech B",
                    "Total Hours Worked": 0.3,
                },
            ]
        )

    def build_fcr_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "Ticket Number": "F-1",
                    "Nexus Ticket Number": "NF-1",
                    "Title": "Quick fix",
                    "Company": "Bravo",
                    "Contact": "Bob",
                    "Created": "2026-03-04 09:00:00",
                    "Complete Date": "2026-03-04 09:20:00",
                    "Issue Type": "Access",
                    "Sub-Issue Type": "Password",
                    "Status": "Complete",
                    "Queue": "KHD - Level I",
                    "Escalation Reason": "",
                    "Source": "Phone",
                    "Priority": "High",
                    "KB Used": "",
                    "Primary Resource": "Tech A",
                    "Total Hours Worked": 0.2,
                },
                {
                    "Ticket Number": "F-2",
                    "Nexus Ticket Number": "NF-2",
                    "Title": "Too slow",
                    "Company": "Bravo",
                    "Contact": "Bea",
                    "Created": "2026-03-04 10:00:00",
                    "Complete Date": "2026-03-04 11:00:00",
                    "Issue Type": "Network",
                    "Sub-Issue Type": "VPN",
                    "Status": "Complete",
                    "Queue": "KHD - Level I",
                    "Escalation Reason": "",
                    "Source": "Phone",
                    "Priority": "High",
                    "KB Used": "",
                    "Primary Resource": "Tech A",
                    "Total Hours Worked": 0.8,
                },
                {
                    "Ticket Number": "F-3",
                    "Nexus Ticket Number": "NF-3",
                    "Title": "Escalated",
                    "Company": "Bravo",
                    "Contact": "Ben",
                    "Created": "2026-03-04 12:00:00",
                    "Complete Date": "2026-03-04 12:15:00",
                    "Issue Type": "Email",
                    "Sub-Issue Type": "Outlook",
                    "Status": "Complete",
                    "Queue": "KHD - Level I",
                    "Escalation Reason": "Partner handoff",
                    "Source": "Phone",
                    "Priority": "High",
                    "KB Used": "",
                    "Primary Resource": "Tech B",
                    "Total Hours Worked": 0.25,
                },
                {
                    "Ticket Number": "F-4",
                    "Nexus Ticket Number": "NF-4",
                    "Title": "Second quick fix",
                    "Company": "Bravo",
                    "Contact": "Bella",
                    "Created": "2026-03-04 13:00:00",
                    "Complete Date": "2026-03-04 13:25:00",
                    "Issue Type": "Access",
                    "Sub-Issue Type": "Password",
                    "Status": "Complete",
                    "Queue": "KHD - Level I",
                    "Escalation Reason": "",
                    "Source": "Phone",
                    "Priority": "High",
                    "KB Used": "",
                    "Primary Resource": "Tech C",
                    "Total Hours Worked": 0.3,
                },
            ]
        )

    def test_given_phase3_spec_when_metrics_module_is_loaded_then_expected_functions_exist(self) -> None:
        metrics = self.load_module(METRICS_MODULE_PATH, "phase3_metrics")

        expected_functions = {
            "compute_resolution_times",
            "compute_sla_compliance",
            "compute_technician_scorecards",
            "compute_repeat_contacts",
            "compute_danger_zone_companies",
            "compute_after_hours_rate",
            "compute_weekly_velocity",
            "compute_fcr_rate",
            "compute_noise_tickets",
            "compute_kb_gaps",
            "normalize_kb_values",
        }

        missing = [name for name in expected_functions if not hasattr(metrics, name)]
        self.assertEqual(missing, [], f"metrics.py is missing Phase 3 functions: {missing}")

    def test_given_repeat_contact_history_when_threshold_is_three_then_contact_is_returned_with_count(self) -> None:
        metrics = self.load_module(METRICS_MODULE_PATH, "phase3_metrics_repeat")

        repeat_contacts = metrics.compute_repeat_contacts(self.build_repeat_contact_df(), threshold=3)

        self.assertIsInstance(repeat_contacts, pd.DataFrame)
        self.assertEqual(len(repeat_contacts), 1)
        row_text = " ".join(str(value) for value in repeat_contacts.iloc[0].tolist())
        self.assertIn("Alice", row_text)
        self.assertIn("Alpha", row_text)
        self.assertIn("3", row_text)

    def test_given_mixed_ticket_outcomes_when_fcr_is_computed_then_only_quick_non_escalated_tickets_count(self) -> None:
        metrics = self.load_module(METRICS_MODULE_PATH, "phase3_metrics_fcr")

        fcr_rate = metrics.compute_fcr_rate(self.build_fcr_df())

        self.assertAlmostEqual(
            fcr_rate,
            50.0,
            places=3,
            msg="FCR should be expressed as a percentage of eligible Level I tickets resolved within 30 minutes without escalation.",
        )

    def test_given_valid_dataset_when_report_artifacts_are_built_then_phase3_metric_fields_are_present(self) -> None:
        utils = self.load_module(UTILS_MODULE_PATH, "phase3_utils")
        settings = self.load_module(SETTINGS_MODULE_PATH, "phase3_settings")

        raw_df = pd.read_csv(SAMPLE_CSV)
        prepared = validate_and_prepare_dataframe(raw_df).dataframe

        signature = inspect.signature(utils.build_report_artifacts)
        self.assertIn(
            "settings",
            signature.parameters,
            "build_report_artifacts should accept the settings payload once Phase 3 metrics are wired in.",
        )

        artifacts = utils.build_report_artifacts(prepared, settings=settings.DEFAULT_SETTINGS)

        for field_name in (
            "resolution_metrics",
            "sla_metrics",
            "technician_scorecards",
            "repeat_contacts",
            "danger_zone_companies",
            "after_hours_metrics",
            "weekly_velocity",
            "fcr_rate",
            "noise_metrics",
            "kb_gaps",
        ):
            self.assertTrue(
                hasattr(artifacts, field_name),
                f"ReportArtifacts should expose `{field_name}` once Phase 3 is implemented.",
            )


if __name__ == "__main__":
    unittest.main()
