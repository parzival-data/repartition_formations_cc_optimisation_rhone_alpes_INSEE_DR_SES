from __future__ import annotations

from dataclasses import dataclass


COMMUNE_STANDARD = "STANDARD"
COMMUNE_PC = "PC"
COMMUNE_TPC = "TPC"


@dataclass(frozen=True)
class ColumnMapping:
    name: str
    insee_code: str
    commune_type: str | None = None


@dataclass(frozen=True)
class CityInput:
    insee_code: str
    name: str
    commune_type: str = COMMUNE_STANDARD


@dataclass(frozen=True)
class CityRecord:
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
    origin_insee: str
    destination_insee: str
    air_distance_km: float
    air_rank: int
    candidate_policy: str


@dataclass(frozen=True)
class GeocodeResult:
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
