"""Exports des temps de trajet calcules depuis le cache SQLite."""

from __future__ import annotations

import logging
import math
import sqlite3
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from travel_times.io_ods import write_ods

LOGGER = logging.getLogger(__name__)


def export_all(conn: sqlite3.Connection, output_dir: Path) -> dict[str, Path]:
    """Ecrit tous les exports de communes, candidats, trajets et matrice.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.
    output_dir : Path
        Dossier de sortie.

    Returns
    -------
    dict[str, Path]
        Chemins des fichiers ODS et CSV produits.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Preparation de l'export des communes")
    cities = pd.read_sql_query(
        """
        SELECT insee_code, name, commune_type, lat, lon, coord_source, population,
               department_code, region_code, geocode_status, geocode_error
        FROM cities
        ORDER BY name, insee_code
        """,
        conn,
    )
    LOGGER.info("Preparation de l'export des candidates")
    candidates = pd.read_sql_query(
        """
        SELECT cr.origin_insee, oc.name AS origin_name, oc.commune_type AS origin_type,
               cr.destination_insee, dc.name AS destination_name,
               dc.commune_type AS destination_type,
               cr.air_distance_km, cr.air_rank, cr.candidate_policy, cr.created_at
        FROM candidate_routes cr
        JOIN cities oc ON oc.insee_code = cr.origin_insee
        JOIN cities dc ON dc.insee_code = cr.destination_insee
        ORDER BY cr.origin_insee, cr.air_rank
        """,
        conn,
    )
    LOGGER.info("Preparation de l'export sparse")
    sparse = travel_times_sparse_df(conn)
    errors = sparse[sparse["route_status"] != "ok"].copy() if not sparse.empty else sparse
    LOGGER.info("Preparation de la matrice minutes")
    matrix = travel_times_matrix_minutes_df(conn)

    paths = {
        "cities_geocoded": output_dir / "cities_geocoded.ods",
        "candidate_routes": output_dir / "candidate_routes.ods",
        "travel_times_sparse_ods": output_dir / "travel_times_sparse.ods",
        "travel_times_sparse_csv": output_dir / "travel_times_sparse.csv",
        "travel_times_matrix_minutes": output_dir / "travel_times_matrix_minutes.ods",
        "travel_times_matrix_minutes_csv": output_dir / "travel_times_matrix_minutes.csv",
        "optimizer_compatible_csv": output_dir / "temps_trajet_clean.csv",
        "errors": output_dir / "errors.ods",
    }
    LOGGER.info("Ecriture cities_geocoded.ods (%s lignes)", len(cities))
    write_ods(paths["cities_geocoded"], {"cities": cities})
    LOGGER.info("Ecriture candidate_routes.ods (%s lignes)", len(candidates))
    write_ods(paths["candidate_routes"], {"candidate_routes": candidates})
    LOGGER.info("Ecriture travel_times_sparse.ods (%s lignes)", len(sparse))
    write_ods(paths["travel_times_sparse_ods"], {"travel_times_sparse": sparse})
    LOGGER.info("Ecriture travel_times_sparse.csv (%s lignes)", len(sparse))
    sparse.to_csv(paths["travel_times_sparse_csv"], index=False)
    LOGGER.info("Ecriture travel_times_matrix_minutes.ods (%s lignes)", len(matrix))
    write_ods(paths["travel_times_matrix_minutes"], {"matrix_minutes": matrix})
    LOGGER.info("Ecriture travel_times_matrix_minutes.csv (%s lignes)", len(matrix))
    matrix.to_csv(paths["travel_times_matrix_minutes_csv"], index=False)
    compatible = optimizer_compatible_travel_times_df(conn)
    LOGGER.info("Ecriture temps_trajet_clean.csv (%s lignes)", len(compatible))
    compatible.to_csv(paths["optimizer_compatible_csv"], index=False)
    LOGGER.info("Ecriture errors.ods (%s lignes)", len(errors))
    write_ods(paths["errors"], {"errors": errors})
    return paths


def export_thresholded(
    conn: sqlite3.Connection,
    output_dir: Path,
    thresholds: list[int],
) -> dict[str, Path]:
    """Ecrit des exports filtres par seuil de duree.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.
    output_dir : Path
        Dossier de sortie.
    thresholds : list[int]
        Seuils de duree en minutes.

    Returns
    -------
    dict[str, Path]
        Chemins des fichiers produits par seuil.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    sparse = travel_times_sparse_df(conn)
    paths: dict[str, Path] = {}
    for threshold in thresholds:
        LOGGER.info("Preparation exports filtres <= %s min", threshold)
        filtered_sparse = filter_sparse_by_duration(sparse, threshold)
        matrix = travel_times_matrix_minutes_df(conn, max_minutes=threshold)
        suffix = f"max_{threshold}min"
        sparse_csv = output_dir / f"travel_times_sparse_{suffix}.csv"
        sparse_ods = output_dir / f"travel_times_sparse_{suffix}.ods"
        matrix_ods = output_dir / f"travel_times_matrix_minutes_{suffix}.ods"
        matrix_csv = output_dir / f"travel_times_matrix_minutes_{suffix}.csv"
        LOGGER.info("Ecriture %s (%s lignes)", sparse_csv.name, len(filtered_sparse))
        filtered_sparse.to_csv(sparse_csv, index=False)
        LOGGER.info("Ecriture %s (%s lignes)", sparse_ods.name, len(filtered_sparse))
        write_ods(sparse_ods, {"travel_times_sparse": filtered_sparse})
        LOGGER.info("Ecriture %s (%s lignes)", matrix_ods.name, len(matrix))
        write_ods(matrix_ods, {"matrix_minutes": matrix})
        LOGGER.info("Ecriture %s (%s lignes)", matrix_csv.name, len(matrix))
        matrix.to_csv(matrix_csv, index=False)
        paths[f"sparse_csv_{threshold}"] = sparse_csv
        paths[f"sparse_ods_{threshold}"] = sparse_ods
        paths[f"matrix_ods_{threshold}"] = matrix_ods
        paths[f"matrix_csv_{threshold}"] = matrix_csv
    return paths


