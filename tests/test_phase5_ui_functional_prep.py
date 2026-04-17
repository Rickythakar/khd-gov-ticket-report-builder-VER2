from __future__ import annotations

import importlib.util
import json
import os
import sys
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest


RUN_PHASE5_PREP = os.getenv("RUN_PHASE5_PREP") == "1"
REPO_ROOT = Path(__file__).resolve().parents[1]
APP_FILE = REPO_ROOT / "streamlit_app.py"
REQUIREMENTS_FILE = REPO_ROOT / "requirements.txt"
SETTINGS_JSON_PATH = REPO_ROOT / "settings.json"
SETTINGS_MODULE_PATH = REPO_ROOT / "settings.py"
STREAMLIT_APP_MODULE_PATH = REPO_ROOT / "streamlit_app.py"
SAMPLE_CSV = REPO_ROOT / "sample_input.csv"


@unittest.skipUnless(RUN_PHASE5_PREP, "Phase 5 prep suite; set RUN_PHASE5_PREP=1 to activate during UI overhaul work.")
class Phase5UiFunctionalPrepTests(unittest.TestCase):
    """Red-suite prep for the Phase 5 functional UI overhaul."""

    @classmethod
    def setUpClass(cls) -> None:
        warnings.filterwarnings(
            "ignore",
            message="Could not infer format, so each element will be parsed individually",
            category=UserWarning,
        )

    def setUp(self) -> None:
        self._original_settings_json = SETTINGS_JSON_PATH.read_text(encoding="utf-8") if SETTINGS_JSON_PATH.exists() else None
        settings = self.load_module(SETTINGS_MODULE_PATH, "phase5_settings_setup")
        SETTINGS_JSON_PATH.write_text(json.dumps(settings.DEFAULT_SETTINGS, indent=2), encoding="utf-8")

    def tearDown(self) -> None:
        if self._original_settings_json is None:
            if SETTINGS_JSON_PATH.exists():
                SETTINGS_JSON_PATH.unlink()
        else:
            SETTINGS_JSON_PATH.write_text(self._original_settings_json, encoding="utf-8")

    def load_module(self, module_path: Path, module_name: str):
        self.assertTrue(module_path.exists(), f"Expected module at {module_path}")
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    def make_app(self) -> AppTest:
        return AppTest.from_file(str(APP_FILE))

    def upload_sample_csv(self, app: AppTest) -> AppTest:
        app.run()
        app.file_uploader[0].upload(SAMPLE_CSV.name, SAMPLE_CSV.read_bytes(), "text/csv")
        app.run()
        return app

    def test_given_phase5_spec_when_requirements_are_reviewed_then_plotly_and_aggrid_are_declared(self) -> None:
        requirements_text = REQUIREMENTS_FILE.read_text(encoding="utf-8")

        self.assertIn(
            "plotly",
            requirements_text,
            "Phase 5 should declare Plotly in requirements.txt for the dashboard chart migration.",
        )
        self.assertIn(
            "streamlit-aggrid",
            requirements_text,
            "Phase 5 should declare streamlit-aggrid in requirements.txt for interactive data tables.",
        )

    def test_given_non_empty_dataframe_block_when_render_dataframe_block_runs_then_aggrid_is_used(self) -> None:
        streamlit_app = self.load_module(STREAMLIT_APP_MODULE_PATH, "phase5_streamlit_grid")
        dataframe = pd.DataFrame([{"Queue": "KHD - Level I", "Tickets": 3, "Share": 60.0}])

        self.assertTrue(
            hasattr(streamlit_app, "AgGrid"),
            "Phase 5 should import the AgGrid entrypoint into streamlit_app.py for interactive table rendering.",
        )

        with patch.object(streamlit_app, "AgGrid") as aggrid_mock, patch.object(streamlit_app.st, "dataframe") as dataframe_mock:
            streamlit_app.render_dataframe_block("Queue Distribution", dataframe, "No rows available.")

        aggrid_mock.assert_called_once()
        dataframe_mock.assert_not_called()

    def test_given_distribution_table_when_render_table_and_chart_runs_then_plotly_is_used_instead_of_altair(self) -> None:
        streamlit_app = self.load_module(STREAMLIT_APP_MODULE_PATH, "phase5_streamlit_plotly")
        dataframe = pd.DataFrame(
            [
                {"Queue": "KHD - Level I", "Tickets": 5, "Share": 50.0},
                {"Queue": "KHD - Level II", "Tickets": 5, "Share": 50.0},
            ]
        )

        with patch.object(streamlit_app.st, "plotly_chart") as plotly_chart_mock, patch.object(streamlit_app.st, "altair_chart") as altair_chart_mock:
            streamlit_app.render_table_and_chart("Queue Distribution", dataframe, "Queue")

        plotly_chart_mock.assert_called_once()
        altair_chart_mock.assert_not_called()

    def test_given_customer_mode_when_csv_is_uploaded_then_sla_and_danger_zone_tabs_are_available_without_raw_preview(self) -> None:
        app = self.make_app()
        self.upload_sample_csv(app)

        tab_labels = [tab.label for tab in app.tabs]
        visible_text = []
        for collection_name in ("markdown", "text", "info", "success", "warning", "error", "caption", "title", "header", "subheader"):
            for item in getattr(app, collection_name):
                visible_text.append(str(getattr(item, "value", "")))
        joined_text = "\n".join(visible_text)

        self.assertIn(
            "Overall SLA Compliance",
            joined_text,
            "Customer mode should still surface the SLA review section after the Phase 5 dashboard overhaul.",
        )
        self.assertIn(
            "Repeat Contacts",
            joined_text,
            "Customer mode should still surface the danger-zone review content after the Phase 5 dashboard overhaul.",
        )
        self.assertNotIn(
            "Completed Tickets",
            tab_labels,
            "Phase 5 should preserve the partner-safe customer surface while reorganizing the dashboard.",
        )


if __name__ == "__main__":
    unittest.main()
