"""Preparation des donnees brutes vers les CSV propres du solveur."""

from __future__ import annotations

import csv
import json
import math
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import yaml


class DataPreparationError(ValueError):
    """Erreur explicite pendant la preparation des donnees."""


@dataclass(frozen=True)
class PreparationIssue:
    """Anomalie detectee pendant la preparation."""

    severity: str
    message: str
    file_name: str | None = None
    row_number: int | None = None


@dataclass(frozen=True)
class PreparationResult:
    """Resultat complet de la preparation."""

    input_dir: Path
    output_dir: Path
    report_dir: Path
    generated_at: str
    raw_files: tuple[str, ...]
    produced_files: tuple[Path, ...]
    stats: dict[str, Any]
    blocking_issues: tuple[PreparationIssue, ...] = field(default_factory=tuple)
    non_blocking_issues: tuple[PreparationIssue, ...] = field(default_factory=tuple)


COMMUNES_OUTPUT_COLUMNS = [
    "code_commune",
    "nom_commune",
    "categorie",
    "territoire_EAR",
    "population",
    "logements",
    "latitude",
    "longitude",
]

TRAVEL_OUTPUT_COLUMNS = [
    "code_commune_origine",
    "code_commune_pivot",
    "temps_minutes",
]

COMPATIBILITY_OUTPUT_COLUMNS = [
    "code_commune_origine",
    "code_commune_pivot",
    "compatible",
]

DEFAULT_COMMUNE_COLUMNS = {
    "code_commune": "Code commune",
    "nom_commune": "Commune",
    "categorie": "Categorie",
    "territoire_EAR": "Territoire EAR 2027",
    "population": "Population 2023",
    "logements": "Logements 2023",
    "latitude": "Latitude",
    "longitude": "Longitude",
}

DEFAULT_CATEGORY_MAPPING = {
    "PC": "PC",
    "TPC": "TPC",
}

DEFAULT_COORDINATE_COLUMNS = {
    "code_commune": "insee_code",
    "nom_commune": "name",
    "latitude": "lat",
    "longitude": "lon",
}

CODE_PATTERN = re.compile(r"\(([^()]+)\)\s*$")


def prepare_data(
    config_path: str | Path,
    input_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    report: bool = False,
    dry_run: bool = False,
    strict: bool = False,
) -> PreparationResult:
    """Prepare les fichiers bruts en CSV propres utilisables par le solveur."""

    config_path = Path(config_path)
    raw_config = _load_raw_config(config_path)
    preparation_config = dict(raw_config.get("data_preparation", {}))
    resolved_input_dir = _resolve_input_dir(input_dir, preparation_config)
    resolved_output_dir = Path(output_dir or preparation_config.get("output_dir") or "data/processed")
    report_dir = Path(raw_config.get("exports", {}).get("output_dir", "outputs")) / "reports"

    if not resolved_input_dir.exists():
        raise DataPreparationError(f"Dossier brut introuvable: {resolved_input_dir}.")

    raw_files = tuple(sorted(path.name for path in resolved_input_dir.iterdir() if path.is_file()))
    blocking_issues: list[PreparationIssue] = []
    non_blocking_issues: list[PreparationIssue] = []
    stats: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "input_dir": str(resolved_input_dir),
        "output_dir": str(resolved_output_dir),
        "raw_files": list(raw_files),
        "produced_files": [],
        "columns_renamed": {},
        "columns_ignored": {},
        "transformations": [
            "Codes communes normalises en chaines de caracteres.",
            "Categories converties vers PC/TPC selon le mapping configure.",
            "Coordonnees jointes aux communes par code commune normalise lorsqu'un fichier est disponible.",
            "Temps de trajet decimaux convertis en minutes entieres par plafond.",
            "Trajets absents conserves absents et traites comme interdits par le modele.",
        ],
    }

    communes_rows, commune_stats = _prepare_communes(
        resolved_input_dir,
        preparation_config,
        blocking_issues,
        non_blocking_issues,
    )
    stats.update(commune_stats)

    coordinate_stats = _merge_coordinates(
        communes_rows,
        resolved_input_dir,
        preparation_config,
        blocking_issues,
        non_blocking_issues,
    )
    _merge_nested_stats(stats, coordinate_stats)

    commune_ids = {row["code_commune"] for row in communes_rows}
    travel_rows, travel_stats = _prepare_travel_times(
        resolved_input_dir,
        preparation_config,
        commune_ids,
        blocking_issues,
        non_blocking_issues,
    )
    stats.update(travel_stats)

    compatibility_rows, compatibility_stats = _prepare_compatibilities(
        resolved_input_dir,
        preparation_config,
        commune_ids,
        blocking_issues,
        non_blocking_issues,
    )
    stats.update(compatibility_stats)

    produced_files: list[Path] = [
        resolved_output_dir / "communes_clean.csv",
        resolved_output_dir / "temps_trajet_clean.csv",
    ]
    if compatibility_rows is not None:
        produced_files.append(resolved_output_dir / "compatibilites_clean.csv")

    stats["produced_files"] = [str(path) for path in produced_files]
    stats["blocking_issues"] = [_issue_to_dict(issue) for issue in blocking_issues]
    stats["non_blocking_issues"] = [_issue_to_dict(issue) for issue in non_blocking_issues]

    result = PreparationResult(
        input_dir=resolved_input_dir,
        output_dir=resolved_output_dir,
        report_dir=report_dir,
        generated_at=stats["generated_at"],
        raw_files=raw_files,
        produced_files=tuple(produced_files),
        stats=stats,
        blocking_issues=tuple(blocking_issues),
        non_blocking_issues=tuple(non_blocking_issues),
    )

    if strict and blocking_issues:
        raise DataPreparationError(
            "Anomalies bloquantes detectees en mode strict: "
            + "; ".join(issue.message for issue in blocking_issues[:5])
        )

    if not dry_run:
        resolved_output_dir.mkdir(parents=True, exist_ok=True)
        _write_csv(resolved_output_dir / "communes_clean.csv", COMMUNES_OUTPUT_COLUMNS, communes_rows)
        _write_csv(resolved_output_dir / "temps_trajet_clean.csv", TRAVEL_OUTPUT_COLUMNS, travel_rows)
        if compatibility_rows is not None:
            _write_csv(resolved_output_dir / "compatibilites_clean.csv", COMPATIBILITY_OUTPUT_COLUMNS, compatibility_rows)
        if report:
            report_dir.mkdir(parents=True, exist_ok=True)
            _write_report(report_dir / "rapport_preparation_donnees.md", result)
            _write_json(report_dir / "statistiques_preparation_donnees.json", stats)

    return result


