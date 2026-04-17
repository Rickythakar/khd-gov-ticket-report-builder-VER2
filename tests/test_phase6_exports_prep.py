from __future__ import annotations

import copy
import importlib.util
import os
import re
import sys
import tempfile
import unittest
import warnings
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import pandas as pd

from validators import validate_and_prepare_dataframe


RUN_PHASE6_PREP = os.getenv("RUN_PHASE6_PREP") == "1"
REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_MODULE_PATH = REPO_ROOT / "config.py"
EXCEL_BUILDER_MODULE_PATH = REPO_ROOT / "excel_builder.py"
PDF_BUILDER_MODULE_PATH = REPO_ROOT / "pdf_builder.py"
SERVER_MODULE_PATH = REPO_ROOT / "server.py"
SETTINGS_MODULE_PATH = REPO_ROOT / "settings.py"
UTILS_MODULE_PATH = REPO_ROOT / "utils.py"
SAMPLE_CSV = REPO_ROOT / "sample_input.csv"


@unittest.skipUnless(RUN_PHASE6_PREP, "Phase 6 prep suite; set RUN_PHASE6_PREP=1 to activate during export extension work.")
class Phase6ExportsPrepTests(unittest.TestCase):
    """Red-suite prep for the Phase 6 Excel and PDF extension work."""

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

    def customer_settings(self) -> dict:
        settings = self.load_module(SETTINGS_MODULE_PATH, "phase6_settings_customer")
        config = copy.deepcopy(settings.DEFAULT_SETTINGS)
        config["mode"] = settings.MODE_CUSTOMER
        return config

    def internal_settings(self) -> dict:
        settings = self.load_module(SETTINGS_MODULE_PATH, "phase6_settings_internal")
        config = copy.deepcopy(settings.DEFAULT_SETTINGS)
        config["mode"] = settings.MODE_INTERNAL
        config["noise_filter"]["hide_spam"] = False
        config["noise_filter"]["hide_sync_errors"] = False
        return config

    def build_workbook_bytes_direct(self, *, report_mode: str, settings: dict, module_suffix: str) -> bytes:
        config = self.load_module(CONFIG_MODULE_PATH, f"phase6_config_{module_suffix}")
        excel_builder = self.load_module(EXCEL_BUILDER_MODULE_PATH, f"phase6_excel_builder_{module_suffix}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            request = excel_builder.ReportRequest(
                dataframe=self.prepared_df(),
                report_title=f"Phase 6 {module_suffix} Workbook",
                logo_path=config.DEFAULT_LOGO_PATH,
                output_path=Path(tmp_dir) / f"{module_suffix}.xlsx",
                partner_name="Acme",
                date_range="March 2026",
                report_mode=report_mode,
                settings=settings,
            )
            built_path = excel_builder.ExcelReportBuilder().build_report(request)
            return built_path.read_bytes()

    def workbook_sheet_states(self, workbook_bytes: bytes) -> dict[str, str]:
        with zipfile.ZipFile(BytesIO(workbook_bytes)) as workbook_zip:
            workbook_xml = ET.fromstring(workbook_zip.read("xl/workbook.xml"))
        namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        return {
            sheet.attrib["name"]: sheet.attrib.get("state", "visible")
            for sheet in workbook_xml.findall("main:sheets/main:sheet", namespace)
        }

    def workbook_sheet_strings(self, workbook_bytes: bytes, sheet_name: str) -> list[str]:
        main_ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        rels_ns = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}
        rel_id_key = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

        with zipfile.ZipFile(BytesIO(workbook_bytes)) as workbook_zip:
            workbook_xml = ET.fromstring(workbook_zip.read("xl/workbook.xml"))
            rels_xml = ET.fromstring(workbook_zip.read("xl/_rels/workbook.xml.rels"))
            rel_targets = {
                rel.attrib["Id"]: rel.attrib["Target"]
                for rel in rels_xml.findall("rel:Relationship", rels_ns)
            }

            worksheet_target = None
            for sheet in workbook_xml.findall("main:sheets/main:sheet", main_ns):
                if sheet.attrib["name"] == sheet_name:
                    worksheet_target = rel_targets.get(sheet.attrib[rel_id_key])
                    break

            self.assertIsNotNone(worksheet_target, f"Expected workbook to contain a {sheet_name!r} sheet.")

            shared_strings: list[str] = []
            if "xl/sharedStrings.xml" in workbook_zip.namelist():
                shared_xml = ET.fromstring(workbook_zip.read("xl/sharedStrings.xml"))
                for item in shared_xml.findall("main:si", main_ns):
                    shared_strings.append("".join(text.text or "" for text in item.iterfind(".//main:t", main_ns)))

            worksheet_xml = ET.fromstring(workbook_zip.read(f"xl/{worksheet_target}"))
            strings: list[str] = []
            for cell in worksheet_xml.findall(".//main:c", main_ns):
                cell_type = cell.attrib.get("t")
                if cell_type == "s":
                    raw_index = cell.findtext("main:v", default="", namespaces=main_ns)
                    if raw_index:
                        strings.append(shared_strings[int(raw_index)])
                elif cell_type == "inlineStr":
                    strings.append("".join(text.text or "" for text in cell.iterfind(".//main:t", main_ns)))
            return strings

    def count_pdf_pages(self, pdf_bytes: bytes) -> int:
        return len(re.findall(rb"/Type\s*/Page\b", pdf_bytes))

    def build_artifacts(self, *, report_mode: str, settings: dict, module_suffix: str):
        utils = self.load_module(UTILS_MODULE_PATH, f"phase6_utils_{module_suffix}")
        return utils.build_report_artifacts(
            self.prepared_df(),
            report_mode=report_mode,
            settings=settings,
        )

    def capture_pdf_titles(self, *, report_mode: str, settings: dict, module_suffix: str) -> tuple[list[str], bytes]:
        artifacts = self.build_artifacts(report_mode=report_mode, settings=settings, module_suffix=f"artifacts_{module_suffix}")
        pdf_builder = self.load_module(PDF_BUILDER_MODULE_PATH, f"phase6_pdf_builder_{module_suffix}")
        captured_titles: list[str] = []
        original = pdf_builder._draw_panel_title

        def capture(draw, rect, title, font, fill="#123D62", **kwargs):
            captured_titles.append(title)
            return original(draw, rect, title, font, fill, **kwargs)

        with patch.object(pdf_builder, "_draw_panel_title", side_effect=capture):
            pdf_bytes = pdf_builder.ExecutivePdfSnapshotBuilder().build_pdf_bytes(
                report_title=f"Phase 6 {module_suffix} Snapshot",
                partner_name="Acme",
                date_range="March 2026",
                artifacts=artifacts,
                logo_bytes=None,
            )

        return captured_titles, pdf_bytes

    def export_workbook_via_server(self, *, settings: dict, module_suffix: str):
        config = self.load_module(CONFIG_MODULE_PATH, f"phase6_server_config_{module_suffix}")
        server = self.load_module(SERVER_MODULE_PATH, f"phase6_server_{module_suffix}")
        utils = self.load_module(UTILS_MODULE_PATH, f"phase6_server_utils_{module_suffix}")
        report_mode = config.REPORT_MODE_INTERNAL if settings.get("mode") == "internal" else config.REPORT_MODE_CUSTOMER
        prepared_df = self.prepared_df()

        server._state["prepared_df"] = prepared_df
        server._state["settings"] = settings
        server._state["artifacts"] = utils.build_report_artifacts(prepared_df, report_mode=report_mode, settings=settings)
        server._state["partner_name"] = "Acme"
        server._state["date_range"] = "March 2026"
        server._state["report_title"] = "Phase 6 Server Export"
        server._state["output_filename"] = "phase6_server_export"
        server._state["error"] = ""

        client = TestClient(server.app)
        return client.get("/export/workbook")

    def test_given_internal_builder_when_workbook_is_built_then_hidden_technician_review_sheet_still_exists(self) -> None:
        config = self.load_module(CONFIG_MODULE_PATH, "phase6_config_internal_control")
        workbook_bytes = self.build_workbook_bytes_direct(
            report_mode=config.REPORT_MODE_INTERNAL,
            settings=self.internal_settings(),
            module_suffix="internal_control",
        )

        sheet_states = self.workbook_sheet_states(workbook_bytes)

        self.assertEqual(
            sheet_states.get("Technician Review"),
            "hidden",
            "Phase 6 should preserve the hidden internal Technician Review sheet while extending the workbook.",
        )

    def test_given_customer_builder_when_workbook_is_built_then_sla_compliance_sheet_contains_targets_and_breach_detail(self) -> None:
        config = self.load_module(CONFIG_MODULE_PATH, "phase6_config_customer_workbook")
        workbook_bytes = self.build_workbook_bytes_direct(
            report_mode=config.REPORT_MODE_CUSTOMER,
            settings=self.customer_settings(),
            module_suffix="customer_workbook",
        )

        sheet_states = self.workbook_sheet_states(workbook_bytes)

        self.assertEqual(
            sheet_states.get("SLA Compliance"),
            "visible",
            "Phase 6 should add a visible SLA Compliance sheet to customer workbooks.",
        )

        sheet_strings = self.workbook_sheet_strings(workbook_bytes, "SLA Compliance")
        joined = "\n".join(sheet_strings)
        self.assertIn("SLA Targets", joined)
        self.assertIn("Compliance", joined)
        self.assertIn("Breach", joined)

    def test_given_internal_server_export_when_workbook_endpoint_is_called_then_mode_and_settings_flow_into_the_generated_workbook(self) -> None:
        response = self.export_workbook_via_server(
            settings=self.internal_settings(),
            module_suffix="internal_endpoint",
        )

        self.assertEqual(response.status_code, 200)
        sheet_states = self.workbook_sheet_states(response.content)

        self.assertEqual(
            sheet_states.get("Technician Review"),
            "hidden",
            "The live FastAPI workbook export should honor internal mode and keep the hidden Technician Review sheet.",
        )
        self.assertEqual(
            sheet_states.get("SLA Compliance"),
            "visible",
            "The live FastAPI workbook export should include the new SLA Compliance sheet once Phase 6 lands.",
        )

    def test_given_internal_pdf_when_snapshot_is_built_then_it_still_renders_a_diagnostics_page_and_the_technician_panel(self) -> None:
        config = self.load_module(CONFIG_MODULE_PATH, "phase6_config_internal_pdf")
        titles, pdf_bytes = self.capture_pdf_titles(
            report_mode=config.REPORT_MODE_INTERNAL,
            settings=self.internal_settings(),
            module_suffix="internal_pdf",
        )

        self.assertGreaterEqual(self.count_pdf_pages(pdf_bytes), 3)
        self.assertTrue(
            any(title in {"Technician Scorecards", "TELEMETRY"} for title in titles),
            "Phase 6 should preserve the internal technician diagnostics page while extending the PDF snapshot.",
        )

    def test_given_customer_pdf_when_snapshot_is_built_then_sla_and_resolution_panels_are_drawn(self) -> None:
        config = self.load_module(CONFIG_MODULE_PATH, "phase6_config_customer_pdf")
        titles, _ = self.capture_pdf_titles(
            report_mode=config.REPORT_MODE_CUSTOMER,
            settings=self.customer_settings(),
            module_suffix="customer_pdf",
        )

        self.assertTrue(
            any("SLA" in title for title in titles),
            "Phase 6 should add a dedicated SLA Compliance panel to the customer PDF snapshot.",
        )
        self.assertTrue(
            any("RESOLUTION" in title.upper() for title in titles),
            "Phase 6 should add a dedicated Resolution Time panel or callout block to the customer PDF snapshot.",
        )


if __name__ == "__main__":
    unittest.main()
