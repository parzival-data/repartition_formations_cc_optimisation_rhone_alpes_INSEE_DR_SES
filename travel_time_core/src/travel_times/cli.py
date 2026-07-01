"""Interface Typer du sous-projet de calcul des temps de trajet."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from travel_times import db
from travel_times.config import load_settings, write_default_settings
from travel_times.geocode import GeoApiGouvClient
from travel_times.ign_client import IgnRouteClient
from travel_times.io_ods import InputValidationError
from travel_times.logging_utils import configure_logging
from travel_times.pipeline import (
    build_and_store_candidates,
    compute_batch,
    compute_configured_routes,
    compute_specific_route,
    export_configured_outputs,
    export_outputs,
    export_threshold_outputs,
    geocode_cities,
    import_configured_communes,
    import_cities,
    init_project,
    run_all,
    run_configured_pipeline,
    validate_settings,
    validate_input,
)

app = typer.Typer(help="Calcul local de matrices de temps de trajet entre communes.")
_CONFIG_PATH = Path("config/config_travel_times.yaml")


def _settings():
    return load_settings(_CONFIG_PATH)


def _parse_thresholds(value: str) -> list[int]:
    thresholds: list[int] = []
    for raw in value.split(","):
        item = raw.strip()
        if not item:
            continue
        try:
            threshold = int(item)
        except ValueError as exc:
            raise typer.BadParameter(f"Seuil invalide: {item}") from exc
        if threshold <= 0:
            raise typer.BadParameter("Les seuils doivent etre strictement positifs")
        thresholds.append(threshold)
    if not thresholds:
        raise typer.BadParameter("Au moins un seuil est requis")
    return thresholds


@app.callback()
def main(
    config: Annotated[
        Path,
        typer.Option("--config", help="Chemin de la configuration travel_time_core."),
    ] = Path("config/config_travel_times.yaml"),
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Configure la CLI avant l'execution d'une commande.

    Parameters
    ----------
    config : Path, default=Path("config/config_travel_times.yaml")
        Chemin du YAML de configuration.
    verbose : bool, default=False
        Active les logs detailles.
    """

    global _CONFIG_PATH
    _CONFIG_PATH = config
    configure_logging(verbose)


@app.command("init")
def init_command() -> None:
    """Initialise la configuration, les dossiers et le cache local."""

    write_default_settings(_CONFIG_PATH)
    settings = _settings()
    init_project(settings)
    typer.echo("Projet initialise.")
    typer.echo(f"Deposez le fichier ODS dans: {settings.input.default_ods_path}")
    typer.echo(f"Base SQLite: {settings.database.sqlite_path}")


@app.command("validate-config")
def validate_config_command() -> None:
    """Valide la configuration `travel_time_core` courante."""

    try:
        validate_settings(_settings())
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Configuration valide: {_CONFIG_PATH}")


@app.command("import-communes")
def import_communes_command() -> None:
    """Importe les communes depuis le fichier configure."""

    settings = _settings()
    validate_settings(settings)
    with db.connect(settings.database.sqlite_path) as conn:
        db.init_db(conn)
        count = import_configured_communes(conn, settings)
    typer.echo(f"{count} communes importees ou mises a jour.")


@app.command("validate-input")
def validate_input_command(
    input_path: Annotated[
        Path,
        typer.Option("--input", exists=True, file_okay=True, dir_okay=False),
    ],
) -> None:
    """Valide un fichier ODS de communes.

    Parameters
    ----------
    input_path : Path
        Chemin du fichier ODS a controler.
    """

    settings = _settings()
    try:
        count = validate_input(input_path, sheet_name=settings.input.sheet_name)
    except InputValidationError as exc:
        typer.echo("Fichier invalide:", err=True)
        for error in exc.errors:
            typer.echo(f"- {error}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Fichier valide: {count} communes.")


@app.command("import-cities")
def import_cities_command(
    input_path: Annotated[
        Path,
        typer.Option("--input", exists=True, file_okay=True, dir_okay=False),
    ],
) -> None:
    """Importe des communes depuis un fichier ODS.

    Parameters
    ----------
    input_path : Path
        Chemin du fichier ODS a importer.
    """

    settings = _settings()
    with db.connect(settings.database.sqlite_path) as conn:
        db.init_db(conn)
        count = import_cities(conn, input_path, sheet_name=settings.input.sheet_name)
    typer.echo(f"{count} communes importees ou mises a jour.")


