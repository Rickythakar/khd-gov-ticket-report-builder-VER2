from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from config import COLUMN_ALIASES, REQUIRED_COLUMNS


class ValidationError(Exception):
    """Raised when app input or CSV contents are not valid for report generation."""


@dataclass
class DataValidationResult:
    dataframe: pd.DataFrame
    column_mapping: dict[str, str]
    missing_columns: list[str]


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


def validate_and_prepare_dataframe(dataframe: pd.DataFrame) -> DataValidationResult:
    if dataframe.empty:
        raise ValidationError("The selected CSV file is empty.")

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
