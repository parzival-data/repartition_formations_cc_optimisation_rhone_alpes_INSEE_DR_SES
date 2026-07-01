"""Acces SQLite pour le cache des communes, candidats et trajets."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from travel_times.models import (
    CandidateRoute,
    CityInput,
    CityRecord,
    GeocodeResult,
    RouteResult,
)


def utc_now() -> str:
    """Retourne l'horodatage UTC courant.

    Returns
    -------
    str
        Date ISO en secondes.
    """

    return datetime.now(UTC).isoformat(timespec="seconds")


def connect(db_path: Path) -> sqlite3.Connection:
    """Ouvre une connexion SQLite configuree pour le cache local.

    Parameters
    ----------
    db_path : Path
        Chemin de la base SQLite.

    Returns
    -------
    sqlite3.Connection
        Connexion avec lignes accessibles par nom de colonne.
    """

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Cree les tables et index du cache si necessaire.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.
    """

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS cities (
          insee_code TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          commune_type TEXT NOT NULL DEFAULT 'STANDARD',
          lat REAL,
          lon REAL,
          coord_source TEXT,
          population INTEGER,
          department_code TEXT,
          region_code TEXT,
          geocode_status TEXT NOT NULL DEFAULT 'pending',
          geocode_error TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS candidate_routes (
          origin_insee TEXT NOT NULL,
          destination_insee TEXT NOT NULL,
          air_distance_km REAL NOT NULL,
          air_rank INTEGER NOT NULL,
          candidate_policy TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY (origin_insee, destination_insee)
        );

        CREATE TABLE IF NOT EXISTS travel_times (
          origin_insee TEXT NOT NULL,
          destination_insee TEXT NOT NULL,
          mode TEXT NOT NULL DEFAULT 'car',
          duration_sec INTEGER,
          distance_m INTEGER,
          engine TEXT NOT NULL DEFAULT 'ign-geoplateforme',
          resource TEXT,
          route_status TEXT NOT NULL,
          api_status_code INTEGER,
          api_error TEXT,
          requested_by_user INTEGER NOT NULL DEFAULT 0,
          computed_at TEXT NOT NULL,
          PRIMARY KEY (origin_insee, destination_insee, mode)
        );

        CREATE INDEX IF NOT EXISTS idx_candidate_origin ON candidate_routes(origin_insee);
        CREATE INDEX IF NOT EXISTS idx_travel_status ON travel_times(route_status);
        """
    )
    conn.commit()


def upsert_cities(conn: sqlite3.Connection, cities: Iterable[CityInput]) -> int:
    """Insere ou met a jour les communes minimales.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.
    cities : Iterable[CityInput]
        Communes a persister.

    Returns
    -------
    int
        Nombre de communes traitees.
    """

    now = utc_now()
    count = 0
    for city in cities:
        conn.execute(
            """
            INSERT INTO cities (
                insee_code, name, commune_type, geocode_status, created_at, updated_at
            )
            VALUES (?, ?, ?, 'pending', ?, ?)
            ON CONFLICT(insee_code) DO UPDATE SET
                name = excluded.name,
                commune_type = excluded.commune_type,
                updated_at = excluded.updated_at
            """,
            (city.insee_code, city.name, city.commune_type, now, now),
        )
        count += 1
    conn.commit()
    return count


def upsert_city_records(conn: sqlite3.Connection, cities: Iterable[CityRecord]) -> int:
    """Insere ou met a jour des communes enrichies.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.
    cities : Iterable[CityRecord]
        Communes enrichies a persister.

    Returns
    -------
    int
        Nombre de communes traitees.
    """

    now = utc_now()
    count = 0
    for city in cities:
        conn.execute(
            """
            INSERT INTO cities (
                insee_code, name, commune_type, lat, lon, coord_source, population,
                department_code, region_code, geocode_status, geocode_error,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(insee_code) DO UPDATE SET
                name = excluded.name,
                commune_type = excluded.commune_type,
                lat = excluded.lat,
                lon = excluded.lon,
                coord_source = excluded.coord_source,
                population = excluded.population,
                department_code = excluded.department_code,
                region_code = excluded.region_code,
                geocode_status = excluded.geocode_status,
                geocode_error = excluded.geocode_error,
                updated_at = excluded.updated_at
            """,
            (
                city.insee_code,
                city.name,
                city.commune_type,
                city.lat,
                city.lon,
                city.coord_source,
                city.population,
                city.department_code,
                city.region_code,
                city.geocode_status,
                city.geocode_error,
                now,
                now,
            ),
        )
        count += 1
    conn.commit()
    return count


def update_city_geocode(conn: sqlite3.Connection, result: GeocodeResult) -> None:
    """Met a jour les coordonnees et le statut de geocodage d'une commune.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.
    result : GeocodeResult
        Resultat de geocodage a appliquer.
    """

    conn.execute(
        """
        UPDATE cities
        SET lat = ?, lon = ?, coord_source = ?, population = ?, department_code = ?,
            region_code = ?, geocode_status = ?, geocode_error = ?, updated_at = ?
        WHERE insee_code = ?
        """,
        (
            result.lat,
            result.lon,
            result.coord_source,
            result.population,
            result.department_code,
            result.region_code,
            result.status,
            result.error,
            utc_now(),
            result.insee_code,
        ),
    )
    conn.commit()


def upsert_candidate_routes(
    conn: sqlite3.Connection,
    routes: Iterable[CandidateRoute],
    clear: bool = True,
) -> int:
    """Insere ou remplace les couples commune-pivot candidats.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.
    routes : Iterable[CandidateRoute]
        Couples candidats a persister.
    clear : bool, default=True
        Vide la table des candidats avant insertion.

    Returns
    -------
    int
        Nombre de couples candidats traites.
    """

    if clear:
        conn.execute("DELETE FROM candidate_routes")
    now = utc_now()
    count = 0
    for route in routes:
        conn.execute(
            """
            INSERT INTO candidate_routes (
                origin_insee, destination_insee, air_distance_km, air_rank,
                candidate_policy, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(origin_insee, destination_insee) DO UPDATE SET
                air_distance_km = excluded.air_distance_km,
                air_rank = excluded.air_rank,
                candidate_policy = excluded.candidate_policy,
                created_at = excluded.created_at
            """,
            (
                route.origin_insee,
                route.destination_insee,
                route.air_distance_km,
                route.air_rank,
                route.candidate_policy,
                now,
            ),
        )
        count += 1
    conn.commit()
    return count


def upsert_travel_time(conn: sqlite3.Connection, result: RouteResult) -> None:
    """Insere ou met a jour un temps de trajet dans le cache.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.
    result : RouteResult
        Resultat de trajet a persister.
    """

    conn.execute(
        """
        INSERT INTO travel_times (
            origin_insee, destination_insee, mode, duration_sec, distance_m, engine, resource,
            route_status, api_status_code, api_error, requested_by_user, computed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(origin_insee, destination_insee, mode) DO UPDATE SET
            duration_sec = excluded.duration_sec,
            distance_m = excluded.distance_m,
            engine = excluded.engine,
            resource = excluded.resource,
            route_status = excluded.route_status,
            api_status_code = excluded.api_status_code,
            api_error = excluded.api_error,
            requested_by_user = CASE
                WHEN travel_times.requested_by_user = 1 OR excluded.requested_by_user = 1 THEN 1
                ELSE 0
            END,
            computed_at = excluded.computed_at
        """,
        (
            result.origin_insee,
            result.destination_insee,
            result.mode,
            result.duration_sec,
            result.distance_m,
            result.engine,
            result.resource,
            result.route_status,
            result.api_status_code,
            result.api_error,
            1 if result.requested_by_user else 0,
            utc_now(),
        ),
    )
    conn.commit()


def fetch_cities(conn: sqlite3.Connection, geocoded_only: bool = False) -> list[CityRecord]:
    """Retourne les communes stockees dans le cache.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.
    geocoded_only : bool, default=False
        Limite le resultat aux communes avec coordonnees valides.

    Returns
    -------
    list[CityRecord]
        Communes triees par nom puis code.
    """

    query = "SELECT * FROM cities"
    if geocoded_only:
        query += " WHERE geocode_status = 'ok' AND lat IS NOT NULL AND lon IS NOT NULL"
    query += " ORDER BY name, insee_code"
    rows = conn.execute(query).fetchall()
    return [_city_from_row(row) for row in rows]


def fetch_cities_for_geocode(
    conn: sqlite3.Connection,
    refresh: bool = False,
    only_missing: bool = False,
) -> list[CityRecord]:
    """Retourne les communes a geocoder.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.
    refresh : bool, default=False
        Selectionne toutes les communes.
    only_missing : bool, default=False
        Selectionne uniquement les communes sans coordonnees valides.

    Returns
    -------
    list[CityRecord]
        Communes candidates au geocodage.
    """

    if refresh:
        query = "SELECT * FROM cities ORDER BY name"
    elif only_missing:
        query = """
            SELECT * FROM cities
            WHERE geocode_status != 'ok' OR lat IS NULL OR lon IS NULL
            ORDER BY name
        """
    else:
        query = "SELECT * FROM cities WHERE geocode_status = 'pending' ORDER BY name"
    return [_city_from_row(row) for row in conn.execute(query).fetchall()]


def fetch_candidate_pairs(
    conn: sqlite3.Connection,
    only_missing: bool = True,
    limit: int | None = None,
) -> list[sqlite3.Row]:
    """Retourne les couples candidats prets au calcul de trajet.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.
    only_missing : bool, default=True
        Exclut les trajets deja calcules.
    limit : int | None, default=None
        Limite maximale de couples retournes.

    Returns
    -------
    list[sqlite3.Row]
        Couples avec coordonnees origine et destination.
    """

    query = """
        SELECT cr.*, oc.lat AS origin_lat, oc.lon AS origin_lon,
               dc.lat AS dest_lat, dc.lon AS dest_lon
        FROM candidate_routes cr
        JOIN cities oc ON oc.insee_code = cr.origin_insee
        JOIN cities dc ON dc.insee_code = cr.destination_insee
        LEFT JOIN travel_times tt
          ON tt.origin_insee = cr.origin_insee
         AND tt.destination_insee = cr.destination_insee
         AND tt.mode = 'car'
        WHERE oc.geocode_status = 'ok'
          AND dc.geocode_status = 'ok'
          AND oc.lat IS NOT NULL AND oc.lon IS NOT NULL
          AND dc.lat IS NOT NULL AND dc.lon IS NOT NULL
    """
    params: list[Any] = []
    if only_missing:
        query += " AND tt.origin_insee IS NULL"
    query += " ORDER BY cr.origin_insee, cr.air_rank"
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    return conn.execute(query, params).fetchall()


def find_city(
    conn: sqlite3.Connection,
    *,
    insee_code: str | None = None,
    name: str | None = None,
) -> CityRecord | None:
    """Recherche une commune par code ou par nom.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.
    insee_code : str | None, default=None
        Code commune recherche.
    name : str | None, default=None
        Nom de commune recherche.

    Returns
    -------
    CityRecord | None
        Commune trouvee, ou ``None``.
    """

    if insee_code:
        row = conn.execute("SELECT * FROM cities WHERE insee_code = ?", (insee_code,)).fetchone()
    elif name:
        row = conn.execute(
            "SELECT * FROM cities WHERE lower(name) = lower(?) ORDER BY name LIMIT 1",
            (name,),
        ).fetchone()
    else:
        row = None
    return _city_from_row(row) if row else None


def get_travel_time(
    conn: sqlite3.Connection,
    origin: str,
    destination: str,
    mode: str = "car",
) -> sqlite3.Row | None:
    """Retourne un trajet stocke dans le cache.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.
    origin : str
        Code commune origine.
    destination : str
        Code commune destination.
    mode : str, default="car"
        Mode de transport.

    Returns
    -------
    sqlite3.Row | None
        Ligne de trajet, ou ``None`` si absente.
    """

    return conn.execute(
        """
        SELECT * FROM travel_times
        WHERE origin_insee = ? AND destination_insee = ? AND mode = ?
        """,
        (origin, destination, mode),
    ).fetchone()


def travel_time_stats(conn: sqlite3.Connection) -> dict[str, int]:
    """Calcule les statistiques globales du cache de trajets.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.

    Returns
    -------
    dict[str, int]
        Compteurs de communes, candidats et trajets.
    """

    row = conn.execute(
        """
        SELECT
          COUNT(*) AS total,
          SUM(CASE WHEN route_status = 'ok' THEN 1 ELSE 0 END) AS ok_count,
          SUM(CASE WHEN route_status != 'ok' THEN 1 ELSE 0 END) AS error_count
        FROM travel_times
        """
    ).fetchone()
    candidates = conn.execute("SELECT COUNT(*) AS count FROM candidate_routes").fetchone()["count"]
    cities = conn.execute("SELECT COUNT(*) AS count FROM cities").fetchone()["count"]
    return {
        "communes": int(cities or 0),
        "candidate_pairs": int(candidates or 0),
        "travel_times_total": int(row["total"] or 0),
        "travel_times_ok": int(row["ok_count"] or 0),
        "travel_times_error": int(row["error_count"] or 0),
    }


def _city_from_row(row: sqlite3.Row) -> CityRecord:
    return CityRecord(
        insee_code=row["insee_code"],
        name=row["name"],
        commune_type=row["commune_type"],
        lat=row["lat"],
        lon=row["lon"],
        coord_source=row["coord_source"],
        population=row["population"],
        department_code=row["department_code"],
        region_code=row["region_code"],
        geocode_status=row["geocode_status"],
        geocode_error=row["geocode_error"],
    )
