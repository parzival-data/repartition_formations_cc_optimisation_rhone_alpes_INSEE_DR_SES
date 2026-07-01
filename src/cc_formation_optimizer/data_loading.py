"""Chargement des donnees d'entree."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from cc_formation_optimizer.config import OptimizerConfig
from cc_formation_optimizer.domain import Compatibility, Commune, TravelTime


class DataLoadingError(ValueError):
    """Erreur explicite lors du chargement des donnees.

    Cette exception signale un fichier absent, un en-tete incomplet, une
    valeur invalide ou une commune dupliquee dans les CSV propres.
    """


def load_communes(config: OptimizerConfig, base_dir: Path | None = None) -> list[Commune]:
    """Charge les communes depuis le CSV configure.

    Les noms de colonnes proviennent exclusivement de la configuration YAML.
    Les identifiants sont normalises par suppression des espaces en bordure.

    Parameters
    ----------
    config : OptimizerConfig
        Configuration contenant le chemin et le mapping des colonnes.
    base_dir : Path | None, default=None
        Repertoire de base pour resoudre un chemin relatif.

    Returns
    -------
    list[Commune]
        Communes chargees depuis le CSV propre.

    Raises
    ------
    DataLoadingError
        Si le fichier est absent, si une colonne obligatoire manque ou si une
        valeur obligatoire est invalide.
    """

    columns = config.columns
    required = [
        columns["commune_id"],
        columns["commune_name"],
        columns["population"],
        columns["category"],
    ]
    rows = _read_csv(_resolve_path(config.inputs.communes_path, base_dir), required)

    communes: list[Commune] = []
    seen_ids: set[str] = set()
    for row_number, row in rows:
        commune_id = _normalize_id(row[columns["commune_id"]], "commune_id", row_number)
        if commune_id in seen_ids:
            raise DataLoadingError(f"Identifiant de commune duplique a la ligne {row_number}: {commune_id}.")
        seen_ids.add(commune_id)

        name = _require_text(row[columns["commune_name"]], columns["commune_name"], row_number)
        population = _parse_non_negative_int(row[columns["population"]], columns["population"], row_number)
        category = _require_text(row[columns["category"]], columns["category"], row_number).upper()
        territory_ear = _optional_text(row, columns.get("territory_ear"))
        housing = _optional_non_negative_int(row, columns.get("housing"), row_number)
        latitude = _optional_float(row, columns.get("latitude"), row_number)
        longitude = _optional_float(row, columns.get("longitude"), row_number)

        communes.append(
            Commune(
                commune_id=commune_id,
                name=name,
                population=population,
                category=category,
                territory_ear=territory_ear,
                housing=housing,
                latitude=latitude,
                longitude=longitude,
            )
        )

    return communes


def load_travel_times(config: OptimizerConfig, base_dir: Path | None = None) -> list[TravelTime]:
    """Charge les temps de trajet orientes depuis le CSV configure.

    Parameters
    ----------
    config : OptimizerConfig
        Configuration contenant le chemin et le mapping des colonnes.
    base_dir : Path | None, default=None
        Repertoire de base pour resoudre un chemin relatif.

    Returns
    -------
    list[TravelTime]
        Temps de trajet propres, en minutes entieres.

    Raises
    ------
    DataLoadingError
        Si le fichier est absent, si une colonne obligatoire manque ou si un
        temps de trajet est invalide.
    """

    columns = config.columns
    required = [
        columns["origin_id"],
        columns["destination_id"],
        columns["travel_time_minutes"],
    ]
    rows = _read_csv(_resolve_path(config.inputs.travel_times_path, base_dir), required)

    travel_times: list[TravelTime] = []
    for row_number, row in rows:
        origin_id = _normalize_id(row[columns["origin_id"]], "origin_id", row_number)
        destination_id = _normalize_id(row[columns["destination_id"]], "destination_id", row_number)
        minutes = _parse_non_negative_int(row[columns["travel_time_minutes"]], columns["travel_time_minutes"], row_number)
        travel_times.append(TravelTime(origin_id=origin_id, destination_id=destination_id, minutes=minutes))

    return travel_times


def load_compatibilities(config: OptimizerConfig, base_dir: Path | None = None) -> list[Compatibility]:
    """Charge les compatibilites si un fichier est configure et present.

    Si aucun fichier n'est configure, une liste vide est retournee. Les
    compatibilites absentes seront interpretees comme autorisees par defaut
    lors de la construction de `b_ij`.

    Parameters
    ----------
    config : OptimizerConfig
        Configuration contenant le chemin optionnel et les colonnes.
    base_dir : Path | None, default=None
        Repertoire de base pour resoudre un chemin relatif.

    Returns
    -------
    list[Compatibility]
        Compatibilites explicites. Une liste vide signifie qu'aucun fichier
        n'est configure ou trouve.

    Raises
    ------
    DataLoadingError
        Si le fichier configure existe mais que ses colonnes ou valeurs sont
        invalides.
    """

    if config.inputs.compatibility_path is None:
        return []

    path = _resolve_path(config.inputs.compatibility_path, base_dir)
    if not path.exists():
        return []

    columns = config.columns
    allowed_column = columns.get("compatibility_allowed")
    if not allowed_column:
        raise DataLoadingError("La colonne de compatibilite doit etre configuree dans columns.compatibility_allowed.")

    required = [columns["origin_id"], columns["destination_id"], allowed_column]
    rows = _read_csv(path, required)

    compatibilities: list[Compatibility] = []
    for row_number, row in rows:
        origin_id = _normalize_id(row[columns["origin_id"]], "origin_id", row_number)
        destination_id = _normalize_id(row[columns["destination_id"]], "destination_id", row_number)
        allowed = _parse_binary_int(row[allowed_column], allowed_column, row_number)
        compatibilities.append(Compatibility(origin_id=origin_id, destination_id=destination_id, allowed=allowed))

    return compatibilities


def _resolve_path(path: Path, base_dir: Path | None) -> Path:
    if path.is_absolute():
        return path
    if base_dir is None:
        return path
    return base_dir / path


def _read_csv(path: Path, required_columns: list[str]) -> list[tuple[int, dict[str, Any]]]:
    if not path.exists():
        raise DataLoadingError(f"Fichier introuvable: {path}.")

    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise DataLoadingError(f"Le fichier CSV est vide ou sans en-tete: {path}.")

        missing = [column for column in required_columns if column not in reader.fieldnames]
        if missing:
            raise DataLoadingError(f"Colonnes obligatoires manquantes dans {path}: {', '.join(missing)}.")

        return [(index, row) for index, row in enumerate(reader, start=2)]


def _normalize_id(value: Any, field_name: str, row_number: int) -> str:
    text = _require_text(value, field_name, row_number)
    return text


def _require_text(value: Any, field_name: str, row_number: int) -> str:
    if value is None:
        raise DataLoadingError(f"Valeur obligatoire manquante pour {field_name} a la ligne {row_number}.")
    text = str(value).strip()
    if not text:
        raise DataLoadingError(f"Valeur obligatoire vide pour {field_name} a la ligne {row_number}.")
    return text


def _parse_non_negative_int(value: Any, field_name: str, row_number: int) -> int:
    text = _require_text(value, field_name, row_number)
    try:
        parsed = int(text)
    except ValueError as exc:
        raise DataLoadingError(f"Valeur entiere invalide pour {field_name} a la ligne {row_number}: {text}.") from exc
    if parsed < 0:
        raise DataLoadingError(f"Valeur negative interdite pour {field_name} a la ligne {row_number}: {parsed}.")
    return parsed


def _parse_binary_int(value: Any, field_name: str, row_number: int) -> int:
    parsed = _parse_non_negative_int(value, field_name, row_number)
    if parsed not in (0, 1):
        raise DataLoadingError(f"Le champ {field_name} doit valoir 0 ou 1 a la ligne {row_number}.")
    return parsed


def _optional_text(row: dict[str, Any], column_name: str | None) -> str | None:
    if not column_name or column_name not in row:
        return None
    value = row[column_name]
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_non_negative_int(row: dict[str, Any], column_name: str | None, row_number: int) -> int | None:
    if not column_name or column_name not in row:
        return None
    value = row[column_name]
    if value is None or str(value).strip() == "":
        return None
    return _parse_non_negative_int(value, column_name, row_number)


def _optional_float(row: dict[str, Any], column_name: str | None, row_number: int) -> float | None:
    if not column_name or column_name not in row:
        return None
    value = row[column_name]
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip().replace(",", ".")
    try:
        return float(text)
    except ValueError as exc:
        raise DataLoadingError(f"Valeur decimale invalide pour {column_name} a la ligne {row_number}: {text}.") from exc
