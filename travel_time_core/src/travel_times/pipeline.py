"""Pipeline de generation des temps de trajet entre communes."""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path

from tqdm import tqdm

from travel_times import db
from travel_times.candidates import build_candidate_routes
from travel_times.config import Settings
from travel_times.data_loading import read_communes_csv
from travel_times.export import (
    export_all,
    export_thresholded,
    write_generation_report,
    write_optimizer_compatible_csv,
)
from travel_times.geocode import GeoApiGouvClient
from travel_times.ign_client import IgnRouteClient
from travel_times.io_ods import read_cities_ods
from travel_times.models import CityRecord, RouteResult
from travel_times.routing_client import OfflineRouteClient, RouteClient
from travel_times.validation import validate_input_file

LOGGER = logging.getLogger(__name__)


def init_project(settings: Settings) -> None:
    """Initialise les dossiers et le cache SQLite.

    Parameters
    ----------
    settings : Settings
        Configuration contenant les chemins d'entree, sortie et cache.
    """

    settings.input.communes_csv_path.parent.mkdir(parents=True, exist_ok=True)
    settings.input.default_ods_path.parent.mkdir(parents=True, exist_ok=True)
    settings.output.directory.mkdir(parents=True, exist_ok=True)
    settings.database.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    with db.connect(settings.database.sqlite_path) as conn:
        db.init_db(conn)


def validate_input(path: Path, sheet_name: str | int | None = None) -> int:
    """Valide un fichier ODS de communes.

    Parameters
    ----------
    path : Path
        Chemin du fichier ODS a controler.
    sheet_name : str | int | None, default=None
        Feuille a lire.

    Returns
    -------
    int
        Nombre de communes valides.
    """

    cities = validate_input_file(path, sheet_name=sheet_name)
    return len(cities)


def import_cities(
    conn: sqlite3.Connection,
    input_path: Path,
    sheet_name: str | int | None = None,
) -> int:
    """Importe les communes d'un ODS dans le cache SQLite.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.
    input_path : Path
        Chemin du fichier ODS.
    sheet_name : str | int | None, default=None
        Feuille a lire.

    Returns
    -------
    int
        Nombre de communes inserees ou mises a jour.
    """

    cities = read_cities_ods(input_path, sheet_name=sheet_name)
    return db.upsert_cities(conn, cities)


def import_communes_csv(conn: sqlite3.Connection, settings: Settings) -> int:
    """Importe les communes depuis le CSV configure.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.
    settings : Settings
        Configuration contenant le chemin CSV et les colonnes.

    Returns
    -------
    int
        Nombre de communes inserees ou mises a jour.
    """

    cities = read_communes_csv(settings.input.communes_csv_path, settings.columns)
    return db.upsert_city_records(conn, cities)


def geocode_cities(
    conn: sqlite3.Connection,
    client: GeoApiGouvClient,
    *,
    refresh: bool = False,
    only_missing: bool = False,
) -> tuple[int, int]:
    """Geocode les communes du cache avec geo.api.gouv.fr.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.
    client : GeoApiGouvClient
        Client de geocodage.
    refresh : bool, default=False
        Recalcule toutes les communes.
    only_missing : bool, default=False
        Ne traite que les communes sans coordonnees valides.

    Returns
    -------
    tuple[int, int]
        Nombre de geocodages reussis puis en erreur.
    """

    cities = db.fetch_cities_for_geocode(conn, refresh=refresh, only_missing=only_missing)
    ok = 0
    failed = 0
    for city in tqdm(cities, desc="Geocodage", unit="commune"):
        result = client.geocode_insee(city.insee_code)
        db.update_city_geocode(conn, result)
        if result.status == "ok":
            ok += 1
        else:
            failed += 1
            LOGGER.warning("%s %s non geocodee: %s", city.insee_code, city.name, result.error)
    return ok, failed


