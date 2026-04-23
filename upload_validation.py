from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from phone_schema_reference import (
    PHONE_SOURCE_SCHEMA,
    POWER_BI_PHONE_REQUIRED_SOURCE_COLUMNS,
    POWER_BI_PHONE_TO_CANONICAL_MAP,
)
from schema_reference import (
    POWER_BI_REQUIRED_SOURCE_COLUMNS,
    POWER_BI_TO_CANONICAL_MAP,
)
from validators import (
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

CANONICAL_TICKET_SCHEMA_GROUPS: dict[str, tuple[str, ...]] = {
    "ticket_id": ("Ticket Number", "Task Number"),
    "company": ("Company", "Account Name"),
    "created": ("Created", "Create Timestamp", "Created Date"),
    "issue_type": ("Issue Type",),
    "queue": ("Queue", "Queue Name", "First Queue Name"),
    "source": ("Source",),
}


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
        "my value",
        "khd ticket number",
        "msp ticket number",
        "partner",
        "client",
    }
    if normalized_columns & power_bi_signals:
        return "power_bi"

    phone_signals = {
        "call id",
        "call timestamp",
        "queue wait time sec",
        "service level category",
        "answered",
        "abandoned",
    }
    if normalized_columns & phone_signals:
        return "power_bi_phone"

    autotask_signals = {
        "task number",
        "parent task number",
        "parent account name",
        "account name",
        "escalation events",
    }
    if normalized_columns & autotask_signals:
        return "autotask"

    return "unknown"


def _resolve_group_match(
    normalized_columns: dict[str, str],
    candidates: tuple[str, ...],
) -> str | None:
    for candidate in candidates:
        original_name = normalized_columns.get(normalize_header(candidate))
        if original_name:
            return original_name
    return None


def validate_supported_upload_schema(dataframe: pd.DataFrame) -> SupportedUploadValidationResult:
    """Check whether a raw upload matches the supported created-ticket schema before prep/analytics."""
    alias_lookup = build_alias_lookup()
    mapped_columns: dict[str, str] = {}
    matched_required: set[str] = set()
    normalized_columns = {normalize_header(column): str(column) for column in list(dataframe.columns)}
    canonical_group_matches: dict[str, str] = {}

    for original_name in list(dataframe.columns):
        canonical_name = alias_lookup.get(normalize_header(original_name))
        if canonical_name:
            mapped_columns[str(original_name)] = canonical_name
            if canonical_name in CREATED_TICKET_SCHEMA_REQUIRED_COLUMNS:
                matched_required.add(canonical_name)

    for group_name, candidates in CANONICAL_TICKET_SCHEMA_GROUPS.items():
        matched_column = _resolve_group_match(normalized_columns, candidates)
        if matched_column:
            canonical_group_matches[group_name] = matched_column

    missing_required = [column for column in CREATED_TICKET_SCHEMA_REQUIRED_COLUMNS if column not in matched_required]
    canonical_group_missing = [
        group_name
        for group_name in CANONICAL_TICKET_SCHEMA_GROUPS
        if group_name not in canonical_group_matches
    ]
    power_bi_missing = [
        column_name
        for column_name in POWER_BI_REQUIRED_SOURCE_COLUMNS
        if normalize_header(column_name) not in normalized_columns
    ]
    phone_missing = [
        column_name
        for column_name in POWER_BI_PHONE_REQUIRED_SOURCE_COLUMNS
        if normalize_header(column_name) not in normalized_columns
    ]
    power_bi_mapped_columns = {
        normalized_columns[normalize_header(source_name)]: canonical_name
        for source_name, canonical_name in POWER_BI_TO_CANONICAL_MAP.items()
        if normalize_header(source_name) in normalized_columns
    }
    phone_mapped_columns = {
        normalized_columns[normalize_header(source_name)]: canonical_name
        for source_name, canonical_name in POWER_BI_PHONE_TO_CANONICAL_MAP.items()
        if normalize_header(source_name) in normalized_columns
    }

    if not canonical_group_missing:
        matched_canonical_columns = sorted(set(mapped_columns.values()) | set(canonical_group_matches.values()))
        return SupportedUploadValidationResult(
            is_supported=True,
            matched_required_columns=matched_canonical_columns,
            missing_required_columns=[],
            mapped_columns=mapped_columns,
            source_hint=detect_source_hint(dataframe),
            accepted_schema="canonical_created_ticket",
            schema_candidates={
                "canonical_created_ticket": [],
                "power_bi_ticket_export": power_bi_missing,
                PHONE_SOURCE_SCHEMA: phone_missing,
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
                PHONE_SOURCE_SCHEMA: phone_missing,
            },
        )

    if not phone_missing:
        matched_phone_columns = [
            POWER_BI_PHONE_TO_CANONICAL_MAP.get(column_name, column_name)
            for column_name in POWER_BI_PHONE_REQUIRED_SOURCE_COLUMNS
        ]
        return SupportedUploadValidationResult(
            is_supported=True,
            matched_required_columns=matched_phone_columns,
            missing_required_columns=[],
            mapped_columns=phone_mapped_columns,
            source_hint=detect_source_hint(dataframe),
            accepted_schema=PHONE_SOURCE_SCHEMA,
            schema_candidates={
                "canonical_created_ticket": missing_required,
                "power_bi_ticket_export": power_bi_missing,
                PHONE_SOURCE_SCHEMA: [],
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
            "canonical_created_ticket": canonical_group_missing,
            "power_bi_ticket_export": power_bi_missing,
            PHONE_SOURCE_SCHEMA: phone_missing,
        },
    )


def build_unsupported_upload_message(result: SupportedUploadValidationResult) -> str:
    return (
        "Unsupported upload format. Please upload a supported ticket export or phone metrics export."
    )
