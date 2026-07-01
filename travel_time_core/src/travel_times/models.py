"""Types metier partages pour le calcul des temps de trajet."""

from __future__ import annotations

from dataclasses import dataclass


COMMUNE_STANDARD = "STANDARD"
COMMUNE_PC = "PC"
COMMUNE_TPC = "TPC"


@dataclass(frozen=True)
class ColumnMapping:
    """Colonnes detectees dans un fichier source de communes.

    Attributes
    ----------
    name : str
        Colonne contenant le nom de commune.
    insee_code : str
        Colonne contenant le code commune.
    commune_type : str | None
        Colonne optionnelle contenant le type de commune.
    """

    name: str
    insee_code: str
    commune_type: str | None = None


@dataclass(frozen=True)
class CityInput:
    """Commune lue depuis un fichier d'entree minimal.

    Attributes
    ----------
    insee_code : str
        Code commune.
    name : str
        Nom de la commune.
    commune_type : str
        Type de commune, par defaut ``STANDARD``.
    """

    insee_code: str
    name: str
    commune_type: str = COMMUNE_STANDARD


@dataclass(frozen=True)
class CityRecord:
    """Commune enrichie et persistable dans le cache SQLite.

    Attributes
    ----------
    insee_code : str
        Code commune.
    name : str
        Nom de la commune.
    commune_type : str
        Type de commune, notamment ``PC`` ou ``TPC`` pour le futur pivot.
    lat : float | None
        Latitude connue.
    lon : float | None
        Longitude connue.
    coord_source : str | None
        Source des coordonnees.
    population : int | None
        Population de la commune.
    department_code : str | None
        Code departement.
    region_code : str | None
        Code region.
    geocode_status : str
        Statut de geocodage.
    geocode_error : str | None
        Message d'erreur de geocodage.
    """

    insee_code: str
    name: str
    commune_type: str
    lat: float | None = None
    lon: float | None = None
    coord_source: str | None = None
    population: int | None = None
    department_code: str | None = None
    region_code: str | None = None
    geocode_status: str = "pending"
    geocode_error: str | None = None


@dataclass(frozen=True)
class CandidateRoute:
    """Couple commune-pivot candidat avant appel au moteur de trajet.

    Attributes
    ----------
    origin_insee : str
        Code de la commune origine.
    destination_insee : str
        Code de la commune destination candidate.
    air_distance_km : float
        Distance a vol d'oiseau utilisee pour classer les candidats.
    air_rank : int
        Rang du candidat pour la commune origine.
    candidate_policy : str
        Politique de generation du candidat.
    """

    origin_insee: str
    destination_insee: str
    air_distance_km: float
    air_rank: int
    candidate_policy: str


@dataclass(frozen=True)
class GeocodeResult:
    """Resultat de geocodage d'une commune.

    Attributes
    ----------
    insee_code : str
        Code commune.
    status : str
        Statut de geocodage.
    lat : float | None
        Latitude extraite.
    lon : float | None
        Longitude extraite.
    coord_source : str
        Source de coordonnees retenue.
    population : int | None
        Population retournee par l'API.
    department_code : str | None
        Code departement.
    region_code : str | None
        Code region.
    error : str | None
        Message d'erreur eventuel.
    """

    insee_code: str
    status: str
    lat: float | None = None
    lon: float | None = None
    coord_source: str = "unknown"
    population: int | None = None
    department_code: str | None = None
    region_code: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class RouteResult:
    """Resultat de calcul d'un trajet oriente.

    Attributes
    ----------
    origin_insee : str
        Code de la commune origine.
    destination_insee : str
        Code de la commune destination.
    route_status : str
        Statut du calcul de trajet.
    duration_sec : int | None
        Duree du trajet en secondes.
    distance_m : int | None
        Distance du trajet en metres.
    api_status_code : int | None
        Code HTTP retourne par l'API, si applicable.
    api_error : str | None
        Message d'erreur API.
    requested_by_user : bool
        Indique si le trajet a ete demande explicitement.
    resource : str | None
        Ressource de routage utilisee.
    mode : str
        Mode de transport.
    engine : str
        Moteur de calcul du trajet.
    """

    origin_insee: str
    destination_insee: str
    route_status: str
    duration_sec: int | None = None
    distance_m: int | None = None
    api_status_code: int | None = None
    api_error: str | None = None
    requested_by_user: bool = False
    resource: str | None = None
    mode: str = "car"
    engine: str = "ign-geoplateforme"
