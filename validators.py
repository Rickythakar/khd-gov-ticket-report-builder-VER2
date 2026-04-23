from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from config import COLUMN_ALIASES, REQUIRED_COLUMNS


class ValidationError(Exception):
    """Raised when app input or CSV contents are not valid for report generation."""


@dataclass
class DataValidationResult:
    dataframe: pd.DataFrame
    column_mapping: dict[str, str]
    missing_columns: list[str]
    source_schema: str = "canonical_created_ticket"
    normalization_notes: list[str] = field(default_factory=list)


POWER_BI_REQUIRED_SOURCE_COLUMNS = [
    "My Value",
    "KHD Ticket Number",
    "Partner",
    "Client",
    "Source",
    "Create Timestamp",
    "Created Date",
    "Task Status",
    "Queue Name",
    "Issue Type",
    "Pickup SLO Status",
]

POWER_BI_OPTIONAL_SOURCE_COLUMNS = [
    "MSP Ticket Number",
    "Timezone",
    "Created Hour",
    "Take Back",
    "Take Back Count",
    "Sub Issue Type",
]

POWER_BI_TO_CANONICAL_MAP: dict[str, str] = {
    "My Value": "Title",
    "KHD Ticket Number": "Ticket Number",
    "MSP Ticket Number": "Nexus Ticket Number",
    "Partner": "Parent Account",
    "Client": "Company",
    "Source": "Source",
    "Task Status": "Status",
    "Queue Name": "Queue",
    "Issue Type": "Issue Type",
    "Sub Issue Type": "Sub-Issue Type",
    "Timezone": "Account Timezone",
    "Take Back": "Take Back Event",
    "Take Back Count": "Take Back Count",
    "Pickup SLO Status": "Pickup SLO Status",
}


def normalize_header(value: str) -> str:
    text = str(value or "").strip().lower()
    for character in ("_", "-", "/", "\\", ".", "(", ")", "[", "]", ":"):
        text = text.replace(character, " ")
    return " ".join(text.split())


def build_alias_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for canonical_name in REQUIRED_COLUMNS:
        lookup[normalize_header(canonical_name)] = canonical_name

    for canonical_name, aliases in COLUMN_ALIASES.items():
        lookup[normalize_header(canonical_name)] = canonical_name
        for alias in aliases:
            lookup[normalize_header(alias)] = canonical_name

    return lookup


def _build_normalized_column_lookup(dataframe: pd.DataFrame) -> dict[str, str]:
    return {normalize_header(column_name): str(column_name) for column_name in list(dataframe.columns)}


def _power_bi_missing_required_columns(dataframe: pd.DataFrame) -> list[str]:
    normalized_lookup = _build_normalized_column_lookup(dataframe)
    return [
        column_name
        for column_name in POWER_BI_REQUIRED_SOURCE_COLUMNS
        if normalize_header(column_name) not in normalized_lookup
    ]


def _matches_power_bi_ticket_export(dataframe: pd.DataFrame) -> bool:
    return not _power_bi_missing_required_columns(dataframe)


def _resolve_source_column(normalized_lookup: dict[str, str], expected_name: str) -> str | None:
    return normalized_lookup.get(normalize_header(expected_name))


def _build_created_series_from_power_bi(raw_df: pd.DataFrame, normalized_lookup: dict[str, str]) -> pd.Series:
    timestamp_column = _resolve_source_column(normalized_lookup, "Create Timestamp")
    created_series = pd.to_datetime(raw_df.get(timestamp_column), errors="coerce") if timestamp_column else pd.Series(pd.NaT, index=raw_df.index)

    created_date_column = _resolve_source_column(normalized_lookup, "Created Date")
    created_hour_column = _resolve_source_column(normalized_lookup, "Created Hour")
    if created_date_column:
        fallback_dates = pd.to_datetime(raw_df.get(created_date_column), errors="coerce")
        if created_hour_column:
            fallback_hours = pd.to_numeric(raw_df.get(created_hour_column), errors="coerce").fillna(0)
            fallback_dates = fallback_dates + pd.to_timedelta(fallback_hours, unit="h")
        created_series = created_series.fillna(fallback_dates)

    return created_series


