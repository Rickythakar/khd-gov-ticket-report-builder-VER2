from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


SETTINGS_PATH = Path(__file__).resolve().parent / "settings.json"

DEFAULT_SETTINGS: dict[str, Any] = {
    "mode": "customer",
    "export": {
        "include_pdf": True,
        "include_workbook": True,
    },
    "sla_targets": {
        "Critical": 60,
        "High": 240,
        "Medium": 480,
        "Low": 1440,
        "None": 1440,
    },
    "sla_queue_overrides": {},
    "expert_mode": False,
    "noise_filter": {
        "hide_spam": True,
        "hide_sync_errors": True,
    },
    "danger_zone_threshold": 3,
    "ai": {
        "enabled": False,
        "provider": "azure_openai",
        "endpoint": "",
        "base_url": "",
        "api_key": "",
        "organization": "",
        "project": "",
        "deployment": "gpt-5.4",
        "reasoning_effort": "high",
        "api_version": "2026-02-01",
        "max_calls_per_run": 50,
        "features": {
            "sentiment": True,
            "categorization": True,
            "executive_summary": True,
            "anomaly_narration": True,
        },
        "tone": "formal",
        "custom_instructions": "",
    },
}

MODE_CUSTOMER = "customer"
MODE_INTERNAL = "internal"
VALID_MODES = {MODE_CUSTOMER, MODE_INTERNAL}


def _deep_merge(defaults: dict, overrides: dict) -> dict:
    result = defaults.copy()
    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_settings() -> dict[str, Any]:
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                user_settings = json.load(f)
            merged = _deep_merge(DEFAULT_SETTINGS, user_settings)
            if merged.get("mode") not in VALID_MODES:
                merged["mode"] = DEFAULT_SETTINGS["mode"]
            return merged
        except (json.JSONDecodeError, OSError):
            return copy.deepcopy(DEFAULT_SETTINGS)
    return copy.deepcopy(DEFAULT_SETTINGS)


def save_settings(settings: dict[str, Any]) -> None:
    clean = {}
    for key, value in settings.items():
        if key in DEFAULT_SETTINGS:
            clean[key] = value
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)


def reset_settings() -> dict[str, Any]:
    save_settings(DEFAULT_SETTINGS)
    return copy.deepcopy(DEFAULT_SETTINGS)


def get_sla_target_minutes(settings: dict[str, Any], priority: str, queue: str = "") -> int:
    queue_overrides = settings.get("sla_queue_overrides", {})
    if queue and queue in queue_overrides:
        return int(queue_overrides[queue])
    sla_targets = settings.get("sla_targets", DEFAULT_SETTINGS["sla_targets"])
    return int(sla_targets.get(priority, sla_targets.get("None", 1440)))


def is_internal_mode(settings: dict[str, Any]) -> bool:
    return settings.get("mode") == MODE_INTERNAL


def is_noise_hidden(settings: dict[str, Any]) -> bool:
    noise = settings.get("noise_filter", {})
    return noise.get("hide_spam", True) or noise.get("hide_sync_errors", True)
