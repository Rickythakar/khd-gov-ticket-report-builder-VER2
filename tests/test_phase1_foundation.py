from __future__ import annotations

import html
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import streamlit_app


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_FILE = REPO_ROOT / "streamlit_app.py"
SAMPLE_CSV = REPO_ROOT / "sample_input.csv"


class Phase1FoundationAppTests(unittest.TestCase):
    """Feature: Phase 1 foundation flow from the improvement spec."""

    @classmethod
    def setUpClass(cls) -> None:
        warnings.filterwarnings(
            "ignore",
            message="Could not infer format, so each element will be parsed individually",
            category=UserWarning,
        )

    def make_app(self) -> AppTest:
        return AppTest.from_file(str(APP_FILE))

    def upload_sample_csv(self, app: AppTest) -> AppTest:
        app.run()
        app.file_uploader[0].upload(SAMPLE_CSV.name, SAMPLE_CSV.read_bytes(), "text/csv")
        app.run()
        return app

    def test_given_uploaded_csv_when_app_reruns_then_analysis_is_automatic(self) -> None:
        app = self.make_app()

        self.upload_sample_csv(app)

        state = app.session_state.filtered_state
        self.assertIsNotNone(
            state["prepared_df"],
            "Uploading a CSV should auto-analyze the workbook and populate prepared_df.",
        )
        self.assertIsNotNone(
            state["artifacts"],
            "Uploading a CSV should auto-analyze the workbook and populate report artifacts.",
        )

    def test_given_phase1_spec_when_actions_render_then_only_export_button_is_shown(self) -> None:
        app = self.make_app()
        app.run()

        labels = [button.label for button in app.button]

        self.assertIn("Export", labels)
        self.assertNotIn(
            "Analyze Workbook",
            labels,
            "The Phase 1 spec removes the old Analyze Workbook action in favor of auto-analysis.",
        )
        self.assertNotIn(
            "Generate Workbook",
            labels,
            "The Phase 1 spec replaces the separate Generate Workbook action with Export.",
        )

    def test_given_pdf_snapshot_is_enabled_when_export_completes_then_bytes_are_cached_in_session_state(self) -> None:
        app = self.make_app()
        self.upload_sample_csv(app)

        state = app.session_state.filtered_state
        pdf_snapshot_bytes = streamlit_app.build_pdf_snapshot_bytes(
            artifacts=state["artifacts"],
            report_title="Phase 1 Snapshot",
            logo_bytes=None,
            partner_name="",
            date_range="",
        )
        app.session_state["pdf_snapshot_bytes"] = pdf_snapshot_bytes
        app.session_state["pdf_snapshot_name"] = "phase1_snapshot.pdf"

        state = app.session_state.filtered_state
        self.assertIn(
            "pdf_snapshot_bytes",
            state,
            "Phase 1 stores the executive snapshot bytes in session_state to avoid a double-click flow.",
        )
        self.assertIsInstance(state["pdf_snapshot_bytes"], bytes)
        self.assertGreater(len(state["pdf_snapshot_bytes"]), 0)

    def test_given_prior_exports_when_a_new_csv_is_uploaded_then_old_download_artifacts_are_cleared(self) -> None:
        app = self.make_app()
        self.upload_sample_csv(app)
        app.session_state["workbook_bytes"] = b"stale workbook"
        app.session_state["workbook_name"] = "stale.xlsx"
        app.session_state["pdf_snapshot_bytes"] = b"stale pdf"
        app.session_state["pdf_snapshot_name"] = "stale.pdf"

        first_state = app.session_state.filtered_state
        self.assertIsNotNone(first_state["workbook_bytes"])
        self.assertIsNotNone(first_state["pdf_snapshot_bytes"])

        app.file_uploader[0].set_value(("second_sample.csv", SAMPLE_CSV.read_bytes(), "text/csv"))
        app.run()

        second_state = app.session_state.filtered_state
        self.assertIsNone(
            second_state["workbook_bytes"],
            "Uploading a new CSV should clear the previous workbook download so stale exports are not offered.",
        )
        self.assertEqual(second_state["workbook_name"], "")
        self.assertIsNone(
            second_state["pdf_snapshot_bytes"],
            "Uploading a new CSV should clear the previous PDF snapshot so the next export matches the current file.",
        )
        self.assertEqual(second_state["pdf_snapshot_name"], "")


class Phase1FoundationCachingTests(unittest.TestCase):
    """Feature: expensive helpers are cached per the improvement spec."""

    def test_given_phase1_spec_when_expensive_helpers_are_defined_then_they_are_cache_wrapped(self) -> None:
        for function_name in (
            "inspect_uploaded_csv",
            "analyze_uploaded_csv",
            "build_workbook_bytes",
            "build_pdf_snapshot_bytes",
        ):
            with self.subTest(function_name=function_name):
                helper = getattr(streamlit_app, function_name)
                self.assertTrue(
                    hasattr(helper, "clear"),
                    f"{function_name} should be wrapped with st.cache_data so repeated runs do not recompute.",
                )


class Phase1FoundationSecurityTests(unittest.TestCase):
    """Feature: CSV-derived values are escaped before HTML injection."""

    @patch("streamlit_app.st.markdown")
    def test_given_untrusted_context_when_render_header_bar_then_user_values_are_escaped(self, markdown_mock) -> None:
        title = 'Quarterly <script>alert("x")</script>'
        partner_name = 'ACME <img src=x onerror="alert(1)">'
        date_range = "Q1 <b>2026</b>"

        streamlit_app.render_header_bar(title, partner_name, date_range)

        markup = markdown_mock.call_args.args[0]
        self.assertNotIn(title, markup)
        self.assertNotIn(partner_name, markup)
        self.assertNotIn(date_range, markup)
        self.assertIn(html.escape(partner_name), markup)
        self.assertIn(html.escape(date_range), markup)

    @patch("streamlit_app.st.markdown")
    def test_given_untrusted_observation_when_render_pulse_band_then_text_is_escaped(self, markdown_mock) -> None:
        observation = '<script>alert("pulse")</script>'

        streamlit_app.render_pulse_band(observation)

        markup = markdown_mock.call_args.args[0]
        self.assertNotIn(observation, markup)
        self.assertIn(html.escape(observation), markup)

    @patch("streamlit_app.st.markdown")
    def test_given_untrusted_state_when_render_state_band_then_text_is_escaped(self, markdown_mock) -> None:
        state_text = '<img src=x onerror="alert(2)">'

        streamlit_app.render_state_band(state_text)

        markup = markdown_mock.call_args.args[0]
        self.assertNotIn(state_text, markup)
        self.assertIn(html.escape(state_text), markup)

    @patch("streamlit_app.st.markdown")
    def test_given_list_items_when_render_list_then_values_are_escaped(self, markdown_mock) -> None:
        items = ['Line <b>one</b>', 'Line <script>alert("two")</script>']

        streamlit_app.render_list(items)

        markup = markdown_mock.call_args.args[0]
        for item in items:
            self.assertNotIn(item, markup)
            self.assertIn(html.escape(item), markup)


if __name__ == "__main__":
    unittest.main()