def build_and_store_candidates(
    conn: sqlite3.Connection,
    *,
    k_default: int,
    k_pc: int,
    k_tpc: int,
) -> int:
    """Construit et stocke les couples commune-pivot candidats.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.
    k_default : int
        Nombre de candidats pour une commune standard.
    k_pc : int
        Nombre de candidats pour une commune PC.
    k_tpc : int
        Nombre de candidats pour une commune TPC.

    Returns
    -------
    int
        Nombre de couples candidats stockes.
    """

    cities = db.fetch_cities(conn, geocoded_only=True)
    routes = build_candidate_routes(cities, k_default=k_default, k_pc=k_pc, k_tpc=k_tpc)
    return db.upsert_candidate_routes(conn, routes, clear=True)


def compute_batch(
    conn: sqlite3.Connection,
    client: RouteClient,
    *,
    only_missing: bool = True,
    refresh: bool = False,
    limit: int | None = None,
    dry_run: bool = False,
) -> int:
    """Calcule un lot de trajets candidats et les stocke dans le cache.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.
    client : RouteClient
        Client de calcul de trajet.
    only_missing : bool, default=True
        Ignore les trajets deja presents dans le cache.
    refresh : bool, default=False
        Recalcule les trajets meme s'ils existent.
    limit : int | None, default=None
        Nombre maximal de couples a traiter.
    dry_run : bool, default=False
        Compte les couples sans appeler le client ni ecrire les resultats.

    Returns
    -------
    int
        Nombre de trajets calcules ou qui seraient calcules en dry-run.
    """

    pairs = db.fetch_candidate_pairs(conn, only_missing=(only_missing and not refresh), limit=limit)
    if dry_run:
        LOGGER.info("Dry run: %s trajets seraient calcules", len(pairs))
        return len(pairs)
    computed = 0
    for row in tqdm(pairs, desc="Calcul IGN", unit="trajet"):
        origin = CityRecord(
            insee_code=row["origin_insee"],
            name="",
            commune_type="STANDARD",
            lat=row["origin_lat"],
            lon=row["origin_lon"],
        )
        destination = CityRecord(
            insee_code=row["destination_insee"],
            name="",
            commune_type="STANDARD",
            lat=row["dest_lat"],
            lon=row["dest_lon"],
        )
        result = client.route(origin, destination)
        db.upsert_travel_time(conn, result)
        computed += 1
    return computed


def compute_specific_route(
    conn: sqlite3.Connection,
    client: IgnRouteClient,
    *,
    from_insee: str | None = None,
    to_insee: str | None = None,
    from_name: str | None = None,
    to_name: str | None = None,
    refresh: bool = False,
) -> RouteResult:
    """Calcule ou relit un trajet specifique demande par l'utilisateur.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.
    client : IgnRouteClient
        Client de routage IGN.
    from_insee : str | None, default=None
        Code commune origine.
    to_insee : str | None, default=None
        Code commune destination.
    from_name : str | None, default=None
        Nom de la commune origine.
    to_name : str | None, default=None
        Nom de la commune destination.
    refresh : bool, default=False
        Force le recalcul meme si le trajet existe en cache.

    Returns
    -------
    RouteResult
        Resultat du trajet.

    Raises
    ------
    ValueError
        Si l'origine ou la destination est introuvable.
    """

    origin = db.find_city(conn, insee_code=from_insee, name=from_name)
    destination = db.find_city(conn, insee_code=to_insee, name=to_name)
    if origin is None:
        raise ValueError("Commune de depart introuvable")
    if destination is None:
        raise ValueError("Commune d'arrivee introuvable")
    existing = db.get_travel_time(conn, origin.insee_code, destination.insee_code)
    if existing is not None and not refresh:
        result = RouteResult(
            origin_insee=origin.insee_code,
            destination_insee=destination.insee_code,
            route_status=existing["route_status"],
            duration_sec=existing["duration_sec"],
            distance_m=existing["distance_m"],
            api_status_code=existing["api_status_code"],
            api_error=existing["api_error"],
            requested_by_user=True,
            resource=existing["resource"],
        )
        db.upsert_travel_time(conn, result)
        return result
    result = client.route(origin, destination, requested_by_user=True)
    db.upsert_travel_time(conn, result)
    return result