def filter_sparse_by_duration(sparse: pd.DataFrame, max_minutes: int | float) -> pd.DataFrame:
    """Filtre un export sparse aux trajets OK sous un seuil.

    Parameters
    ----------
    sparse : pd.DataFrame
        Table sparse de trajets.
    max_minutes : int | float
        Duree maximale en minutes.

    Returns
    -------
    pd.DataFrame
        Copie filtree de la table sparse.
    """

    if sparse.empty:
        return sparse.copy()
    duration = pd.to_numeric(sparse["duration_min"], errors="coerce")
    return sparse[(sparse["route_status"] == "ok") & (duration <= max_minutes)].copy()


def travel_times_sparse_df(conn: sqlite3.Connection) -> pd.DataFrame:
    """Construit la table sparse des trajets stockes.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.

    Returns
    -------
    pd.DataFrame
        Trajets orientes avec duree, distance et statut.
    """

    return pd.read_sql_query(
        """
        SELECT
          tt.origin_insee,
          oc.name AS origin_name,
          oc.commune_type AS origin_type,
          tt.destination_insee,
          dc.name AS destination_name,
          dc.commune_type AS destination_type,
          cr.air_distance_km,
          cr.air_rank,
          tt.duration_sec,
          CASE
            WHEN tt.duration_sec IS NOT NULL THEN ROUND(tt.duration_sec / 60.0, 2)
          END AS duration_min,
          tt.distance_m,
          CASE
            WHEN tt.distance_m IS NOT NULL THEN ROUND(tt.distance_m / 1000.0, 3)
          END AS distance_km,
          tt.route_status,
          tt.requested_by_user,
          tt.computed_at
        FROM travel_times tt
        JOIN cities oc ON oc.insee_code = tt.origin_insee
        JOIN cities dc ON dc.insee_code = tt.destination_insee
        LEFT JOIN candidate_routes cr
          ON cr.origin_insee = tt.origin_insee
         AND cr.destination_insee = tt.destination_insee
        ORDER BY oc.name, dc.name
        """,
        conn,
    )