def _normalize_power_bi_ticket_export(dataframe: pd.DataFrame) -> DataValidationResult:
    missing_source_columns = _power_bi_missing_required_columns(dataframe)
    if missing_source_columns:
        missing = ", ".join(missing_source_columns)
        raise ValidationError(
            "The uploaded CSV is missing required Power BI ticket export columns: "
            f"{missing}."
        )

    normalized_lookup = _build_normalized_column_lookup(dataframe)
    prepared = pd.DataFrame(index=dataframe.index)
    column_mapping: dict[str, str] = {}
    normalization_notes = [
        "Power BI ticket export mapped into the canonical created-ticket schema.",
        "Title derived from My Value.",
        "Complete Date derived from Created because the Power BI export does not include a completion timestamp.",
        "Escalation Reason defaulted to blank because the Power BI export does not include that field.",
    ]

    for source_name, canonical_name in POWER_BI_TO_CANONICAL_MAP.items():
        source_column = _resolve_source_column(normalized_lookup, source_name)
        if source_column:
            prepared[canonical_name] = dataframe[source_column]
            column_mapping[source_column] = canonical_name

    created_series = _build_created_series_from_power_bi(dataframe, normalized_lookup)
    prepared["Created"] = created_series
    timestamp_column = _resolve_source_column(normalized_lookup, "Create Timestamp")
    if timestamp_column:
        column_mapping[timestamp_column] = "Created"
    else:
        created_date_column = _resolve_source_column(normalized_lookup, "Created Date")
        if created_date_column:
            column_mapping[created_date_column] = "Created"

    if prepared["Created"].isna().all():
        raise ValidationError(
            "The Power BI ticket export could not be normalized because no valid created timestamps were found."
        )

    prepared["Complete Date"] = prepared["Created"]
    prepared["Escalation Reason"] = ""

    for required in REQUIRED_COLUMNS:
        if required not in prepared.columns:
            prepared[required] = ""

    for column_name in prepared.columns:
        if prepared[column_name].dtype == object:
            prepared[column_name] = prepared[column_name].fillna("").astype(str).str.strip()

    for date_column in ("Created", "Complete Date"):
        prepared[date_column] = pd.to_datetime(prepared[date_column], errors="coerce")

    return DataValidationResult(
        dataframe=prepared,
        column_mapping=column_mapping,
        missing_columns=[],
        source_schema="power_bi_ticket_export",
        normalization_notes=normalization_notes,
    )


def validate_and_prepare_dataframe(dataframe: pd.DataFrame) -> DataValidationResult:
    if dataframe.empty:
        raise ValidationError("The selected CSV file is empty.")

    if _matches_power_bi_ticket_export(dataframe):
        return _normalize_power_bi_ticket_export(dataframe)

    alias_lookup = build_alias_lookup()
    original_columns = list(dataframe.columns)
    column_mapping: dict[str, str] = {}
    seen_targets: set[str] = set()

    for original_name in original_columns:
        normalized_name = normalize_header(original_name)
        canonical_name = alias_lookup.get(normalized_name, str(original_name).strip())

        if canonical_name in seen_targets and canonical_name in REQUIRED_COLUMNS:
            raise ValidationError(
                f'The CSV appears to contain duplicate matches for the required column "{canonical_name}". '
                "Please keep only one matching source column."
            )

        column_mapping[original_name] = canonical_name
        seen_targets.add(canonical_name)

    prepared = dataframe.rename(columns=column_mapping).copy()
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in prepared.columns]

    for required in REQUIRED_COLUMNS:
        if required not in prepared.columns:
            prepared[required] = ""

    for column_name in prepared.columns:
        if prepared[column_name].dtype == object:
            prepared[column_name] = prepared[column_name].fillna("").astype(str).str.strip()

    for date_column in ("Created", "Complete Date"):
        if date_column in prepared.columns:
            prepared[date_column] = pd.to_datetime(prepared[date_column], errors="coerce")

    return DataValidationResult(
        dataframe=prepared,
        column_mapping=column_mapping,
        missing_columns=missing_columns,
    )
