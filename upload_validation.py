from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from validators import (
    POWER_BI_REQUIRED_SOURCE_COLUMNS,
    POWER_BI_TO_CANONICAL_MAP,
    build_alias_lookup,
    normalize_header,
)


CREATED_TICKET_SCHEMA_REQUIRED_COLUMNS = [
    "Ticket Number",
    "Title",
    "Company",
    "Created",
    "Complete Date",
    "Issue Type",
    "Queue",
    "Escalation Reason",
    "Source",
]


@dataclass
class SupportedUploadValidationResult:
    is_supported: bool
    matched_required_columns: list[str]
    missing_required_columns: list[str]
    mapped_columns: dict[str, str]
    source_hint: str = "unknown"
    accepted_schema: str = "unknown"
    schema_candidates: dict[str, list[str]] = field(default_factory=dict)


def detect_source_hint(dataframe: pd.DataFrame) -> str:
    """Return a lightweight source hint without making it part of the acceptance criteria."""
    normalized_columns = {normalize_header(column) for column in list(dataframe.columns)}

    power_bi_signals = {
        "khd ticket number",
        "msp ticket number",
        "pickup slo status",
        "take back count",
        "queue name",
        "created hour",
    }
    if normalized_columns & power_bi_signals:
        return "power_bi"

    autotask_signals = {
        "ticket #",
        "service ticket number",
        "nexus ticket #",
    }
    if normalized_columns & autotask_signals:
        return "autotask"

    return "unknown"


def validate_supported_upload_schema(dataframe: pd.DataFrame) -> SupportedUploadValidationResult:
    """Check whether a raw upload matches the supported created-ticket schema before prep/analytics."""
    alias_lookup = build_alias_lookup()
    mapped_columns: dict[str, str] = {}
    matched_required: set[str] = set()
    normalized_columns = {normalize_header(column): str(column) for column in list(dataframe.columns)}

    for original_name in list(dataframe.columns):
        canonical_name = alias_lookup.get(normalize_header(original_name))
        if canonical_name:
            mapped_columns[str(original_name)] = canonical_name
            if canonical_name in CREATED_TICKET_SCHEMA_REQUIRED_COLUMNS:
                matched_required.add(canonical_name)

    missing_required = [column for column in CREATED_TICKET_SCHEMA_REQUIRED_COLUMNS if column not in matched_required]
    power_bi_missing = [
        column_name
        for column_name in POWER_BI_REQUIRED_SOURCE_COLUMNS
        if normalize_header(column_name) not in normalized_columns
    ]
    power_bi_mapped_columns = {
        normalized_columns[normalize_header(source_name)]: canonical_name
        for source_name, canonical_name in POWER_BI_TO_CANONICAL_MAP.items()
        if normalize_header(source_name) in normalized_columns
    }

    if not missing_required:
        return SupportedUploadValidationResult(
            is_supported=True,
            matched_required_columns=sorted(matched_required),
            missing_required_columns=[],
            mapped_columns=mapped_columns,
            source_hint=detect_source_hint(dataframe),
            accepted_schema="canonical_created_ticket",
            schema_candidates={
                "canonical_created_ticket": [],
                "power_bi_ticket_export": power_bi_missing,
            },
        )

    if not power_bi_missing:
        matched_power_bi_columns = [
            POWER_BI_TO_CANONICAL_MAP.get(column_name, column_name)
            for column_name in POWER_BI_REQUIRED_SOURCE_COLUMNS
        ]
        return SupportedUploadValidationResult(
            is_supported=True,
            matched_required_columns=matched_power_bi_columns,
            missing_required_columns=[],
            mapped_columns=power_bi_mapped_columns,
            source_hint=detect_source_hint(dataframe),
            accepted_schema="power_bi_ticket_export",
            schema_candidates={
                "canonical_created_ticket": missing_required,
                "power_bi_ticket_export": [],
            },
        )

    return SupportedUploadValidationResult(
        is_supported=False,
        matched_required_columns=sorted(matched_required),
        missing_required_columns=missing_required,
        mapped_columns=mapped_columns,
        source_hint=detect_source_hint(dataframe),
        accepted_schema="unknown",
        schema_candidates={
            "canonical_created_ticket": missing_required,
            "power_bi_ticket_export": power_bi_missing,
        },
    )


def build_unsupported_upload_message(result: SupportedUploadValidationResult) -> str:
    canonical_missing = result.schema_candidates.get("canonical_created_ticket", result.missing_required_columns)
    power_bi_missing = result.schema_candidates.get("power_bi_ticket_export", [])
    if result.source_hint == "power_bi" or (power_bi_missing and len(power_bi_missing) <= len(canonical_missing)):
        missing = ", ".join(power_bi_missing)
        return (
            "The uploaded CSV does not match a supported created-ticket export format. "
            f"Missing required Power BI ticket export columns: {missing}. "
            "Supported uploads are either the canonical created-ticket export or the mapped Power BI ticket export."
        )

    missing = ", ".join(canonical_missing)
    return (
        "The uploaded CSV does not match a supported created-ticket export format. "
        f"Missing required canonical columns: {missing}. "
        "Supported uploads are either the canonical created-ticket export or the mapped Power BI ticket export."
    )
