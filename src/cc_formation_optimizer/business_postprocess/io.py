"""Lecture et ecriture des fichiers de post-traitement metier."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any

from cc_formation_optimizer.config import OptimizerConfig
from cc_formation_optimizer.data_loading import load_compatibilities, load_travel_times

from cc_formation_optimizer.business_postprocess.types import (
    BusinessPostprocessContext,
    PROPOSAL_COLUMNS,
    SUMMARY_COLUMNS,
    PostprocessError,
    PostprocessResult,
)


def load_context(
    input_dir: str | Path,
    config: OptimizerConfig,
    min_travel_time_gain_min: int,
) -> BusinessPostprocessContext:
    """Charge les exports d'optimisation et les donnees necessaires aux regles."""

    root = Path(input_dir)
    sessions = _read_csv(root / "solutions" / "sessions.csv", _required_session_columns())
    assignments = _read_csv(root / "solutions" / "communes_affectees.csv", _required_assignment_columns())
    travel_times = {
        (travel.origin_id, travel.destination_id): travel.minutes for travel in load_travel_times(config)
    }
    compatibilities = {(item.origin_id, item.destination_id): item.allowed for item in load_compatibilities(config)}

    return BusinessPostprocessContext(
        sessions={str(row["id_session"]): row for row in sessions},
        assignments=assignments,
        assignments_by_session=_group_assignments(assignments),
        assignment_by_commune=_index_assignments_by_commune(assignments),
        travel_times=travel_times,
        compatibilities=compatibilities,
        config=config,
        min_travel_time_gain_min=min_travel_time_gain_min,
    )


def write_outputs(
    output_dir: str | Path,
    proposals: list[dict[str, Any]],
    summary: list[dict[str, Any]],
) -> PostprocessResult:
    """Ecrit les deux CSV de propositions et de synthese."""

    out_dir = Path(output_dir)
    proposals_csv = out_dir / "business_reallocation_proposals.csv"
    summary_csv = out_dir / "business_reallocation_summary.csv"
    _write_csv(proposals_csv, PROPOSAL_COLUMNS, proposals)
    _write_csv(summary_csv, SUMMARY_COLUMNS, summary)
    return PostprocessResult(
        proposals_csv=proposals_csv,
        summary_csv=summary_csv,
        proposal_count=len(proposals),
        summary_count=len(summary),
    )


def default_output_dir(input_dir: str | Path) -> Path:
    """Retourne le dossier de sortie par defaut de la surcouche."""

    return Path(input_dir) / "postprocess"


def _group_assignments(assignments: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in assignments:
        grouped[str(row["id_session"])].append(row)
    return dict(grouped)


def _index_assignments_by_commune(assignments: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in assignments:
        code = str(row["code_commune"])
        if code in indexed:
            raise PostprocessError(f"Commune affectee plusieurs fois dans les exports: {code}.")
        indexed[code] = row
    return indexed


def _read_csv(path: Path, required_columns: list[str]) -> list[dict[str, Any]]:
    if not path.exists():
        raise PostprocessError(f"Fichier d'export introuvable: {path}.")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise PostprocessError(f"Fichier d'export vide ou sans en-tete: {path}.")
        missing = [column for column in required_columns if column not in reader.fieldnames]
        if missing:
            raise PostprocessError(f"Colonnes manquantes dans {path}: {', '.join(missing)}.")
        return [dict(row) for row in reader]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _required_session_columns() -> list[str]:
    return ["id_session", "code_pivot", "nom_pivot", "type_session", "nombre_CC", "temps_trajet_max"]


def _required_assignment_columns() -> list[str]:
    return [
        "code_commune",
        "nom_commune",
        "categorie",
        "territoire_EAR",
        "population",
        "nombre_CC",
        "id_session",
        "code_pivot",
        "nom_pivot",
        "type_session",
        "temps_trajet_minutes",
    ]
