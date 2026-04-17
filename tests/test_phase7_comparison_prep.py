from __future__ import annotations

import copy
import html
import importlib.util
import json
import os
import re
import sys
import tempfile
import unittest
import warnings
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import fields
from io import BytesIO
from pathlib import Path
from typing import get_args, get_origin, get_type_hints

import pandas as pd
from fastapi.testclient import TestClient

from validators import validate_and_prepare_dataframe


RUN_PHASE7_PREP = os.getenv("RUN_PHASE7_PREP") == "1"
REPO_ROOT = Path(__file__).resolve().parents[1]
COMPARISON_MODULE_PATH = REPO_ROOT / "comparison.py"
CONFIG_MODULE_PATH = REPO_ROOT / "config.py"
EXCEL_BUILDER_MODULE_PATH = REPO_ROOT / "excel_builder.py"
METRICS_MODULE_PATH = REPO_ROOT / "metrics.py"
SERVER_MODULE_PATH = REPO_ROOT / "server.py"
SETTINGS_MODULE_PATH = REPO_ROOT / "settings.py"
TEMPLATE_PATH = REPO_ROOT / "templates" / "dashboard.html"
UTILS_MODULE_PATH = REPO_ROOT / "utils.py"
SAMPLE_CSV = REPO_ROOT / "sample_input.csv"
SAMPLE_FEBRUARY_CSV = REPO_ROOT / "sample_february.csv"