def export_outputs(conn: sqlite3.Connection, output_dir: Path) -> dict[str, Path]:
    """Ecrit les exports complets depuis le cache.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.
    output_dir : Path
        Dossier de sortie.

    Returns
    -------
    dict[str, Path]
        Chemins des fichiers produits.
    """

    return export_all(conn, output_dir)


def export_threshold_outputs(
    conn: sqlite3.Connection,
    output_dir: Path,
    thresholds: list[int],
) -> dict[str, Path]:
    """Ecrit les exports filtres par seuils de temps.

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
        Chemins des fichiers produits.
    """

    return export_thresholded(conn, output_dir, thresholds)


def run_all(
    settings: Settings,
    input_path: Path,
    *,
    dry_run: bool = False,
) -> None:
    """Execute l'ancien pipeline complet depuis un ODS.

    Parameters
    ----------
    settings : Settings
        Configuration du pipeline.
    input_path : Path
        Fichier ODS d'entree.
    dry_run : bool, default=False
        Ne produit pas les exports finaux si actif.
    """

    init_project(settings)
    validate_input(input_path, sheet_name=settings.input.sheet_name)
    with db.connect(settings.database.sqlite_path) as conn:
        db.init_db(conn)
        imported = import_cities(conn, input_path, sheet_name=settings.input.sheet_name)
        LOGGER.info("%s communes importees", imported)
        geo_client = GeoApiGouvClient(settings.geocode)
        ok, failed = geocode_cities(conn, geo_client, only_missing=True)
        LOGGER.info("Geocodage termine: %s ok, %s erreurs", ok, failed)
        candidates_count = build_and_store_candidates(
            conn,
            k_default=settings.candidates.k_default,
            k_pc=settings.candidates.k_pc,
            k_tpc=settings.candidates.k_tpc,
        )
        LOGGER.info("%s candidates stockees", candidates_count)
        route_client = IgnRouteClient(
            settings.ign,
            raw_response_dir=settings.database.sqlite_path.parent / "raw_ign",
        )
        compute_batch(conn, route_client, only_missing=True, dry_run=dry_run)
        if not dry_run:
            export_outputs(conn, settings.output.directory)


def validate_settings(settings: Settings) -> None:
    """Valide les parametres d'execution du pipeline configure.

    Parameters
    ----------
    settings : Settings
        Configuration a controler.

    Raises
    ------
    ValueError
        Si le format, le mode, l'autorisation reseau ou les seuils sont
        incoherents.
    """

    if settings.input.format not in {"csv", "ods"}:
        raise ValueError("input.format doit valoir 'csv' ou 'ods'")
    if settings.runtime.mode not in {"offline", "ign"}:
        raise ValueError("runtime.mode doit valoir 'offline' ou 'ign'")
    if settings.runtime.mode == "ign" and not settings.runtime.allow_network:
        raise ValueError("runtime.allow_network doit etre true pour utiliser le mode ign")
    if not settings.output.thresholds_minutes:
        raise ValueError("output.thresholds_minutes doit contenir au moins un seuil")
    if any(threshold <= 0 for threshold in settings.output.thresholds_minutes):
        raise ValueError("Les seuils output.thresholds_minutes doivent etre positifs")


def import_configured_communes(conn: sqlite3.Connection, settings: Settings) -> int:
    """Importe les communes selon le format configure.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.
    settings : Settings
        Configuration contenant format et chemins d'entree.

    Returns
    -------
    int
        Nombre de communes inserees ou mises a jour.
    """

    if settings.input.format == "csv":
        return import_communes_csv(conn, settings)
    return import_cities(conn, settings.input.default_ods_path, sheet_name=settings.input.sheet_name)


def route_client_for_settings(settings: Settings) -> RouteClient:
    """Construit le client de trajet correspondant au mode configure.

    Parameters
    ----------
    settings : Settings
        Configuration contenant le mode runtime.

    Returns
    -------
    RouteClient
        Client offline ou IGN.

    Raises
    ------
    ValueError
        Si le mode IGN est demande sans autorisation reseau.
    """

    if settings.runtime.mode == "ign":
        if not settings.runtime.allow_network:
            raise ValueError("Appel reseau refuse: activez runtime.allow_network pour le mode ign")
        return IgnRouteClient(
            settings.ign,
            raw_response_dir=settings.database.sqlite_path.parent / "raw_ign",
        )
    return OfflineRouteClient(settings.runtime)