def travel_times_matrix_minutes_df(
    conn: sqlite3.Connection,
    max_minutes: int | float | None = None,
) -> pd.DataFrame:
    """Construit la matrice des durees en minutes.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.
    max_minutes : int | float | None, default=None
        Seuil optionnel de duree admissible.

    Returns
    -------
    pd.DataFrame
        Matrice origine-destination en minutes.
    """

    sparse = travel_times_sparse_df(conn)
    cities = pd.read_sql_query(
        "SELECT insee_code, name FROM cities ORDER BY name, insee_code",
        conn,
    )
    labels = [f"{row.name} ({row.insee_code})" for row in cities.itertuples(index=False)]
    matrix = pd.DataFrame("", index=labels, columns=labels, dtype=object)
    if sparse.empty:
        matrix.insert(0, "origin", labels)
        return matrix.reset_index(drop=True)
    code_to_label = dict(zip(cities["insee_code"], labels, strict=False))
    ok_rows = sparse[sparse["route_status"] == "ok"].copy()
    if max_minutes is not None:
        duration = pd.to_numeric(ok_rows["duration_min"], errors="coerce")
        ok_rows = ok_rows[duration <= max_minutes]
    for row in ok_rows.itertuples(index=False):
        origin_label = code_to_label.get(row.origin_insee)
        destination_label = code_to_label.get(row.destination_insee)
        if origin_label and destination_label:
            matrix.loc[origin_label, destination_label] = row.duration_min
    matrix.insert(0, "origin", labels)
    return matrix.reset_index(drop=True)


def optimizer_compatible_travel_times_df(conn: sqlite3.Connection) -> pd.DataFrame:
    """Construit le CSV compatible avec l'optimiseur de formations.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.

    Returns
    -------
    pd.DataFrame
        Colonnes ``code_commune_origine``, ``code_commune_pivot`` et
        ``temps_minutes``.
    """

    sparse = travel_times_sparse_df(conn)
    if sparse.empty:
        return pd.DataFrame(
            columns=["code_commune_origine", "code_commune_pivot", "temps_minutes"]
        )
    ok_rows = sparse[sparse["route_status"] == "ok"].copy()
    durations = pd.to_numeric(ok_rows["duration_min"], errors="coerce")
    ok_rows = ok_rows[durations.notna()].copy()
    ok_rows["temps_minutes"] = durations[durations.notna()].map(lambda value: int(math.ceil(value)))
    return ok_rows.rename(
        columns={
            "origin_insee": "code_commune_origine",
            "destination_insee": "code_commune_pivot",
        }
    )[["code_commune_origine", "code_commune_pivot", "temps_minutes"]]


def write_optimizer_compatible_csv(conn: sqlite3.Connection, path: Path) -> Path:
    """Ecrit le CSV compatible avec l'optimiseur.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.
    path : Path
        Chemin du CSV a ecrire.

    Returns
    -------
    Path
        Chemin du fichier produit.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    optimizer_compatible_travel_times_df(conn).to_csv(path, index=False)
    return path


def write_generation_report(path: Path, stats: dict[str, Any]) -> Path:
    """Ecrit le rapport JSON de generation des trajets.

    Parameters
    ----------
    path : Path
        Chemin du JSON a ecrire.
    stats : dict[str, Any]
        Statistiques a inclure dans le rapport.

    Returns
    -------
    Path
        Chemin du fichier produit.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        **stats,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
