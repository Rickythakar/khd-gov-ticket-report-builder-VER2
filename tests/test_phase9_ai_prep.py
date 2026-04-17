from __future__ import annotations

import copy
import importlib.util
import os
import sys
import tempfile
import unittest
import warnings
import zipfile
from io import BytesIO
from pathlib import Path
from unittest import mock

import pandas as pd
from fastapi.testclient import TestClient

from validators import validate_and_prepare_dataframe


RUN_PHASE9_PREP = os.getenv("RUN_PHASE9_PREP") == "1"
REPO_ROOT = Path(__file__).resolve().parents[1]
AI_ENGINE_MODULE_PATH = REPO_ROOT / "ai_engine.py"
CONFIG_MODULE_PATH = REPO_ROOT / "config.py"
EXCEL_BUILDER_MODULE_PATH = REPO_ROOT / "excel_builder.py"
REQUIREMENTS_PATH = REPO_ROOT / "requirements.txt"
SERVER_MODULE_PATH = REPO_ROOT / "server.py"
SETTINGS_MODULE_PATH = REPO_ROOT / "settings.py"
TEMPLATE_PATH = REPO_ROOT / "templates" / "dashboard.html"
SAMPLE_CSV = REPO_ROOT / "sample_input.csv"
UTILS_MODULE_PATH = REPO_ROOT / "utils.py"


