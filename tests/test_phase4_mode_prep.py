from __future__ import annotations

import copy
import importlib.util
import inspect
import json
import os
import re
import sys
import unittest
import warnings
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from validators import validate_and_prepare_dataframe


RUN_PHASE4_PREP = os.getenv("RUN_PHASE4_PREP") == "1"
REPO_ROOT = Path(__file__).resolve().parents[1]
APP_FILE = REPO_ROOT / "streamlit_app.py"
CONFIG_MODULE_PATH = REPO_ROOT / "config.py"
PDF_BUILDER_MODULE_PATH = REPO_ROOT / "pdf_builder.py"
SETTINGS_JSON_PATH = REPO_ROOT / "settings.json"
SETTINGS_MODULE_PATH = REPO_ROOT / "settings.py"
STREAMLIT_APP_MODULE_PATH = REPO_ROOT / "streamlit_app.py"
UTILS_MODULE_PATH = REPO_ROOT / "utils.py"
SAMPLE_CSV = REPO_ROOT / "sample_input.csv"


@unittest.skipUnless(RUN_PHASE4_PREP, "Phase 4 prep suite; set RUN_PHASE4_PREP=1 to activate during mode work.")
class Phase4ModePrepTests(unittest.TestCase):
    """Red-suite prep for the Phase 4 internal versus customer mode work."""

    @classmethod
    def setUpClass(cls) -> None:
        warnings.filterwarnings(
            "ignore",
            message="Could not infer format, so each element will be parsed individually",
            category=UserWarning,
        )

    def setUp(self) -> None:
        self._original_settings_json = SETTINGS_JSON_PATH.read_text(encoding="utf-8") if SETTINGS_JSON_PATH.exists() else None
        settings = self.load_module(SETTINGS_MODULE_PATH, "phase4_settings_setup")
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

    def set_mode(self, app: AppTest, mode: str) -> AppTest:
        app.run()
        app.radio[0].set_value(mode)
        app.run()
        return app

    def prepared_df(self) -> pd.DataFrame:
        raw_df = pd.read_csv(SAMPLE_CSV)
        return validate_and_prepare_dataframe(raw_df).dataframe

    def logo_bytes(self) -> bytes:
        streamlit_app = self.load_module(STREAMLIT_APP_MODULE_PATH, "phase4_streamlit_logo")
        self.assertTrue(streamlit_app.DEFAULT_LOGO_PATH.exists(), "Expected bundled default logo for export tests.")
        return streamlit_app.DEFAULT_LOGO_PATH.read_bytes()

    def customer_settings(self) -> dict:
        settings = self.load_module(SETTINGS_MODULE_PATH, "phase4_settings_customer")
        config = copy.deepcopy(settings.DEFAULT_SETTINGS)
        config["mode"] = settings.MODE_CUSTOMER
        return config

    def internal_settings(self) -> dict:
        settings = self.load_module(SETTINGS_MODULE_PATH, "phase4_settings_internal")
        config = copy.deepcopy(settings.DEFAULT_SETTINGS)
        config["mode"] = settings.MODE_INTERNAL
        config["noise_filter"]["hide_spam"] = False
        config["noise_filter"]["hide_sync_errors"] = False
        return config

    def workbook_sheet_states(self, workbook_bytes: bytes) -> dict[str, str]:
        with zipfile.ZipFile(BytesIO(workbook_bytes)) as workbook_zip:
            workbook_xml = ET.fromstring(workbook_zip.read("xl/workbook.xml"))
        namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        return {
            sheet.attrib["name"]: sheet.attrib.get("state", "visible")
            for sheet in workbook_xml.findall("main:sheets/main:sheet", namespace)
        }

    def count_pdf_pages(self, pdf_bytes: bytes) -> int:
        return len(re.findall(rb"/Type\s*/Page\b", pdf_bytes))

    def test_given_customer_mode_when_report_artifacts_are_built_then_full_metrics_remain_available_for_export_layers(self) -> None:
        config = self.load_module(CONFIG_MODULE_PATH, "phase4_config_customer")
        utils = self.load_module(UTILS_MODULE_PATH, "phase4_utils_customer")

        artifacts = utils.build_report_artifacts(
            self.prepared_df(),
            report_mode=config.REPORT_MODE_CUSTOMER,
            settings=self.customer_settings(),
        )

        self.assertEqual(artifacts.report_mode, config.REPORT_MODE_CUSTOMER)
        self.assertIsInstance(
            artifacts.technician_scorecards,
            pd.DataFrame,
            "Phase 4 should keep technician scorecards in the artifacts payload even when customer mode hides them in the UI.",
        )
        self.assertIsNotNone(
            artifacts.noise_metrics,
            "Phase 4 mode filtering should happen at the UI/export layer, not by stripping metrics out of the artifacts payload.",
        )

    def test_given_customer_mode_when_a_csv_is_analyzed_then_internal_only_tabs_are_hidden(self) -> None:
        app = self.make_app()
        self.upload_sample_csv(app)

        tab_labels = [tab.label for tab in app.tabs]

        self.assertNotIn(
            "Technicians",
            tab_labels,
            "Customer mode should not render the internal technician review tab.",
        )
        self.assertNotIn(
            "Raw Preview",
            tab_labels,
            "Customer mode should hide the raw-preview tab from partner-safe workflows.",
        )

    def test_given_internal_mode_when_a_csv_is_analyzed_then_technicians_and_raw_preview_tabs_are_visible(self) -> None:
        settings = self.load_module(SETTINGS_MODULE_PATH, "phase4_settings_mode")
        app = self.make_app()
        self.set_mode(app, settings.MODE_INTERNAL)
        self.upload_sample_csv(app)

        tab_labels = [tab.label for tab in app.tabs]
        visible_text = []
        for collection_name in ("markdown", "text", "info", "success", "warning", "error", "caption", "title", "header", "subheader"):
            for item in getattr(app, collection_name):
                visible_text.append(str(getattr(item, "value", "")))
        joined_text = "\n".join(visible_text)

        self.assertIn(
            "Technician Scorecards",
            joined_text,
            "Internal mode should expose technician review content for QA and coaching.",
        )
        self.assertIn(
            "Completed Tickets",
            tab_labels,
            "Internal mode should retain the raw-preview tabs for diagnostics and drill-in.",
        )

    def test_given_mode_specific_exports_when_workbook_is_built_then_only_internal_mode_adds_hidden_technician_review_sheet(self) -> None:
        config = self.load_module(CONFIG_MODULE_PATH, "phase4_config_workbook")
        settings = self.load_module(SETTINGS_MODULE_PATH, "phase4_settings_workbook")
        streamlit_app = self.load_module(STREAMLIT_APP_MODULE_PATH, "phase4_streamlit_workbook")

        signature = inspect.signature(streamlit_app.build_workbook_bytes)
        self.assertIn(
            "report_mode",
            signature.parameters,
            "Workbook export needs a report_mode input before Phase 4 can emit different sheets for customer and internal workflows.",
        )
        self.assertIn(
            "settings",
            signature.parameters,
            "Workbook export needs the persisted settings payload before Phase 4 can emit mode-specific sheets.",
        )

        prepared_df = self.prepared_df()
        logo_bytes = self.logo_bytes()
        customer_workbook = streamlit_app.build_workbook_bytes(
            prepared_df=prepared_df,
            report_title="Phase 4 Customer Workbook",
            logo_bytes=logo_bytes,
            output_filename="phase4_customer.xlsx",
            partner_name="Acme",
            date_range="March 2026",
            report_mode=config.REPORT_MODE_CUSTOMER,
            settings=self.customer_settings(),
        )
        internal_workbook = streamlit_app.build_workbook_bytes(
            prepared_df=prepared_df,
            report_title="Phase 4 Internal Workbook",
            logo_bytes=logo_bytes,
            output_filename="phase4_internal.xlsx",
            partner_name="Acme",
            date_range="March 2026",
            report_mode=config.REPORT_MODE_INTERNAL,
            settings=self.internal_settings(),
        )

        customer_sheets = self.workbook_sheet_states(customer_workbook)
        internal_sheets = self.workbook_sheet_states(internal_workbook)

        self.assertNotIn(
            "Technician Review",
            customer_sheets,
            "Customer workbooks should not expose the internal technician review sheet.",
        )
        self.assertEqual(
            internal_sheets.get("Technician Review"),
            "hidden",
            "Internal workbook export should add a hidden Technician Review sheet for internal-only analysis.",
        )

    def test_given_customer_and_internal_artifacts_when_pdf_snapshot_is_built_then_internal_mode_adds_a_third_page(self) -> None:
        config = self.load_module(CONFIG_MODULE_PATH, "phase4_config_pdf")
        pdf_builder = self.load_module(PDF_BUILDER_MODULE_PATH, "phase4_pdf_builder")
        utils = self.load_module(UTILS_MODULE_PATH, "phase4_utils_pdf")

        prepared_df = self.prepared_df()
        customer_artifacts = utils.build_report_artifacts(
            prepared_df,
            report_mode=config.REPORT_MODE_CUSTOMER,
            settings=self.customer_settings(),
        )
        internal_artifacts = utils.build_report_artifacts(
            prepared_df,
            report_mode=config.REPORT_MODE_INTERNAL,
            settings=self.internal_settings(),
        )

        builder = pdf_builder.ExecutivePdfSnapshotBuilder()
        customer_pdf = builder.build_pdf_bytes(
            report_title="Phase 4 Customer Snapshot",
            partner_name="Acme",
            date_range="March 2026",
            artifacts=customer_artifacts,
            logo_bytes=None,
        )
        internal_pdf = builder.build_pdf_bytes(
            report_title="Phase 4 Internal Snapshot",
            partner_name="Acme",
            date_range="March 2026",
            artifacts=internal_artifacts,
            logo_bytes=None,
        )

        self.assertEqual(
            self.count_pdf_pages(internal_pdf),
            self.count_pdf_pages(customer_pdf) + 1,
            "Internal PDF exports should preserve one extra diagnostics page beyond the customer snapshot.",
        )


if __name__ == "__main__":
    unittest.main()