@app.command("geocode")
def geocode_command(
    refresh: Annotated[bool, typer.Option("--refresh")] = False,
    only_missing: Annotated[bool, typer.Option("--only-missing")] = False,
) -> None:
    """Geocode les communes presentes dans le cache.

    Parameters
    ----------
    refresh : bool, default=False
        Recalcule toutes les communes.
    only_missing : bool, default=False
        Ne traite que les communes sans coordonnees.
    """

    settings = _settings()
    with db.connect(settings.database.sqlite_path) as conn:
        db.init_db(conn)
        ok, failed = geocode_cities(
            conn,
            GeoApiGouvClient(settings.geocode),
            refresh=refresh,
            only_missing=only_missing,
        )
    typer.echo(f"Geocodage termine: {ok} ok, {failed} non geocodees ou erreurs.")


@app.command("build-candidates")
def build_candidates_command(
    k_default: Annotated[int | None, typer.Option("--k-default")] = None,
    k_pc: Annotated[int | None, typer.Option("--k-pc")] = None,
    k_tpc: Annotated[int | None, typer.Option("--k-tpc")] = None,
) -> None:
    """Construit les couples commune-pivot candidats.

    Parameters
    ----------
    k_default : int | None, default=None
        Nombre de candidats pour une commune standard.
    k_pc : int | None, default=None
        Nombre de candidats pour une commune PC.
    k_tpc : int | None, default=None
        Nombre de candidats pour une commune TPC.
    """

    settings = _settings()
    with db.connect(settings.database.sqlite_path) as conn:
        db.init_db(conn)
        count = build_and_store_candidates(
            conn,
            k_default=k_default or settings.candidates.k_default,
            k_pc=k_pc or settings.candidates.k_pc,
            k_tpc=k_tpc or settings.candidates.k_tpc,
        )
    typer.echo(f"{count} candidates stockees.")


