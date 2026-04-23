from __future__ import annotations

import pandas as pd

from phone_schema_reference import (
    CANONICAL_PHONE_FIELDS,
    PHONE_SOURCE_LABEL,
    PHONE_SOURCE_SCHEMA,
    POWER_BI_PHONE_NORMALIZATION_NOTES,
    POWER_BI_PHONE_REQUIRED_SOURCE_COLUMNS,
    POWER_BI_PHONE_TO_CANONICAL_MAP,
)
from validators import DataValidationResult, ValidationError, normalize_header


def _build_normalized_column_lookup(dataframe: pd.DataFrame) -> dict[str, str]:
    return {normalize_header(column_name): str(column_name) for column_name in list(dataframe.columns)}


def _resolve_source_column(normalized_lookup: dict[str, str], expected_name: str) -> str | None:
    return normalized_lookup.get(normalize_header(expected_name))


def _missing_required_phone_columns(dataframe: pd.DataFrame) -> list[str]:
    lookup = _build_normalized_column_lookup(dataframe)
    return [
        column_name
        for column_name in POWER_BI_PHONE_REQUIRED_SOURCE_COLUMNS
        if normalize_header(column_name) not in lookup
    ]


def _coerce_flag_series(series: pd.Series) -> pd.Series:
    normalized = series.fillna("").astype(str).str.strip().str.lower()
    truthy = {"true", "yes", "y", "1", "answered", "abandoned"}
    falsy = {"false", "no", "n", "0", ""}

    def _map_value(value: str) -> int:
        if value in truthy:
            return 1
        if value in falsy:
            return 0
        try:
            return 1 if float(value) > 0 else 0
        except (TypeError, ValueError):
            return 0

    return normalized.apply(_map_value).astype(int)


def validate_and_prepare_phone_dataframe(dataframe: pd.DataFrame) -> DataValidationResult:
    if dataframe.empty:
        raise ValidationError("The selected CSV file is empty.")

    missing_columns = _missing_required_phone_columns(dataframe)
    if missing_columns:
        raise ValidationError(
            "The uploaded CSV is missing required Power BI phone export columns: "
            + ", ".join(missing_columns)
            + "."
        )

    normalized_lookup = _build_normalized_column_lookup(dataframe)
    prepared = pd.DataFrame(index=dataframe.index)
    column_mapping: dict[str, str] = {}

    for source_name, canonical_name in POWER_BI_PHONE_TO_CANONICAL_MAP.items():
        source_column = _resolve_source_column(normalized_lookup, source_name)
        if source_column:
            prepared[canonical_name] = dataframe[source_column]
            column_mapping[source_column] = canonical_name

    timestamp_column = _resolve_source_column(normalized_lookup, "Call Timestamp")
    prepared["Call Timestamp"] = pd.to_datetime(dataframe.get(timestamp_column), errors="coerce") if timestamp_column else pd.Series(pd.NaT, index=dataframe.index)
    if prepared["Call Timestamp"].isna().all():
        raise ValidationError("The Power BI phone export could not be normalized because no valid call timestamps were found.")

    prepared["Call Date"] = prepared["Call Timestamp"].dt.normalize()
    prepared["Call Hour"] = prepared["Call Timestamp"].dt.hour.astype("Int64")

    if "Answered Flag" in prepared.columns:
        prepared["Answered Flag"] = _coerce_flag_series(prepared["Answered Flag"])
    else:
        prepared["Answered Flag"] = 0

    if "Abandoned Flag" in prepared.columns:
        prepared["Abandoned Flag"] = _coerce_flag_series(prepared["Abandoned Flag"])
    else:
        prepared["Abandoned Flag"] = 0

    for numeric_column in ("Wait Seconds", "Answer Seconds", "Hold Seconds", "Handle Minutes", "Service Level Value"):
        if numeric_column in prepared.columns:
            prepared[numeric_column] = pd.to_numeric(prepared[numeric_column], errors="coerce")
        else:
            prepared[numeric_column] = pd.NA

    prepared["Handle Seconds"] = pd.to_numeric(prepared.get("Handle Minutes"), errors="coerce") * 60

    for field_name in CANONICAL_PHONE_FIELDS:
        if field_name not in prepared.columns:
            prepared[field_name] = ""

    for column_name in prepared.columns:
        if column_name in {"Call Timestamp", "Call Date", "Call Hour", "Answered Flag", "Abandoned Flag", "Wait Seconds", "Answer Seconds", "Hold Seconds", "Handle Minutes", "Handle Seconds", "Service Level Value"}:
            continue
        if prepared[column_name].dtype == object:
            prepared[column_name] = prepared[column_name].fillna("").astype(str).str.strip()

    prepared = prepared[CANONICAL_PHONE_FIELDS].copy()
    normalization_notes = list(POWER_BI_PHONE_NORMALIZATION_NOTES)
    if "Agent" not in prepared.columns or prepared.get("Agent", pd.Series(dtype=str)).replace("", pd.NA).dropna().empty:
        normalization_notes.append("Agent detail is not present in the current Power BI phone export.")

    prepared.attrs["source_schema"] = PHONE_SOURCE_SCHEMA
    prepared.attrs["source_label"] = PHONE_SOURCE_LABEL
    prepared.attrs["normalization_notes"] = normalization_notes

    return DataValidationResult(
        dataframe=prepared,
        column_mapping=column_mapping,
        missing_columns=[],
        source_schema=PHONE_SOURCE_SCHEMA,
        source_label=PHONE_SOURCE_LABEL,
        normalization_notes=normalization_notes,
    )
