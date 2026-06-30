from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from travel_times.config import ColumnSettings
from travel_times.io_ods import normalize_commune_type, normalize_insee
from travel_times.models import CityRecord


class DataLoadingError(ValueError):
    """Raised when an input commune file cannot be loaded safely."""


def read_communes_csv(path: Path, columns: ColumnSettings) -> list[CityRecord]:
    if not path.exists():
        raise DataLoadingError(f"Fichier communes introuvable: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise DataLoadingError(f"Fichier communes vide ou sans en-tete: {path}")
        _validate_columns(path, reader.fieldnames, columns)
        rows = list(reader)

    communes: list[CityRecord] = []
    seen: dict[str, int] = {}
    errors: list[str] = []
    for index, row in enumerate(rows, start=2):
        code = normalize_insee(row.get(columns.code_commune))
        name = _required_text(row.get(columns.nom_commune))
        if not code:
            errors.append(f"Ligne {index}: code commune vide")
            continue
        if not name:
            errors.append(f"Ligne {index}: nom commune vide")
            continue
        if code in seen:
            errors.append(f"Ligne {index}: code commune duplique {code}, deja vu ligne {seen[code]}")
            continue
        seen[code] = index
        lat = _parse_float(row.get(columns.latitude), columns.latitude, index, errors)
        lon = _parse_float(row.get(columns.longitude), columns.longitude, index, errors)
        if lat is None or lon is None:
            continue
        if not -90 <= lat <= 90:
            errors.append(f"Ligne {index}: latitude hors plage {lat}")
            continue
        if not -180 <= lon <= 180:
            errors.append(f"Ligne {index}: longitude hors plage {lon}")
            continue
        communes.append(
            CityRecord(
                insee_code=code,
                name=name,
                commune_type=normalize_commune_type(row.get(columns.categorie)),
                lat=lat,
                lon=lon,
                coord_source="input_csv",
                population=_parse_optional_int(row, columns.population, index, errors),
                geocode_status="ok",
            )
        )

    if errors:
        raise DataLoadingError("\n".join(errors))
    return communes


def _validate_columns(path: Path, fieldnames: list[str], columns: ColumnSettings) -> None:
    required = [
        columns.code_commune,
        columns.nom_commune,
        columns.categorie,
        columns.latitude,
        columns.longitude,
    ]
    missing = [column for column in required if column not in fieldnames]
    if missing:
        raise DataLoadingError(f"Colonnes obligatoires manquantes dans {path}: {', '.join(missing)}")


def _required_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_float(value: Any, field_name: str, row_number: int, errors: list[str]) -> float | None:
    text = _required_text(value).replace(",", ".")
    if not text:
        errors.append(f"Ligne {row_number}: valeur vide pour {field_name}")
        return None
    try:
        return float(text)
    except ValueError:
        errors.append(f"Ligne {row_number}: valeur decimale invalide pour {field_name}: {text}")
        return None


def _parse_optional_int(
    row: dict[str, Any],
    column_name: str | None,
    row_number: int,
    errors: list[str],
) -> int | None:
    if not column_name or column_name not in row:
        return None
    text = _required_text(row.get(column_name))
    if not text:
        return None
    try:
        parsed = int(float(text.replace(",", ".")))
    except ValueError:
        errors.append(f"Ligne {row_number}: entier invalide pour {column_name}: {text}")
        return None
    if parsed < 0:
        errors.append(f"Ligne {row_number}: entier negatif interdit pour {column_name}: {parsed}")
        return None
    return parsed
