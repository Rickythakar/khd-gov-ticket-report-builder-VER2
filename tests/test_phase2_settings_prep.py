from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


RUN_PHASE2_PREP = os.getenv("RUN_PHASE2_PREP") == "1"
REPO_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_MODULE_PATH = REPO_ROOT / "settings.py"
SETTINGS_JSON_PATH = REPO_ROOT / "settings.json"
APP_FILE = REPO_ROOT / "streamlit_app.py"


@unittest.skipUnless(RUN_PHASE2_PREP, "Phase 2 prep suite; set RUN_PHASE2_PREP=1 to activate during settings work.")
class Phase2SettingsPrepTests(unittest.TestCase):
    """Red-suite prep for the Phase 2 settings system."""

    def setUp(self) -> None:
        self._original_settings_json = SETTINGS_JSON_PATH.read_text(encoding="utf-8") if SETTINGS_JSON_PATH.exists() else None

    def tearDown(self) -> None:
        if self._original_settings_json is None:
            if SETTINGS_JSON_PATH.exists():
                SETTINGS_JSON_PATH.unlink()
        else:
            SETTINGS_JSON_PATH.write_text(self._original_settings_json, encoding="utf-8")

    def load_settings_module(self):
        self.assertTrue(SETTINGS_MODULE_PATH.exists(), "Phase 2 expects a settings.py module at the repo root.")
        spec = importlib.util.spec_from_file_location("phase2_settings_module", SETTINGS_MODULE_PATH)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_given_missing_settings_file_when_load_settings_then_defaults_are_returned(self) -> None:
        settings = self.load_settings_module()

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_settings_path = Path(tmp_dir) / "settings.json"
            with patch.object(settings, "SETTINGS_PATH", temp_settings_path):
                loaded = settings.load_settings()

        self.assertEqual(loaded, settings.DEFAULT_SETTINGS)

    def test_given_partial_overrides_when_load_settings_then_defaults_are_deep_merged(self) -> None:
        settings = self.load_settings_module()

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_settings_path = Path(tmp_dir) / "settings.json"
            temp_settings_path.write_text(
                (
                    "{\n"
                    '  "mode": "internal",\n'
                    '  "sla_targets": {"Critical": 30},\n'
                    '  "export": {"include_pdf": false}\n'
                    "}\n"
                ),
                encoding="utf-8",
            )
            with patch.object(settings, "SETTINGS_PATH", temp_settings_path):
                loaded = settings.load_settings()

        self.assertEqual(loaded["mode"], "internal")
        self.assertEqual(loaded["sla_targets"]["Critical"], 30)
        self.assertEqual(loaded["export"]["include_pdf"], False)
        self.assertEqual(
            loaded["sla_targets"]["High"],
            settings.DEFAULT_SETTINGS["sla_targets"]["High"],
            "Unspecified SLA targets should retain their defaults after deep merge.",
        )
        self.assertEqual(
            loaded["export"]["include_workbook"],
            settings.DEFAULT_SETTINGS["export"]["include_workbook"],
            "Export settings should deep-merge rather than overwrite the whole export block.",
        )

    def test_given_saved_settings_when_reloaded_then_persisted_values_are_returned(self) -> None:
        settings = self.load_settings_module()

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_settings_path = Path(tmp_dir) / "settings.json"
            with patch.object(settings, "SETTINGS_PATH", temp_settings_path):
                settings.save_settings(
                    {
                        "mode": "internal",
                        "export": {
                            "include_pdf": False,
                            "include_workbook": True,
                        },
                        "noise_filter": {
                            "hide_spam": False,
                            "hide_sync_errors": True,
                        },
                    }
                )
                loaded = settings.load_settings()

        self.assertEqual(loaded["mode"], "internal")
        self.assertEqual(loaded["export"]["include_pdf"], False)
        self.assertEqual(loaded["noise_filter"]["hide_spam"], False)

    def test_given_changed_mode_when_reset_defaults_is_clicked_then_ui_and_file_return_to_defaults(self) -> None:
        settings = self.load_settings_module()
        internal_settings = settings.load_settings()
        internal_settings["mode"] = "internal"
        SETTINGS_JSON_PATH.write_text(json.dumps(internal_settings, indent=2), encoding="utf-8")

        app = AppTest.from_file(str(APP_FILE))
        app.run()

        saved_settings = json.loads(SETTINGS_JSON_PATH.read_text(encoding="utf-8"))
        self.assertEqual(saved_settings["mode"], "internal")
        self.assertEqual(app.radio[0].value, "internal")

        settings.reset_settings()

        app = AppTest.from_file(str(APP_FILE))
        app.run()

        reset_settings = json.loads(SETTINGS_JSON_PATH.read_text(encoding="utf-8"))
        self.assertEqual(reset_settings["mode"], "customer")
        self.assertEqual(
            app.radio[0].value,
            "customer",
            "Reset Defaults should refresh the rendered controls back to the default mode, not just the file on disk.",
        )


if __name__ == "__main__":
    unittest.main()
