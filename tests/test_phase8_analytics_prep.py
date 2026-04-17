from __future__ import annotations

import copy
import importlib.util
import os
import sys
import unittest
import warnings
from dataclasses import fields
from pathlib import Path

import pandas as pd

from validators import validate_and_prepare_dataframe


RUN_PHASE8_PREP = os.getenv("RUN_PHASE8_PREP") == "1"
REPO_ROOT = Path(__file__).resolve().parents[1]
ANALYTICS_MODULE_PATH = REPO_ROOT / "analytics.py"
CONFIG_MODULE_PATH = REPO_ROOT / "config.py"
METRICS_MODULE_PATH = REPO_ROOT / "metrics.py"
SERVER_MODULE_PATH = REPO_ROOT / "server.py"
SETTINGS_MODULE_PATH = REPO_ROOT / "settings.py"
TEMPLATE_PATH = REPO_ROOT / "templates" / "dashboard.html"
UTILS_MODULE_PATH = REPO_ROOT / "utils.py"
SAMPLE_CSV = REPO_ROOT / "sample_input.csv"


@unittest.skipUnless(RUN_PHASE8_PREP, "Phase 8 prep suite; set RUN_PHASE8_PREP=1 to activate during internal analytics work.")
class Phase8AnalyticsPrepTests(unittest.TestCase):
    """Red-suite prep for the Phase 8 advanced internal analytics work."""

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
        settings = self.load_module(SETTINGS_MODULE_PATH, "phase8_settings_internal")
        config = copy.deepcopy(settings.DEFAULT_SETTINGS)
        config["mode"] = settings.MODE_INTERNAL
        return config

    def internal_artifacts(self):
        utils = self.load_module(UTILS_MODULE_PATH, "phase8_utils_internal")
        config = self.load_module(CONFIG_MODULE_PATH, "phase8_config_internal")
        return utils.build_report_artifacts(
            self.prepared_df(),
            report_mode=config.REPORT_MODE_INTERNAL,
            settings=self.internal_settings(),
        )

    def test_given_current_internal_artifact_builder_when_i_analyze_the_sample_csv_in_internal_mode_then_technician_review_metrics_are_already_available_as_the_phase8_foundation(self) -> None:
        artifacts = self.internal_artifacts()

        self.assertIsNotNone(
            artifacts.technician_scorecards,
            "Phase 8 should build on the existing internal technician review foundation rather than replacing it.",
        )
        self.assertIn(
            "Technician",
            list(getattr(artifacts.technician_scorecards, "columns", [])),
            "Technician scorecards should already provide the per-tech baseline that Phase 8 analytics expands.",
        )

    def test_given_the_phase8_analytics_module_path_when_i_inspect_the_internal_analytics_api_then_analytics_py_exists_and_exposes_the_planned_logic_functions(self) -> None:
        self.assertTrue(
            ANALYTICS_MODULE_PATH.exists(),
            "Phase 8 introduces a new analytics.py module for pure local analytics logic.",
        )

        analytics = self.load_module(ANALYTICS_MODULE_PATH, "phase8_analytics_module")
        for name in (
            "compute_complexity_scores",
            "classify_tickets_by_keyword",
            "compute_workload_balance",
            "compute_peak_heatmap",
            "compute_kb_coverage",
            "compute_company_issue_patterns",
            "compute_escalation_timing",
            "compute_description_complexity",
        ):
            self.assertTrue(
                hasattr(analytics, name),
                f"analytics.py should expose {name}() for the Phase 8 internal analytics surface.",
            )

    def test_given_the_metrics_module_when_i_inspect_the_phase8_integration_surface_then_complexity_keyword_workload_and_heatmap_helpers_are_available_from_metrics_py(self) -> None:
        metrics = self.load_module(METRICS_MODULE_PATH, "phase8_metrics_api")

        for name in (
            "compute_complexity_scores",
            "classify_tickets_by_keyword",
            "compute_workload_balance",
            "compute_peak_heatmap",
        ):
            self.assertTrue(
                hasattr(metrics, name),
                f"metrics.py should expose {name}() so the existing reporting pipeline can integrate Phase 8 analytics.",
            )

    def test_given_the_reportartifacts_dataclass_when_i_inspect_the_internal_analytics_fields_then_analytics_payload_fields_exist_for_dashboard_serialization(self) -> None:
        utils = self.load_module(UTILS_MODULE_PATH, "phase8_utils_fields")
        artifact_fields = {field.name for field in fields(utils.ReportArtifacts)}

        for field_name in (
            "complexity_scores",
            "keyword_category_table",
            "workload_balance",
            "peak_heatmap",
            "kb_coverage",
            "company_issue_patterns",
            "escalation_timing",
            "description_complexity",
        ):
            self.assertIn(
                field_name,
                artifact_fields,
                f"ReportArtifacts should grow a {field_name} field for Phase 8 internal analytics.",
            )

    def test_given_the_dashboard_template_when_i_review_the_internal_analytics_surface_then_it_renders_an_analytics_widget_with_complexity_keyword_workload_and_peakload_tabs(self) -> None:
        template_text = TEMPLATE_PATH.read_text(encoding="utf-8").upper()

        self.assertIn(
            "ANALYTICS",
            template_text,
            "Phase 8 should add an internal-only Analytics widget to dashboard.html.",
        )
        for token in ("COMPLEXITY", "KEYWORD", "WORKLOAD", "PEAK LOAD"):
            self.assertIn(
                token,
                template_text,
                f"Phase 8 should expose a {token.title()} tab or label in the Analytics widget.",
            )

    def test_given_internalmode_report_artifacts_when_i_serialize_them_for_the_fastapi_dashboard_then_the_payload_includes_analytics_data_for_the_internal_widget(self) -> None:
        server = self.load_module(SERVER_MODULE_PATH, "phase8_server_serialize")
        payload = server._serialize_artifacts(self.internal_artifacts())

        self.assertIn(
            "analytics",
            payload,
            "Phase 8 should serialize a dedicated analytics payload for the internal dashboard widget.",
        )


if __name__ == "__main__":
    unittest.main()