@unittest.skipUnless(RUN_PHASE9_PREP, "Phase 9 prep suite; set RUN_PHASE9_PREP=1 to activate during AI work.")
class Phase9AiPrepTests(unittest.TestCase):
    """Regression gate for the Phase 9 AI analysis work."""

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

    def internal_settings(self) -> dict:
        settings = self.load_module(SETTINGS_MODULE_PATH, "phase9_settings_internal")
        config = copy.deepcopy(settings.DEFAULT_SETTINGS)
        config["mode"] = settings.MODE_INTERNAL
        config["ai"]["enabled"] = True
        config["ai"]["provider"] = "azure_openai"
        config["ai"]["endpoint"] = "https://example.openai.azure.com/"
        config["ai"]["api_key"] = "fake-key"
        return config

    def customer_settings(self) -> dict:
        settings = self.load_module(SETTINGS_MODULE_PATH, "phase9_settings_customer")
        config = copy.deepcopy(settings.DEFAULT_SETTINGS)
        config["mode"] = settings.MODE_CUSTOMER
        config["ai"]["enabled"] = True
        return config

    def build_fake_ai_result(self):
        ai_engine = self.load_module(AI_ENGINE_MODULE_PATH, "phase9_ai_engine_result")
        return ai_engine.AIAnalysisResult(
            executive_summary="AI-generated executive summary for governance review.",
            sentiment=[
                ai_engine.SentimentResult(ticket_id="1001", sentiment=2, confidence=0.91, indicators=["angry"]),
                ai_engine.SentimentResult(ticket_id="1002", sentiment=4, confidence=0.77, indicators=["thanks"]),
            ],
            calls_made=3,
            tokens_used=1200,
        )

    def build_artifacts(self, mode: str = "internal"):
        utils = self.load_module(UTILS_MODULE_PATH, f"phase9_utils_{mode}")
        config = self.load_module(CONFIG_MODULE_PATH, f"phase9_config_{mode}")
        settings = self.internal_settings() if mode == "internal" else self.customer_settings()
        report_mode = config.REPORT_MODE_INTERNAL if mode == "internal" else config.REPORT_MODE_CUSTOMER
        return utils.build_report_artifacts(
            self.prepared_df(),
            report_mode=report_mode,
            settings=settings,
        )

    def build_workbook_bytes_with_ai(self) -> bytes:
        config = self.load_module(CONFIG_MODULE_PATH, "phase9_config_workbook")
        excel_builder = self.load_module(EXCEL_BUILDER_MODULE_PATH, "phase9_excel_builder")

        with tempfile.TemporaryDirectory() as tmp_dir:
            request = excel_builder.ReportRequest(
                dataframe=self.prepared_df(),
                report_title="Phase 9 Workbook",
                logo_path=config.DEFAULT_LOGO_PATH,
                output_path=Path(tmp_dir) / "phase9.xlsx",
                partner_name="Acme",
                date_range="Mar 2026",
                report_mode=config.REPORT_MODE_INTERNAL,
                settings=self.internal_settings(),
                ai_results=self.build_fake_ai_result(),
            )
            built_path = excel_builder.ExcelReportBuilder().build_report(request)
            return built_path.read_bytes()

    def test_given_phase9_spec_when_requirements_are_reviewed_then_openai_dependency_is_declared(self) -> None:
        requirements = REQUIREMENTS_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "openai",
            requirements.lower(),
            "Phase 9 adds Azure OpenAI integration, so requirements.txt should declare the openai package.",
        )

    def test_given_openai_provider_support_when_dashboard_template_is_reviewed_then_provider_controls_and_env_guidance_exist(self) -> None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")

        self.assertIn(
            'id="aiProvider"',
            template,
            "The settings modal should let operators switch between Azure OpenAI and OpenAI API.",
        )
        self.assertIn(
            "OPENAI_API_KEY",
            template,
            "The OpenAI provider guidance should mention env-backed auth so users do not have to persist secrets in settings.",
        )
        self.assertIn(
            "syncAiProviderUi",
            template,
            "Provider-specific controls should be toggled in the settings UI instead of leaving both forms visible.",
        )

    def test_given_phase9_spec_when_ai_routes_are_reviewed_then_status_results_summary_and_clear_endpoints_exist(self) -> None:
        server = self.load_module(SERVER_MODULE_PATH, "phase9_server_routes")
        paths = {route.path for route in server.app.routes}

        for path in ("/ai/run", "/ai/status", "/ai/results", "/ai/summary", "/ai/clear"):
            self.assertIn(
                path,
                paths,
                f"Phase 9 should expose {path} so the AI dashboard can run, poll, inspect, and clear analysis state.",
            )

    def test_given_customer_and_internal_render_contexts_when_dashboard_template_is_rendered_then_ai_assist_is_internal_only(self) -> None:
        server = self.load_module(SERVER_MODULE_PATH, "phase9_server_render")

        common = {
            "app_name": "KHD Governance Report Builder",
            "app_version": "test",
            "partner_name": "Acme",
            "date_range": "Mar 2026",
            "report_title": "AI Dashboard",
            "output_filename": "ai-dashboard",
            "csv_name": SAMPLE_CSV.name,
            "error": "",
            "has_data": True,
            "MODE_CUSTOMER": "customer",
            "MODE_INTERNAL": "internal",
            "period": "1M",
            "selected_month": "",
            "available_months": [],
            "comp": {"has_comparison": False},
            "file_count": 1,
            "ai": {"has_ai": False},
            "ai_enabled": True,
        }

        customer_html = server.render_template(
            "dashboard.html",
            {
                **common,
                "settings": self.customer_settings(),
                "mode": "customer",
                "a": server._serialize_artifacts(self.build_artifacts("customer")),
            },
        )
        internal_html = server.render_template(
            "dashboard.html",
            {
                **common,
                "settings": self.internal_settings(),
                "mode": "internal",
                "a": server._serialize_artifacts(self.build_artifacts("internal")),
            },
        )

        self.assertNotIn(
            'id="aiToggleBtn"',
            customer_html,
            "The Phase 9 AI surface should stay hidden in customer mode even when AI is configured.",
        )
        self.assertNotIn(
            'class="ai-view"',
            customer_html,
            "Customer mode should not render the hidden AI panel container at all.",
        )
        self.assertIn(
            'id="aiToggleBtn"',
            internal_html,
            "Internal mode should expose the AI assist entrypoint once AI is enabled.",
        )

    def test_given_openai_provider_when_client_is_created_then_it_uses_the_standard_openai_client_without_requiring_an_endpoint(self) -> None:
        ai_engine = self.load_module(AI_ENGINE_MODULE_PATH, "phase9_ai_engine_openai_provider")
        settings = self.internal_settings()
        settings["ai"].update({
            "provider": "openai",
            "endpoint": "",
            "api_key": "sk-openai-test",
            "base_url": "https://api.openai.com/v1",
            "organization": "org_test",
            "project": "proj_test",
        })

        openai_ctor = mock.Mock(return_value=object())
        fake_openai_module = type("FakeOpenAI", (), {"OpenAI": openai_ctor})

        with mock.patch.dict(sys.modules, {"openai": fake_openai_module}):
            engine = ai_engine.AIEngine(settings)
            client = engine._get_client()

        self.assertIs(client, openai_ctor.return_value)
        openai_ctor.assert_called_once_with(
            api_key="sk-openai-test",
            base_url="https://api.openai.com/v1",
            organization="org_test",
            project="proj_test",
        )

    def test_given_openai_provider_when_api_key_is_supplied_via_environment_then_ai_context_still_passes(self) -> None:
        server = self.load_module(SERVER_MODULE_PATH, "phase9_server_openai_env")
        settings = self.internal_settings()
        settings["ai"].update({
            "provider": "openai",
            "endpoint": "",
            "api_key": "",
        })
        server._state["settings"] = settings
        server._state["prepared_df"] = self.prepared_df()
        server._state["artifacts"] = object()

        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "env-openai-key"}, clear=False):
            _, error = server._ensure_ai_context()

        self.assertIsNone(
            error,
            "Operators should be able to rely on OPENAI_API_KEY instead of persisting the key in settings.json.",
        )

    def test_given_stale_ai_results_when_context_changes_then_cached_ai_analysis_is_cleared(self) -> None:
        server = self.load_module(SERVER_MODULE_PATH, "phase9_server_state")
        ai_result = self.build_fake_ai_result()
        server._state["ai_results"] = ai_result
        server._state["prepared_df"] = self.prepared_df()
        server._state["artifacts"] = object()
        server._state["buckets"] = []

        client = TestClient(server.app)
        clear_response = client.post("/clear")

        self.assertEqual(clear_response.status_code, 200)
        self.assertIsNone(
            server._state["ai_results"],
            "Clearing or replacing the active dataset should clear cached AI results so stale analysis does not survive into the next run.",
        )

    def test_given_ai_results_when_internal_workbook_is_built_then_summary_and_ticket_exports_include_ai_output(self) -> None:
        workbook_bytes = self.build_workbook_bytes_with_ai()

        with zipfile.ZipFile(BytesIO(workbook_bytes)) as workbook_zip:
            shared_strings = workbook_zip.read("xl/sharedStrings.xml").decode("utf-8")

        self.assertIn(
            "AI-Generated Executive Summary",
            shared_strings,
            "Phase 9 should add the AI executive summary to the workbook summary sheet.",
        )
        self.assertIn(
            "AI Sentiment",
            shared_strings,
            "Phase 9 should add an AI Sentiment column to the ticket export when AI results are available.",
        )

    def test_given_ai_results_when_export_routes_run_then_they_receive_the_cached_ai_payload(self) -> None:
        server = self.load_module(SERVER_MODULE_PATH, "phase9_server_exports")
        ai_result = self.build_fake_ai_result()
        server._state["settings"] = self.internal_settings()
        server._state["prepared_df"] = self.prepared_df()
        server._state["artifacts"] = mock.Mock(report_mode="internal_analysis")
        server._state["partner_name"] = "Acme"
        server._state["date_range"] = "Mar 2026"
        server._state["report_title"] = "AI Export"
        server._state["output_filename"] = "ai-export"
        server._state["ai_results"] = ai_result

        client = TestClient(server.app)

        with mock.patch("excel_builder.ExcelReportBuilder.build_report") as build_report:
            fake_path = Path(tempfile.gettempdir()) / "phase9-export.xlsx"
            fake_path.write_bytes(b"phase9")
            build_report.return_value = fake_path
            response = client.get("/export/workbook")
            self.assertEqual(response.status_code, 200)
            request_arg = build_report.call_args.args[0]
            self.assertIs(
                request_arg.ai_results,
                ai_result,
                "Workbook export should receive the cached AI payload so the summary sheet and ticket columns stay aligned with the dashboard.",
            )
            fake_path.unlink(missing_ok=True)

        with mock.patch("pdf_builder.ExecutivePdfSnapshotBuilder.build_pdf_bytes", return_value=b"%PDF-1.4\n%%EOF") as build_pdf:
            response = client.get("/export/pdf")
            self.assertEqual(response.status_code, 200)
            self.assertIs(
                build_pdf.call_args.kwargs["ai_results"],
                ai_result,
                "PDF export should receive the cached AI payload so page 1 can include the AI-generated executive summary.",
            )


if __name__ == "__main__":
    unittest.main()