@app.command("compute-batch")
def compute_batch_command(
    only_missing: Annotated[bool, typer.Option("--only-missing")] = False,
    refresh: Annotated[bool, typer.Option("--refresh")] = False,
    limit: Annotated[int | None, typer.Option("--limit")] = None,
    rate_limit: Annotated[float | None, typer.Option("--rate-limit")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    """Calcule un lot de trajets via le client IGN.

    Parameters
    ----------
    only_missing : bool, default=False
        Ignore les trajets deja presents.
    refresh : bool, default=False
        Force le recalcul.
    limit : int | None, default=None
        Limite le nombre de couples traites.
    rate_limit : float | None, default=None
        Remplace temporairement la cadence IGN.
    dry_run : bool, default=False
        Compte les trajets sans les calculer.
    """

    settings = _settings()
    if rate_limit is not None:
        settings.ign.rate_limit_per_sec = rate_limit
    with db.connect(settings.database.sqlite_path) as conn:
        db.init_db(conn)
        count = compute_batch(
            conn,
            IgnRouteClient(
                settings.ign,
                raw_response_dir=settings.database.sqlite_path.parent / "raw_ign",
            ),
            only_missing=only_missing or not refresh,
            refresh=refresh,
            limit=limit,
            dry_run=dry_run,
        )
    verb = "seraient calcules" if dry_run else "calcules"
    typer.echo(f"{count} trajets {verb}.")


@app.command("compute")
def compute_command(
    refresh: Annotated[bool, typer.Option("--refresh")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    """Calcule les trajets selon la configuration runtime.

    Parameters
    ----------
    refresh : bool, default=False
        Force le recalcul.
    dry_run : bool, default=False
        Compte les trajets sans les calculer.
    """

    settings = _settings()
    validate_settings(settings)
    with db.connect(settings.database.sqlite_path) as conn:
        db.init_db(conn)
        count = compute_configured_routes(
            conn,
            settings,
            only_missing=not refresh,
            refresh=refresh,
            dry_run=dry_run,
        )
    verb = "seraient calcules" if dry_run else "calcules"
    typer.echo(f"{count} trajets {verb}.")


@app.command("route")
def route_command(
    from_insee: Annotated[str | None, typer.Option("--from-insee")] = None,
    to_insee: Annotated[str | None, typer.Option("--to-insee")] = None,
    from_name: Annotated[str | None, typer.Option("--from-name")] = None,
    to_name: Annotated[str | None, typer.Option("--to-name")] = None,
    refresh: Annotated[bool, typer.Option("--refresh")] = False,
) -> None:
    """Calcule un trajet specifique entre deux communes.

    Parameters
    ----------
    from_insee : str | None, default=None
        Code commune origine.
    to_insee : str | None, default=None
        Code commune destination.
    from_name : str | None, default=None
        Nom de commune origine.
    to_name : str | None, default=None
        Nom de commune destination.
    refresh : bool, default=False
        Force le recalcul du trajet.
    """

    if not ((from_insee or from_name) and (to_insee or to_name)):
        typer.echo("Indiquez une origine et une destination par INSEE ou par nom.", err=True)
        raise typer.Exit(1)
    settings = _settings()
    with db.connect(settings.database.sqlite_path) as conn:
        db.init_db(conn)
        try:
            result = compute_specific_route(
                conn,
                IgnRouteClient(
                    settings.ign,
                    raw_response_dir=settings.database.sqlite_path.parent / "raw_ign",
                ),
                from_insee=from_insee,
                to_insee=to_insee,
                from_name=from_name,
                to_name=to_name,
                refresh=refresh,
            )
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1) from exc
    duration = f"{result.duration_sec / 60:.1f} min" if result.duration_sec is not None else "n/a"
    distance = f"{result.distance_m / 1000:.1f} km" if result.distance_m is not None else "n/a"
    typer.echo(
        f"{result.origin_insee} -> {result.destination_insee}: "
        f"statut={result.route_status}, duree={duration}, distance={distance}"
    )
    if result.api_error:
        typer.echo(f"Erreur API: {result.api_error}")


@app.command("export")
def export_command() -> None:
    """Ecrit les exports complets depuis le cache SQLite."""

    settings = _settings()
    with db.connect(settings.database.sqlite_path) as conn:
        db.init_db(conn)
        paths = export_outputs(conn, settings.output.directory)
    typer.echo("Exports generes:")
    for path in paths.values():
        typer.echo(f"- {path}")


@app.command("export-thresholds")
def export_thresholds_command(
    thresholds: Annotated[
        str,
        typer.Option(
            "--thresholds",
            help="Seuils de duree en minutes, separes par des virgules.",
        ),
    ] = "60,90,120",
) -> None:
    """Ecrit les exports filtres par seuils de duree.

    Parameters
    ----------
    thresholds : str, default="60,90,120"
        Seuils en minutes separes par des virgules.
    """

    parsed_thresholds = _parse_thresholds(thresholds)
    settings = _settings()
    with db.connect(settings.database.sqlite_path) as conn:
        db.init_db(conn)
        paths = export_threshold_outputs(conn, settings.output.directory, parsed_thresholds)
    typer.echo("Exports filtres generes:")
    for path in paths.values():
        typer.echo(f"- {path}")


@app.command("export-matrices")
def export_matrices_command() -> None:
    """Ecrit les exports configures, dont le CSV compatible optimiseur."""

    settings = _settings()
    validate_settings(settings)
    with db.connect(settings.database.sqlite_path) as conn:
        db.init_db(conn)
        paths = export_configured_outputs(conn, settings)
    typer.echo("Exports generes:")
    for path in paths.values():
        typer.echo(f"- {path}")


@app.command("run-all")
def run_all_command(
    input_path: Annotated[
        Path,
        typer.Option("--input", exists=True, file_okay=True, dir_okay=False),
    ],
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    """Execute l'ancien pipeline complet depuis un ODS.

    Parameters
    ----------
    input_path : Path
        Fichier ODS d'entree.
    dry_run : bool, default=False
        Execute sans ecrire les exports finaux.
    """

    run_all(_settings(), input_path, dry_run=dry_run)
    typer.echo("Pipeline termine.")


@app.command("run-pipeline")
def run_pipeline_command(
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    """Execute le pipeline configure de bout en bout.

    Parameters
    ----------
    dry_run : bool, default=False
        Execute sans ecrire les exports finaux.
    """

    paths = run_configured_pipeline(_settings(), dry_run=dry_run)
    typer.echo("Pipeline termine.")
    for path in paths.values():
        typer.echo(f"- {path}")


if __name__ == "__main__":
    app()
