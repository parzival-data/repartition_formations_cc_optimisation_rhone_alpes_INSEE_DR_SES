"""Configuration du sous-projet de calcul des temps de trajet."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class InputSettings(BaseModel):
    """Parametres des fichiers d'entree.

    Attributes
    ----------
    default_ods_path : Path
        Chemin ODS par defaut.
    communes_csv_path : Path
        Chemin CSV des communes deja nettoyees.
    format : str
        Format d'entree configure, ``csv`` ou ``ods``.
    sheet_name : str | int | None
        Feuille ODS a lire.
    """

    default_ods_path: Path = Path("data/input/villes.ods")
    communes_csv_path: Path = Path("data/input/communes.csv")
    format: str = "csv"
    sheet_name: str | int | None = None


class ColumnSettings(BaseModel):
    """Mapping des colonnes du CSV de communes.

    Attributes
    ----------
    code_commune : str
        Colonne du code commune.
    nom_commune : str
        Colonne du nom de commune.
    categorie : str
        Colonne de categorie PC/TPC.
    latitude : str
        Colonne latitude.
    longitude : str
        Colonne longitude.
    population : str | None
        Colonne population optionnelle.
    territoire : str | None
        Colonne territoire optionnelle.
    """

    code_commune: str = "code_commune"
    nom_commune: str = "nom_commune"
    categorie: str = "categorie"
    latitude: str = "latitude"
    longitude: str = "longitude"
    population: str | None = "population"
    territoire: str | None = "territoire_EAR"


class DatabaseSettings(BaseModel):
    """Parametres du cache SQLite.

    Attributes
    ----------
    sqlite_path : Path
        Chemin de la base SQLite locale.
    """

    sqlite_path: Path = Path("data/cache/travel_times.sqlite")


class GeocodeSettings(BaseModel):
    """Parametres d'appel a geo.api.gouv.fr.

    Attributes
    ----------
    base_url : str
        URL de base de l'API.
    timeout_sec : float
        Timeout HTTP en secondes.
    rate_limit_per_sec : float
        Nombre maximal d'appels par seconde.
    """

    base_url: str = "https://geo.api.gouv.fr"
    timeout_sec: float = 20
    rate_limit_per_sec: float = 5.0


class IgnSettings(BaseModel):
    """Parametres d'appel au service de routage IGN.

    Attributes
    ----------
    get_capabilities_url : str
        URL de decouverte du service.
    route_url : str
        URL de calcul d'itineraire.
    resource : str
        Ressource de routage utilisee.
    profile : str
        Profil de transport.
    optimization : str
        Critere d'optimisation du trajet.
    distance_unit : str
        Unite de distance attendue.
    time_unit : str
        Unite de temps attendue.
    crs : str
        Systeme de coordonnees.
    get_steps : bool
        Indique si les etapes doivent etre demandees.
    get_bbox : bool
        Indique si la bbox doit etre demandee.
    timeout_sec : float
        Timeout HTTP en secondes.
    rate_limit_per_sec : float
        Nombre maximal d'appels par seconde.
    max_retries : int
        Nombre maximal de tentatives.
    backoff_initial_sec : float
        Delai initial de reprise.
    debug_raw_responses : bool
        Indique si les reponses brutes doivent etre ecrites.
    api_key : str | None
        Jeton API optionnel.
    """

    get_capabilities_url: str = "https://data.geopf.fr/navigation/getCapabilities"
    route_url: str = "https://data.geopf.fr/navigation/itineraire"
    resource: str = "bdtopo-osrm"
    profile: str = "car"
    optimization: str = "fastest"
    distance_unit: str = "meter"
    time_unit: str = "second"
    crs: str = "EPSG:4326"
    get_steps: bool = False
    get_bbox: bool = False
    timeout_sec: float = 30
    rate_limit_per_sec: float = 4.5
    max_retries: int = 3
    backoff_initial_sec: float = 1.0
    debug_raw_responses: bool = False
    api_key: str | None = None


class CandidateSettings(BaseModel):
    """Parametres de generation des couples candidats.

    Attributes
    ----------
    k_default : int
        Nombre de pivots candidats pour une commune standard.
    k_pc : int
        Nombre de pivots candidats pour une commune PC.
    k_tpc : int
        Nombre de pivots candidats pour une commune TPC.
    """

    k_default: int = Field(default=150, ge=1)
    k_pc: int = Field(default=120, ge=1)
    k_tpc: int = Field(default=100, ge=1)


class RuntimeSettings(BaseModel):
    """Parametres d'execution du calcul des trajets.

    Attributes
    ----------
    mode : str
        Mode de calcul, ``offline`` ou ``ign``.
    allow_network : bool
        Autorisation explicite des appels reseau.
    max_couples : int | None
        Limite optionnelle du nombre de couples a traiter.
    offline_speed_kmh : float
        Vitesse moyenne utilisee en mode offline.
    offline_distance_factor : float
        Facteur applique a la distance a vol d'oiseau en mode offline.
    """

    mode: str = "offline"
    allow_network: bool = False
    max_couples: int | None = Field(default=None, ge=1)
    offline_speed_kmh: float = Field(default=55.0, gt=0)
    offline_distance_factor: float = Field(default=1.25, gt=0)


class OutputSettings(BaseModel):
    """Parametres des exports de temps de trajet.

    Attributes
    ----------
    directory : Path
        Dossier des exports complets.
    compatible_csv_path : Path
        Chemin du CSV compatible avec l'optimiseur.
    report_json_path : Path
        Chemin du rapport JSON de generation.
    thresholds_minutes : list[int]
        Seuils de duree pour les exports filtres.
    """

    directory: Path = Path("data/output")
    compatible_csv_path: Path = Path("data/output/temps_trajet_clean.csv")
    report_json_path: Path = Path("data/output/generation_report.json")
    thresholds_minutes: list[int] = Field(default_factory=lambda: [60, 75, 90, 120])


class Settings(BaseModel):
    """Configuration complete de `travel_time_core`.

    Attributes
    ----------
    input : InputSettings
        Parametres d'entree.
    columns : ColumnSettings
        Mapping des colonnes.
    database : DatabaseSettings
        Parametres du cache SQLite.
    geocode : GeocodeSettings
        Parametres de geocodage.
    ign : IgnSettings
        Parametres de routage IGN.
    candidates : CandidateSettings
        Parametres de generation de candidats.
    runtime : RuntimeSettings
        Parametres d'execution.
    output : OutputSettings
        Parametres d'export.
    """

    input: InputSettings = Field(default_factory=InputSettings)
    columns: ColumnSettings = Field(default_factory=ColumnSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    geocode: GeocodeSettings = Field(default_factory=GeocodeSettings)
    ign: IgnSettings = Field(default_factory=IgnSettings)
    candidates: CandidateSettings = Field(default_factory=CandidateSettings)
    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)
    output: OutputSettings = Field(default_factory=OutputSettings)


DEFAULT_SETTINGS = """input:
  format: "csv"
  communes_csv_path: "data/input/communes.csv"
  default_ods_path: "data/input/villes.ods"
  sheet_name: null