def compute_configured_routes(
    conn: sqlite3.Connection,
    settings: Settings,
    *,
    only_missing: bool = True,
    refresh: bool = False,
    dry_run: bool = False,
) -> int:
    """Calcule les trajets selon la configuration runtime.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.
    settings : Settings
        Configuration du pipeline.
    only_missing : bool, default=True
        Ignore les trajets deja presents.
    refresh : bool, default=False
        Force le recalcul.
    dry_run : bool, default=False
        Compte les couples sans ecrire.

    Returns
    -------
    int
        Nombre de trajets traites ou prevus.
    """

    return compute_batch(
        conn,
        route_client_for_settings(settings),
        only_missing=only_missing,
        refresh=refresh,
        limit=settings.runtime.max_couples,
        dry_run=dry_run,
    )


def export_configured_outputs(conn: sqlite3.Connection, settings: Settings) -> dict[str, Path]:
    """Ecrit les exports complets, filtres et compatibles optimiseur.

    Parameters
    ----------
    conn : sqlite3.Connection
        Connexion SQLite ouverte.
    settings : Settings
        Configuration des dossiers, seuils et rapport.

    Returns
    -------
    dict[str, Path]
        Chemins des exports produits.
    """

    paths = export_outputs(conn, settings.output.directory)
    paths.update(export_threshold_outputs(conn, settings.output.directory, settings.output.thresholds_minutes))
    paths["optimizer_compatible_configured"] = write_optimizer_compatible_csv(
        conn,
        settings.output.compatible_csv_path,
    )
    stats = db.travel_time_stats(conn)
    stats.update(
        {
            "output_directory": str(settings.output.directory),
            "compatible_csv_path": str(settings.output.compatible_csv_path),
            "thresholds_minutes": settings.output.thresholds_minutes,
            "runtime_mode": settings.runtime.mode,
            "allow_network": settings.runtime.allow_network,
            "max_couples": settings.runtime.max_couples,
        }
    )
    paths["generation_report"] = write_generation_report(settings.output.report_json_path, stats)
    return paths


def run_configured_pipeline(settings: Settings, *, dry_run: bool = False) -> dict[str, Path]:
    """Execute le pipeline configure de bout en bout.

    Parameters
    ----------
    settings : Settings
        Configuration complete du sous-projet.
    dry_run : bool, default=False
        Initialise et calcule les volumes sans ecrire les exports.

    Returns
    -------
    dict[str, Path]
        Chemins des exports produits, ou dictionnaire vide en dry-run.
    """

    validate_settings(settings)
    start = time.monotonic()
    init_project(settings)
    with db.connect(settings.database.sqlite_path) as conn:
        db.init_db(conn)
        imported = import_configured_communes(conn, settings)
        LOGGER.info("%s communes importees", imported)
        candidates_count = build_and_store_candidates(
            conn,
            k_default=settings.candidates.k_default,
            k_pc=settings.candidates.k_pc,
            k_tpc=settings.candidates.k_tpc,
        )
        LOGGER.info("%s candidates stockees", candidates_count)
        computed = compute_configured_routes(conn, settings, only_missing=True, dry_run=dry_run)
        LOGGER.info("%s trajets traites", computed)
        if dry_run:
            return {}
        paths = export_configured_outputs(conn, settings)
        stats = db.travel_time_stats(conn)
        stats.update(
            {
                "routes_computed_this_run": computed,
                "routes_from_cache_estimate": max(stats["travel_times_total"] - computed, 0),
                "elapsed_seconds": round(time.monotonic() - start, 3),
                "runtime_mode": settings.runtime.mode,
                "allow_network": settings.runtime.allow_network,
                "max_couples": settings.runtime.max_couples,
                "compatible_csv_path": str(settings.output.compatible_csv_path),
                "thresholds_minutes": settings.output.thresholds_minutes,
            }
        )
        write_generation_report(settings.output.report_json_path, stats)
        return paths