def _load_raw_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as stream:
        raw = yaml.safe_load(stream)
    if not isinstance(raw, dict):
        raise DataPreparationError(f"La configuration {config_path} doit contenir un objet YAML.")
    return raw


def _resolve_input_dir(input_dir: str | Path | None, preparation_config: dict[str, Any]) -> Path:
    if input_dir is not None:
        return Path(input_dir)
    configured = preparation_config.get("input_dir")
    if configured:
        return Path(configured)
    preferred = Path("donnee_brut_EAR2027")
    if preferred.exists():
        return preferred
    fallback = Path("donnee_brut_EAR27")
    if fallback.exists():
        return fallback
    return preferred


def _prepare_communes(
    input_dir: Path,
    preparation_config: dict[str, Any],
    blocking_issues: list[PreparationIssue],
    non_blocking_issues: list[PreparationIssue],
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    config = dict(preparation_config.get("communes", {}))
    file_path = _select_file(input_dir, config, ["info_minimum.ods", "villes_rhone_alpes.ods"], "communes")
    rows = _read_tabular_file(file_path, config.get("sheet"))
    if not rows:
        raise DataPreparationError(f"Fichier communes vide: {file_path}.")

    header = _normalize_headers(rows[0])
    raw_columns = dict(DEFAULT_COMMUNE_COLUMNS)
    raw_columns.update(config.get("columns", {}))
    category_mapping = {_normalize_category_key(k): v for k, v in DEFAULT_CATEGORY_MAPPING.items()}
    category_mapping.update({_normalize_category_key(k): v for k, v in config.get("category_mapping", {}).items()})

    column_indexes = _column_indexes(header)
    missing_required = [
        clean
        for clean in ["code_commune", "nom_commune", "categorie", "population"]
        if _normalize_header(raw_columns[clean]) not in column_indexes
    ]
    if missing_required:
        raise DataPreparationError(
            f"Colonnes communes obligatoires manquantes dans {file_path.name}: {', '.join(missing_required)}."
        )

    optional_missing = [
        clean
        for clean in ["territoire_EAR", "logements", "latitude", "longitude"]
        if _normalize_header(raw_columns[clean]) not in column_indexes
    ]
    for clean in optional_missing:
        non_blocking_issues.append(
            PreparationIssue("non_blocking", f"Colonne optionnelle absente pour communes: {clean}.", file_path.name)
        )

    ignored = [column for column in rows[0] if _normalize_header(column) not in {_normalize_header(v) for v in raw_columns.values()}]
    clean_rows: list[dict[str, str]] = []
    seen_codes: set[str] = set()
    unknown_categories = 0
    invalid_rows = 0

    for row_number, values in enumerate(rows[1:], start=2):
        if not any(str(value).strip() for value in values):
            continue
        row = _row_dict(header, values)
        code = _normalize_commune_code(_value(row, raw_columns["code_commune"]))
        if not code:
            blocking_issues.append(PreparationIssue("blocking", "Code commune vide.", file_path.name, row_number))
            invalid_rows += 1
            continue
        if code in seen_codes:
            blocking_issues.append(PreparationIssue("blocking", f"Commune dupliquee: {code}.", file_path.name, row_number))
            invalid_rows += 1
            continue
        seen_codes.add(code)

        raw_category = _value(row, raw_columns["categorie"])
        category = category_mapping.get(_normalize_category_key(raw_category))
        if category not in {"PC", "TPC"}:
            blocking_issues.append(
                PreparationIssue("blocking", f"Categorie inconnue pour {code}: {raw_category}.", file_path.name, row_number)
            )
            unknown_categories += 1
            invalid_rows += 1
            continue

        population = _parse_non_negative_number(
            _value(row, raw_columns["population"]),
            "population",
            file_path.name,
            row_number,
            blocking_issues,
        )
        if population is None:
            invalid_rows += 1
            continue

        housing = _parse_optional_non_negative_number(
            _optional_value(row, raw_columns["logements"]),
            "logements",
            file_path.name,
            row_number,
            blocking_issues,
        )
        latitude = _parse_optional_float(
            _optional_value(row, raw_columns["latitude"]),
            "latitude",
            file_path.name,
            row_number,
            blocking_issues,
        )
        longitude = _parse_optional_float(
            _optional_value(row, raw_columns["longitude"]),
            "longitude",
            file_path.name,
            row_number,
            blocking_issues,
        )

        clean_rows.append(
            {
                "code_commune": code,
                "nom_commune": _value(row, raw_columns["nom_commune"]).strip(),
                "categorie": category,
                "territoire_EAR": _optional_value(row, raw_columns["territoire_EAR"]).strip(),
                "population": str(int(population)),
                "logements": "" if housing is None else str(int(housing)),
                "latitude": "" if latitude is None else str(latitude),
                "longitude": "" if longitude is None else str(longitude),
            }
        )

    return clean_rows, {
        "communes_file": file_path.name,
        "communes_rows_raw": max(len(rows) - 1, 0),
        "communes_count": len(clean_rows),
        "pc_count": sum(1 for row in clean_rows if row["categorie"] == "PC"),
        "tpc_count": sum(1 for row in clean_rows if row["categorie"] == "TPC"),
        "communes_invalid_rows": invalid_rows,
        "communes_unknown_categories": unknown_categories,
        "columns_renamed": {"communes": raw_columns},
        "columns_ignored": {"communes": ignored},
    }


def _merge_coordinates(
    commune_rows: list[dict[str, str]],
    input_dir: Path,
    preparation_config: dict[str, Any],
    blocking_issues: list[PreparationIssue],
    non_blocking_issues: list[PreparationIssue],
) -> dict[str, Any]:
    config = dict(preparation_config.get("coordinates", {}))
    file_path = _select_optional_file(
        input_dir,
        config,
        ["cities_geocoded.ods"],
        ["*geocod*.csv", "*geocod*.ods", "*coord*.csv", "*coord*.ods"],
    )
    commune_ids = {row["code_commune"] for row in commune_rows}

    if file_path is None:
        missing_codes = [row["code_commune"] for row in commune_rows if not row["latitude"] or not row["longitude"]]
        if missing_codes:
            non_blocking_issues.append(
                PreparationIssue(
                    "non_blocking",
                    f"Aucun fichier de coordonnees trouve; {len(missing_codes)} communes sans coordonnees latitude/longitude.",
                )
            )
        return _coordinate_stats_without_file(commune_rows, missing_codes)

    rows = _read_tabular_file(file_path, config.get("sheet"))
    if not rows:
        raise DataPreparationError(f"Fichier coordonnees vide: {file_path}.")

    header = _normalize_headers(rows[0])
    raw_columns = dict(DEFAULT_COORDINATE_COLUMNS)
    raw_columns.update(config.get("columns", {}))
    column_indexes = _column_indexes(header)
    missing_required = [
        clean
        for clean in ["code_commune", "latitude", "longitude"]
        if _normalize_header(raw_columns[clean]) not in column_indexes
    ]
    if missing_required:
        raise DataPreparationError(
            f"Colonnes coordonnees obligatoires manquantes dans {file_path.name}: {', '.join(missing_required)}."
        )

    ignored = [
        column
        for column in rows[0]
        if _normalize_header(column) not in {_normalize_header(value) for value in raw_columns.values()}
    ]
    coordinates: dict[str, tuple[float, float]] = {}
    seen_codes: set[str] = set()
    duplicates = 0
    invalid = 0
    outside_scope: list[str] = []

    for row_number, values in enumerate(rows[1:], start=2):
        if not any(str(value).strip() for value in values):
            continue
        row = _row_dict(header, values)
        code = _normalize_commune_code(_value(row, raw_columns["code_commune"]))
        if not code:
            blocking_issues.append(
                PreparationIssue("blocking", "Code commune vide dans le fichier de coordonnees.", file_path.name, row_number)
            )
            invalid += 1
            continue
        if code in seen_codes:
            blocking_issues.append(
                PreparationIssue("blocking", f"Coordonnees dupliquees pour la commune {code}.", file_path.name, row_number)
            )
            duplicates += 1
            invalid += 1
            continue
        seen_codes.add(code)

        latitude = _parse_coordinate(
            _value(row, raw_columns["latitude"]),
            "latitude",
            -90,
            90,
            file_path.name,
            row_number,
            blocking_issues,
        )
        longitude = _parse_coordinate(
            _value(row, raw_columns["longitude"]),
            "longitude",
            -180,
            180,
            file_path.name,
            row_number,
            blocking_issues,
        )
        if latitude is None or longitude is None:
            invalid += 1
            continue
        if code not in commune_ids:
            outside_scope.append(code)
            continue
        coordinates[code] = (latitude, longitude)

    if outside_scope:
        non_blocking_issues.append(
            PreparationIssue(
                "non_blocking",
                f"{len(outside_scope)} coordonnees hors perimetre EAR2027 ignorees.",
                file_path.name,
            )
        )

    for row in commune_rows:
        coordinate = coordinates.get(row["code_commune"])
        if coordinate is None:
            continue
        row["latitude"] = str(coordinate[0])
        row["longitude"] = str(coordinate[1])

    missing_codes = [row["code_commune"] for row in commune_rows if not row["latitude"] or not row["longitude"]]
    if missing_codes:
        non_blocking_issues.append(
            PreparationIssue(
                "non_blocking",
                f"{len(missing_codes)} communes sans coordonnees apres jointure.",
                file_path.name,
            )
        )

    return {
        "coordinates_file": file_path.name,
        "coordinates_sheet": config.get("sheet"),
        "coordinates_columns": raw_columns,
        "coordinates_crs": config.get("crs", "non precise"),
        "coordinates_rows_raw": max(len(rows) - 1, 0),
        "coordinates_valid": len(coordinates),
        "coordinates_invalid": invalid,
        "coordinates_duplicates": duplicates,
        "coordinates_outside_scope": len(outside_scope),
        "coordinates_outside_scope_codes": outside_scope[:50],
        "communes_with_coordinates": sum(1 for row in commune_rows if row["latitude"] and row["longitude"]),
        "communes_without_coordinates": len(missing_codes),
        "communes_without_coordinates_codes": missing_codes[:50],
        "columns_renamed": {"coordinates": raw_columns},
        "columns_ignored": {"coordinates": ignored},
    }


def _coordinate_stats_without_file(commune_rows: list[dict[str, str]], missing_codes: list[str]) -> dict[str, Any]:
    return {
        "coordinates_file": None,
        "coordinates_sheet": None,
        "coordinates_columns": {},
        "coordinates_crs": "non precise",
        "coordinates_rows_raw": 0,
        "coordinates_valid": 0,
        "coordinates_invalid": 0,
        "coordinates_duplicates": 0,
        "coordinates_outside_scope": 0,
        "coordinates_outside_scope_codes": [],
        "communes_with_coordinates": sum(1 for row in commune_rows if row["latitude"] and row["longitude"]),
        "communes_without_coordinates": len(missing_codes),
        "communes_without_coordinates_codes": missing_codes[:50],
    }


def _prepare_travel_times(
    input_dir: Path,
    preparation_config: dict[str, Any],
    commune_ids: set[str],
    blocking_issues: list[PreparationIssue],
    non_blocking_issues: list[PreparationIssue],
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    config = dict(preparation_config.get("travel_times", {}))
    file_path = _select_file(
        input_dir,
        config,
        ["matrice_temps_trajets_max_90min.ods", "matrice_temps_trajets_complete.ods"],
        "temps de trajet",
    )
    rows = _read_tabular_file(file_path, config.get("sheet"))
    if not rows:
        raise DataPreparationError(f"Fichier temps de trajet vide: {file_path}.")

    header = rows[0]
    clean_rows: list[dict[str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()
    duplicates = 0
    invalid = 0
    unknown_communes: set[str] = set()

    if _looks_like_long_travel_file(header) or {"origin_column", "destination_column", "minutes_column"}.issubset(config):
        normalized_names = {_normalize_header(column) for column in header}
        default_origin = "code_commune_origine" if "code_commune_origine" in normalized_names else "origin"
        default_destination = "code_commune_pivot" if "code_commune_pivot" in normalized_names else "destination"
        source_columns = {
            "origin": config.get("origin_column", default_origin),
            "destination": config.get("destination_column", default_destination),
            "minutes": config.get("minutes_column", "temps_minutes"),
        }
        normalized_header = _normalize_headers(header)
        for row_number, values in enumerate(rows[1:], start=2):
            row = _row_dict(normalized_header, values)
            origin = _normalize_commune_code(_value(row, source_columns["origin"]))
            destination = _normalize_commune_code(_value(row, source_columns["destination"]))
            minutes = _parse_non_negative_number(
                _value(row, source_columns["minutes"]),
                "temps_minutes",
                file_path.name,
                row_number,
                blocking_issues,
            )
            append_status = _append_travel_row(
                clean_rows,
                seen_pairs,
                commune_ids,
                origin,
                destination,
                minutes,
                file_path.name,
                row_number,
                blocking_issues,
                unknown_communes,
            )
            invalid += int(append_status != "ok")
            duplicates += int(append_status == "duplicate")
    else:
        destinations = [_extract_commune_code(cell) for cell in header[1:]]
        for row_number, values in enumerate(rows[1:], start=2):
            if not values:
                continue
            origin = _extract_commune_code(values[0])
            for index, raw_minutes in enumerate(values[1:], start=0):
                if index >= len(destinations):
                    break
                if raw_minutes is None or str(raw_minutes).strip() == "":
                    continue
                destination = destinations[index]
                minutes = _parse_non_negative_number(
                    raw_minutes,
                    "temps_minutes",
                    file_path.name,
                    row_number,
                    blocking_issues,
                )
                append_status = _append_travel_row(
                    clean_rows,
                    seen_pairs,
                    commune_ids,
                    origin,
                    destination,
                    minutes,
                    file_path.name,
                    row_number,
                    blocking_issues,
                    unknown_communes,
                )
                invalid += int(append_status != "ok")
                duplicates += int(append_status == "duplicate")

    if duplicates:
        non_blocking_issues.append(PreparationIssue("non_blocking", f"{duplicates} trajets dupliques detectes.", file_path.name))

    return clean_rows, {
        "travel_times_file": file_path.name,
        "travel_times_count": len(clean_rows),
        "travel_times_invalid_rejected": invalid,
        "travel_times_duplicates": duplicates,
        "travel_times_unknown_communes": sorted(unknown_communes),
        "travel_times_missing_are_forbidden": True,
    }


def _append_travel_row(
    clean_rows: list[dict[str, str]],
    seen_pairs: set[tuple[str, str]],
    commune_ids: set[str],
    origin: str,
    destination: str,
    minutes: float | None,
    file_name: str,
    row_number: int,
    blocking_issues: list[PreparationIssue],
    unknown_communes: set[str],
) -> str:
    if not origin or not destination:
        blocking_issues.append(PreparationIssue("blocking", "Origine ou destination de trajet vide.", file_name, row_number))
        return "invalid"
    if origin not in commune_ids or destination not in commune_ids:
        if origin not in commune_ids:
            unknown_communes.add(origin)
        if destination not in commune_ids:
            unknown_communes.add(destination)
        blocking_issues.append(
            PreparationIssue("blocking", f"Trajet avec commune inconnue: {origin} -> {destination}.", file_name, row_number)
        )
        return "invalid"
    if minutes is None:
        return "invalid"
    key = (origin, destination)
    if key in seen_pairs:
        blocking_issues.append(PreparationIssue("blocking", f"Trajet duplique: {origin} -> {destination}.", file_name, row_number))
        return "duplicate"
    seen_pairs.add(key)
    clean_rows.append(
        {
            "code_commune_origine": origin,
            "code_commune_pivot": destination,
            "temps_minutes": str(int(math.ceil(minutes))),
        }
    )
    return "ok"


def _prepare_compatibilities(
    input_dir: Path,
    preparation_config: dict[str, Any],
    commune_ids: set[str],
    blocking_issues: list[PreparationIssue],
    non_blocking_issues: list[PreparationIssue],
) -> tuple[list[dict[str, str]] | None, dict[str, Any]]:
    config = dict(preparation_config.get("compatibilities", {}))
    configured_file = config.get("file")
    if configured_file:
        file_path = input_dir / configured_file
    else:
        candidates = sorted(input_dir.glob("*compat*.csv")) + sorted(input_dir.glob("*compat*.ods"))
        file_path = candidates[0] if candidates else None

    if file_path is None or not file_path.exists():
        non_blocking_issues.append(
            PreparationIssue(
                "non_blocking",
                "Aucun fichier de compatibilites trouve; b_ij vaudra 1 par defaut dans le modele.",
            )
        )
        return None, {
            "compatibilities_loaded": False,
            "compatibilities_file": None,
            "compatibilities_count": 0,
            "compatibilities_invalid_rejected": 0,
        }

    rows = _read_tabular_file(file_path, config.get("sheet"))
    if not rows:
        raise DataPreparationError(f"Fichier compatibilites vide: {file_path}.")

    header = _normalize_headers(rows[0])
    source_columns = {
        "origin": config.get("origin_column", "origin"),
        "destination": config.get("destination_column", "destination"),
        "allowed": config.get("allowed_column", "compatible"),
    }
    clean_rows: list[dict[str, str]] = []
    invalid = 0
    for row_number, values in enumerate(rows[1:], start=2):
        row = _row_dict(header, values)
        origin = _normalize_commune_code(_value(row, source_columns["origin"]))
        destination = _normalize_commune_code(_value(row, source_columns["destination"]))
        allowed_text = _value(row, source_columns["allowed"]).strip()
        if allowed_text not in {"0", "1"}:
            blocking_issues.append(
                PreparationIssue("blocking", f"Compatibilite invalide pour {origin} -> {destination}: {allowed_text}.", file_path.name, row_number)
            )
            invalid += 1
            continue
        if origin not in commune_ids or destination not in commune_ids:
            blocking_issues.append(
                PreparationIssue("blocking", f"Compatibilite avec commune inconnue: {origin} -> {destination}.", file_path.name, row_number)
            )
            invalid += 1
            continue
        clean_rows.append(
            {
                "code_commune_origine": origin,
                "code_commune_pivot": destination,
                "compatible": allowed_text,
            }
        )

    return clean_rows, {
        "compatibilities_loaded": True,
        "compatibilities_file": file_path.name,
        "compatibilities_count": len(clean_rows),
        "compatibilities_invalid_rejected": invalid,
    }


def _select_file(input_dir: Path, config: dict[str, Any], defaults: list[str], label: str) -> Path:
    configured = config.get("file")
    candidates = [configured] if configured else defaults
    for name in candidates:
        if not name:
            continue
        path = input_dir / str(name)
        if path.exists():
            return path
    raise DataPreparationError(f"Aucun fichier {label} trouve dans {input_dir}: {', '.join(defaults)}.")


def _select_optional_file(
    input_dir: Path,
    config: dict[str, Any],
    defaults: list[str],
    patterns: list[str],
) -> Path | None:
    configured = config.get("file")
    if configured:
        path = input_dir / str(configured)
        return path if path.exists() else None
    for name in defaults:
        path = input_dir / name
        if path.exists():
            return path
    matches: list[Path] = []
    for pattern in patterns:
        matches.extend(sorted(input_dir.glob(pattern)))
    return matches[0] if matches else None


def _read_tabular_file(path: Path, sheet_name: str | None = None) -> list[list[str]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            return [list(row) for row in csv.reader(stream)]
    if suffix == ".ods":
        return _read_ods(path, sheet_name)
    raise DataPreparationError(f"Format de fichier non supporte: {path}.")


def _read_ods(path: Path, sheet_name: str | None = None) -> list[list[str]]:
    ns = {
        "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
        "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
        "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    }
    with zipfile.ZipFile(path) as archive:
        with archive.open("content.xml") as stream:
            root = ElementTree.parse(stream).getroot()

    tables = root.findall(".//table:table", ns)
    if not tables:
        raise DataPreparationError(f"Aucune feuille trouvee dans {path}.")

    selected = None
    for table in tables:
        name = table.attrib.get(f"{{{ns['table']}}}name")
        if sheet_name is None or name == sheet_name:
            selected = table
            break
    if selected is None:
        raise DataPreparationError(f"Feuille introuvable dans {path}: {sheet_name}.")

    rows: list[list[str]] = []
    for row_node in selected.findall("table:table-row", ns):
        repeated_rows = int(row_node.attrib.get(f"{{{ns['table']}}}number-rows-repeated", "1"))
        row = _read_ods_row(row_node, ns)
        if not any(cell.strip() for cell in row):
            continue
        for _ in range(min(repeated_rows, 1)):
            rows.append(row)
    return rows


def _read_ods_row(row_node: ElementTree.Element, ns: dict[str, str]) -> list[str]:
    cells: list[str] = []
    for cell in list(row_node):
        if cell.tag not in {
            f"{{{ns['table']}}}table-cell",
            f"{{{ns['table']}}}covered-table-cell",
        }:
            continue
        repeated = int(cell.attrib.get(f"{{{ns['table']}}}number-columns-repeated", "1"))
        text_parts = [node.text or "" for node in cell.findall(".//text:p", ns)]
        value = " ".join(part for part in text_parts if part).strip()
        if not value:
            value = str(cell.attrib.get(f"{{{ns['office']}}}value", "")).strip()
        cells.extend([value] * repeated)
    return cells


def _looks_like_long_travel_file(header: list[str]) -> bool:
    normalized = {_normalize_header(column) for column in header}
    return {"origin", "destination"}.issubset(normalized) or {
        "code_commune_origine",
        "code_commune_pivot",
    }.issubset(normalized)


def _normalize_headers(headers: list[str]) -> list[str]:
    return [str(header).strip() for header in headers]


def _column_indexes(header: list[str]) -> dict[str, int]:
    return {_normalize_header(column): index for index, column in enumerate(header)}


def _row_dict(header: list[str], values: list[str]) -> dict[str, str]:
    return {header[index]: values[index] if index < len(values) else "" for index in range(len(header))}


def _value(row: dict[str, str], column_name: str) -> str:
    normalized = _normalize_header(column_name)
    for key, value in row.items():
        if _normalize_header(key) == normalized:
            return str(value).strip()
    return ""


def _optional_value(row: dict[str, str], column_name: str) -> str:
    return _value(row, column_name)


def _normalize_header(value: str) -> str:
    return str(value).strip().lower().replace("é", "e").replace("è", "e").replace("ê", "e")


def _normalize_category_key(value: Any) -> str:
    return str(value).strip().upper().replace(" ", "")


def _normalize_commune_code(value: Any) -> str:
    text = str(value).strip()
    if not text:
        return ""
    if text.endswith(".0"):
        text = text[:-2]
    if text.isdigit() and len(text) < 5:
        return text.zfill(5)
    return text


def _extract_commune_code(value: Any) -> str:
    text = str(value).strip()
    match = CODE_PATTERN.search(text)
    if match:
        return _normalize_commune_code(match.group(1))
    return _normalize_commune_code(text)


def _parse_non_negative_number(
    value: Any,
    field_name: str,
    file_name: str,
    row_number: int,
    blocking_issues: list[PreparationIssue],
) -> float | None:
    text = str(value).strip().replace(",", ".")
    if not text:
        blocking_issues.append(PreparationIssue("blocking", f"Valeur vide pour {field_name}.", file_name, row_number))
        return None
    try:
        parsed = float(text)
    except ValueError:
        blocking_issues.append(PreparationIssue("blocking", f"Valeur numerique invalide pour {field_name}: {text}.", file_name, row_number))
        return None
    if parsed < 0:
        blocking_issues.append(PreparationIssue("blocking", f"Valeur negative interdite pour {field_name}: {text}.", file_name, row_number))
        return None
    return parsed


def _parse_optional_non_negative_number(
    value: Any,
    field_name: str,
    file_name: str,
    row_number: int,
    blocking_issues: list[PreparationIssue],
) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    return _parse_non_negative_number(value, field_name, file_name, row_number, blocking_issues)


def _parse_optional_float(
    value: Any,
    field_name: str,
    file_name: str,
    row_number: int,
    blocking_issues: list[PreparationIssue],
) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip().replace(",", ".")
    try:
        return float(text)
    except ValueError:
        blocking_issues.append(PreparationIssue("blocking", f"Valeur decimale invalide pour {field_name}: {text}.", file_name, row_number))
        return None


def _parse_coordinate(
    value: Any,
    field_name: str,
    lower_bound: float,
    upper_bound: float,
    file_name: str,
    row_number: int,
    blocking_issues: list[PreparationIssue],
) -> float | None:
    text = str(value).strip().replace(",", ".")
    if not text:
        blocking_issues.append(PreparationIssue("blocking", f"Coordonnee vide pour {field_name}.", file_name, row_number))
        return None
    try:
        parsed = float(text)
    except ValueError:
        blocking_issues.append(
            PreparationIssue("blocking", f"Coordonnee numerique invalide pour {field_name}: {text}.", file_name, row_number)
        )
        return None
    if parsed < lower_bound or parsed > upper_bound:
        blocking_issues.append(
            PreparationIssue(
                "blocking",
                f"Coordonnee hors plage pour {field_name}: {text} (attendu {lower_bound}..{upper_bound}).",
                file_name,
                row_number,
            )
        )
        return None
    return parsed


def _merge_nested_stats(target: dict[str, Any], incoming: dict[str, Any]) -> None:
    for key, value in incoming.items():
        if key in {"columns_renamed", "columns_ignored"} and isinstance(value, dict):
            target.setdefault(key, {}).update(value)
        else:
            target[key] = value


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def _write_report(path: Path, result: PreparationResult) -> None:
    stats = result.stats
    lines = [
        "# Rapport de preparation des donnees",
        "",
        f"- Date/heure de generation : {result.generated_at}",
        f"- Dossier brut utilise : {result.input_dir}",
        f"- Fichiers reels lus : {', '.join(result.raw_files)}",
        f"- Fichiers propres produits : {', '.join(str(path) for path in result.produced_files)}",
        "",
        "## Synthese",
        "",
        f"- Nombre de communes : {stats.get('communes_count', 0)}",
        f"- Nombre de PC : {stats.get('pc_count', 0)}",
        f"- Nombre de TPC : {stats.get('tpc_count', 0)}",
        f"- Communes avec coordonnees : {stats.get('communes_with_coordinates', 0)}",
        f"- Communes sans coordonnees : {stats.get('communes_without_coordinates', 0)}",
        f"- Nombre de trajets : {stats.get('travel_times_count', 0)}",
        f"- Trajets invalides rejetes : {stats.get('travel_times_invalid_rejected', 0)}",
        f"- Doublons detectes : {stats.get('travel_times_duplicates', 0)}",
        f"- Compatibilites chargees : {'oui' if stats.get('compatibilities_loaded') else 'non'}",
        f"- Fichier de coordonnees utilise : {stats.get('coordinates_file') or 'aucun'}",
        f"- Coordonnees lues : {stats.get('coordinates_rows_raw', 0)}",
        f"- Coordonnees valides jointes : {stats.get('coordinates_valid', 0)}",
        f"- Coordonnees invalides : {stats.get('coordinates_invalid', 0)}",
        f"- Coordonnees hors perimetre : {stats.get('coordinates_outside_scope', 0)}",
        "",
        "## Colonnes",
        "",
        f"- Colonnes renommees : `{json.dumps(stats.get('columns_renamed', {}), ensure_ascii=False)}`",
        f"- Colonnes ignorees : `{json.dumps(stats.get('columns_ignored', {}), ensure_ascii=False)}`",
        f"- Colonnes de jointure coordonnees : `{json.dumps(stats.get('coordinates_columns', {}), ensure_ascii=False)}`",
        f"- Systeme de coordonnees declare : {stats.get('coordinates_crs', 'non precise')}",
        "",
        "## Communes sans coordonnees",
        "",
        _format_code_sample(stats.get("communes_without_coordinates_codes", [])),
        "",
        "## Coordonnees hors perimetre",
        "",
        _format_code_sample(stats.get("coordinates_outside_scope_codes", [])),
        "",
        "## Anomalies bloquantes",
        "",
    ]
    lines.extend(_format_issues(result.blocking_issues))
    lines.extend(["", "## Anomalies non bloquantes", ""])
    lines.extend(_format_issues(result.non_blocking_issues))
    lines.extend(
        [
            "",
            "## Transformations realisees",
            "",
            *[f"- {item}" for item in stats.get("transformations", [])],
            "- Les trajets absents ne sont pas completes artificiellement et sont traites comme interdits.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _format_issues(issues: tuple[PreparationIssue, ...]) -> list[str]:
    if not issues:
        return ["- Aucune."]
    return [f"- {issue.message}" for issue in issues]


def _format_code_sample(codes: list[str]) -> str:
    if not codes:
        return "- Aucune."
    suffix = "..." if len(codes) >= 50 else ""
    return "- " + ", ".join(codes) + suffix


def _issue_to_dict(issue: PreparationIssue) -> dict[str, Any]:
    return {
        "severity": issue.severity,
        "message": issue.message,
        "file_name": issue.file_name,
        "row_number": issue.row_number,
    }