columns:
  code_commune: "code_commune"
  nom_commune: "nom_commune"
  categorie: "categorie"
  latitude: "latitude"
  longitude: "longitude"
  population: "population"
  territoire: "territoire_EAR"

database:
  sqlite_path: "data/cache/travel_times.sqlite"

geocode:
  base_url: "https://geo.api.gouv.fr"
  timeout_sec: 20
  rate_limit_per_sec: 5.0

ign:
  get_capabilities_url: "https://data.geopf.fr/navigation/getCapabilities"
  route_url: "https://data.geopf.fr/navigation/itineraire"
  resource: "bdtopo-osrm"
  profile: "car"
  optimization: "fastest"
  distance_unit: "meter"
  time_unit: "second"
  crs: "EPSG:4326"
  get_steps: false
  get_bbox: false
  timeout_sec: 30
  rate_limit_per_sec: 4.5
  max_retries: 3
  backoff_initial_sec: 1.0
  debug_raw_responses: false
  api_key: null

candidates:
  k_default: 150
  k_pc: 120
  k_tpc: 100

runtime:
  mode: "offline"
  allow_network: false
  max_couples: null
  offline_speed_kmh: 55.0
  offline_distance_factor: 1.25

output:
  directory: "data/output"
  compatible_csv_path: "data/output/temps_trajet_clean.csv"
  report_json_path: "data/output/generation_report.json"
  thresholds_minutes: [60, 75, 90, 120]
"""


def load_settings(path: Path | str = Path("config/settings.yml")) -> Settings:
    """Charge la configuration de calcul des temps de trajet.

    Parameters
    ----------
    path : Path | str, default=Path("config/settings.yml")
        Chemin du YAML a charger si la variable d'environnement
        ``TRAVEL_TIMES_CONFIG`` n'est pas definie.

    Returns
    -------
    Settings
        Configuration validee et chemins relatifs resolus.
    """

    config_path = Path(os.getenv("TRAVEL_TIMES_CONFIG", str(path)))
    if not config_path.exists():
        return Settings()
    with config_path.open("r", encoding="utf-8") as file:
        raw: dict[str, Any] = yaml.safe_load(file) or {}
    settings = Settings.model_validate(raw)
    _resolve_paths(settings, _config_base_dir(config_path))
    env_api_key = os.getenv("TRAVEL_TIMES_IGN_API_KEY")
    if env_api_key:
        settings.ign.api_key = env_api_key
    return settings


def write_default_settings(path: Path) -> None:
    """Ecrit le YAML de configuration par defaut s'il n'existe pas.

    Parameters
    ----------
    path : Path
        Chemin du fichier YAML a initialiser.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(DEFAULT_SETTINGS, encoding="utf-8")


def _config_base_dir(config_path: Path) -> Path:
    parent = config_path.resolve().parent
    if parent.name == "config":
        return parent.parent
    return parent


def _resolve_path(path: Path, base_dir: Path) -> Path:
    return path if path.is_absolute() else base_dir / path


def _resolve_paths(settings: Settings, base_dir: Path) -> None:
    settings.input.default_ods_path = _resolve_path(settings.input.default_ods_path, base_dir)
    settings.input.communes_csv_path = _resolve_path(settings.input.communes_csv_path, base_dir)
    settings.database.sqlite_path = _resolve_path(settings.database.sqlite_path, base_dir)
    settings.output.directory = _resolve_path(settings.output.directory, base_dir)
    settings.output.compatible_csv_path = _resolve_path(
        settings.output.compatible_csv_path,
        base_dir,
    )
    settings.output.report_json_path = _resolve_path(settings.output.report_json_path, base_dir)