@unittest.skipUnless(RUN_PHASE7_PREP, "Phase 7 prep suite; set RUN_PHASE7_PREP=1 to activate during comparison work.")
class Phase7ComparisonPrepTests(unittest.TestCase):
    """Red-suite prep for the Phase 7 multi-month comparison work."""

    @classmethod
    def setUpClass(cls) -> None:
        warnings.filterwarnings(
            "ignore",
            message="Could not infer format, so each element will be parsed individually",
            category=UserWarning,
        )

    def load_module(self, module_path: Path, module_name: str):
        self.assertTrue(module_path.exists(), f"Expected module at {module_path}")
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    def prepared_df(self) -> pd.DataFrame:
        raw_df = pd.read_csv(SAMPLE_CSV)
        return validate_and_prepare_dataframe(raw_df).dataframe

    def prepared_df_for(self, path: Path) -> pd.DataFrame:
        raw_df = pd.read_csv(path)
        return validate_and_prepare_dataframe(raw_df).dataframe

    def customer_settings(self) -> dict:
        settings = self.load_module(SETTINGS_MODULE_PATH, "phase7_settings_customer")
        config = copy.deepcopy(settings.DEFAULT_SETTINGS)
        config["mode"] = settings.MODE_CUSTOMER
        return config

    def workbook_sheet_states(self, workbook_bytes: bytes) -> dict[str, str]:
        with zipfile.ZipFile(BytesIO(workbook_bytes)) as workbook_zip:
            workbook_xml = ET.fromstring(workbook_zip.read("xl/workbook.xml"))
        namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        return {
            sheet.attrib["name"]: sheet.attrib.get("state", "visible")
            for sheet in workbook_xml.findall("main:sheets/main:sheet", namespace)
        }

    def build_customer_workbook(self) -> bytes:
        config = self.load_module(CONFIG_MODULE_PATH, "phase7_config_workbook")
        excel_builder = self.load_module(EXCEL_BUILDER_MODULE_PATH, "phase7_excel_builder")

        with tempfile.TemporaryDirectory() as tmp_dir:
            request = excel_builder.ReportRequest(
                dataframe=self.prepared_df(),
                report_title="Phase 7 Workbook",
                logo_path=config.DEFAULT_LOGO_PATH,
                output_path=Path(tmp_dir) / "phase7.xlsx",
                partner_name="Acme",
                date_range="Quarterly Comparison",
                report_mode=config.REPORT_MODE_CUSTOMER,
                settings=self.customer_settings(),
            )
            built_path = excel_builder.ExcelReportBuilder().build_report(request)
            return built_path.read_bytes()

    def render_comparison_dashboard_html(self) -> str:
        comparison = self.load_module(COMPARISON_MODULE_PATH, "phase7_comparison_render")
        config = self.load_module(CONFIG_MODULE_PATH, "phase7_config_render")
        server = self.load_module(SERVER_MODULE_PATH, "phase7_server_render")
        utils = self.load_module(UTILS_MODULE_PATH, "phase7_utils_render")

        february_df = self.prepared_df_for(SAMPLE_FEBRUARY_CSV)
        march_df = self.prepared_df()
        combined_df = pd.concat([february_df, march_df], ignore_index=True)
        settings = self.customer_settings()
        comparison_obj = comparison.compute_comparison(comparison.bucket_by_month(combined_df), period="1M")
        artifacts = utils.build_report_artifacts(
            march_df,
            report_mode=config.REPORT_MODE_CUSTOMER,
            settings=settings,
        )

        return server.render_template(
            "dashboard.html",
            {
                "app_name": "KHD Governance Report Builder",
                "app_version": "test",
                "settings": settings,
                "mode": settings["mode"],
                "partner_name": "Acme",
                "date_range": "Feb 2026 - Mar 2026",
                "report_title": "Comparison Dashboard",
                "output_filename": "comparison-dashboard",
                "csv_name": f"{SAMPLE_FEBRUARY_CSV.name}, {SAMPLE_CSV.name}",
                "error": "",
                "has_data": True,
                "a": server._serialize_artifacts(artifacts, comparison_obj),
                "MODE_CUSTOMER": settings["mode"],
                "MODE_INTERNAL": "internal_analysis",
                "period": "1M",
                "selected_month": "2026-03",
                "available_months": [bucket.label for bucket in comparison.bucket_by_month(combined_df)],
                "comp": comparison.serialize_comparison(comparison_obj),
                "file_count": 2,
            },
        )

    def test_given_current_artifact_builder_when_sample_csv_is_analyzed_then_monthly_trend_table_is_already_available(self) -> None:
        utils = self.load_module(UTILS_MODULE_PATH, "phase7_utils_foundation")
        config = self.load_module(CONFIG_MODULE_PATH, "phase7_config_foundation")

        artifacts = utils.build_report_artifacts(
            self.prepared_df(),
            report_mode=config.REPORT_MODE_CUSTOMER,
            settings=self.customer_settings(),
        )

        self.assertFalse(
            artifacts.monthly_trend_table.empty,
            "Phase 7 already has a month-level trend foundation in ReportArtifacts via monthly_trend_table.",
        )
        self.assertEqual(
            list(artifacts.monthly_trend_table.columns),
            ["Month", "Tickets"],
            "The existing monthly_trend_table should already expose the basic month-volume shape Phase 7 can build on.",
        )

    def test_given_live_upload_endpoint_when_i_inspect_the_signature_then_it_accepts_multiple_upload_files(self) -> None:
        server = self.load_module(SERVER_MODULE_PATH, "phase7_server_upload")
        type_hints = get_type_hints(server.upload_csv)
        annotation = type_hints["file"]
        origin = get_origin(annotation)
        args = get_args(annotation)

        supports_multi_upload = origin in (list, tuple) and any(arg.__name__ == "UploadFile" for arg in args if hasattr(arg, "__name__"))
        self.assertTrue(
            supports_multi_upload,
            "Phase 7 needs the FastAPI upload endpoint to accept multiple UploadFile inputs for multi-month comparison mode.",
        )

    def test_given_prior_upload_state_when_i_upload_a_new_multifile_comparison_set_then_the_previous_inmemory_upload_set_is_replaced_instead_of_accumulating_forever(self) -> None:
        server = self.load_module(SERVER_MODULE_PATH, "phase7_server_replace_uploads")
        server._state["all_dfs"] = [("old.csv", self.prepared_df().head(5))]
        server._state["csv_names"] = ["old.csv"]

        client = TestClient(server.app)
        response = client.post(
            "/upload",
            files=[
                ("file", (SAMPLE_FEBRUARY_CSV.name, SAMPLE_FEBRUARY_CSV.read_bytes(), "text/csv")),
                ("file", (SAMPLE_CSV.name, SAMPLE_CSV.read_bytes(), "text/csv")),
            ],
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            server._state["csv_names"],
            [SAMPLE_FEBRUARY_CSV.name, SAMPLE_CSV.name],
            "A fresh comparison upload should replace the prior in-memory file set instead of silently stacking old runs.",
        )
        self.assertEqual(len(server._state["all_dfs"]), 2)

    def test_given_metrics_module_when_i_inspect_the_phase7_api_then_comparison_helpers_exist(self) -> None:
        metrics = self.load_module(METRICS_MODULE_PATH, "phase7_metrics_api")

        self.assertTrue(
            hasattr(metrics, "compute_monthly_breakdown"),
            "Phase 7 should add compute_monthly_breakdown() to metrics.py for multi-month comparison support.",
        )
        self.assertTrue(
            hasattr(metrics, "compute_period_deltas"),
            "Phase 7 should add compute_period_deltas() to metrics.py for delta indicators and comparison exports.",
        )

    def test_given_dashboard_template_when_i_review_the_comparison_controls_then_period_selector_and_trends_widget_exist(self) -> None:
        template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
        missing_period_tokens = [token for token in ("1M", "QTR", "HALF", "YR") if token not in template_text]
        self.assertEqual(
            missing_period_tokens,
            [],
            "Phase 7 should render a period selector with 1M/QTR/HALF/YR controls in dashboard.html.",
        )

        self.assertIn(
            "TRENDS",
            template_text.upper(),
            "Phase 7 should add a Trends widget surface to the FastAPI dashboard template.",
        )

    def test_given_rendered_comparison_dashboard_html_when_i_inspect_the_trend_svg_data_attributes_then_the_label_and_value_payloads_remain_valid_json_arrays_for_browser_side_chart_rendering(self) -> None:
        template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "window.TREND_DATA = {{ comp.trends | tojson }};",
            template_text,
            "The Trends template should serialize the comparison payload into window.TREND_DATA for browser-side chart rendering.",
        )
        self.assertIn(
            'data-key="tickets"',
            template_text,
            "The Trends template should keep the tickets SVG keyed so the browser renderer can bind window.TREND_DATA into the right chart.",
        )

        server = self.load_module(SERVER_MODULE_PATH, "phase7_server_trend_attr_render")
        script_snippet = server._jinja_env.from_string(
            "<script>window.TREND_DATA = {{ comp.trends | tojson }};</script>"
        ).render(comp={"trends": {"tickets": [500, 746], "labels": ["2026-02", "2026-03"]}})

        payload_match = re.search(r"window\.TREND_DATA = (.*?);</script>", script_snippet, re.S)
        self.assertIsNotNone(payload_match, "Expected the rendered Trends script snippet to expose a JSON payload.")

        payload = json.loads(html.unescape(payload_match.group(1)))
        labels = payload["labels"]
        values = payload["tickets"]

        self.assertEqual(
            labels,
            ["2026-02", "2026-03"],
            "Trend chart labels should survive template rendering as valid JSON so browser-side chart rendering does not crash.",
        )
        self.assertEqual(
            len(values),
            2,
            "Trend chart values should survive template rendering as a valid JSON array for each uploaded month.",
        )

    def test_given_rendered_comparison_dashboard_html_when_i_inspect_the_total_tickets_metric_card_then_the_primary_value_remains_in_a_dedicated_span_so_the_counter_animation_cannot_concatenate_the_delta_text(self) -> None:
        rendered_html = self.render_comparison_dashboard_html()
        card_match = re.search(
            r'<div class="m-label">Total Tickets</div>\s*<div class="m-val" data-val="([^"]+)">\s*<span class="m-val-num">([^<]+)</span>\s*(?:<span class="m-delta [^"]*">([^<]+)</span>)?',
            rendered_html,
            re.S,
        )

        self.assertIsNotNone(card_match, "Expected a rendered Total Tickets metric card in comparison mode.")
        self.assertEqual(
            card_match.group(1),
            card_match.group(2),
            "The metric card should keep the primary value isolated in .m-val-num so delta text cannot pollute the counter animation value.",
        )
        self.assertIsNotNone(
            card_match.group(3),
            "Comparison mode should still render a separate delta badge alongside the primary metric value.",
        )

    def test_given_workbook_built_from_multi_month_foundation_when_i_inspect_the_sheets_then_a_trends_sheet_is_present(self) -> None:
        sheet_states = self.workbook_sheet_states(self.build_customer_workbook())

        self.assertEqual(
            sheet_states.get("Trends"),
            "visible",
            "Phase 7 should add a visible Trends sheet to workbook exports for comparison mode.",
        )


if __name__ == "__main__":
    unittest.main()
