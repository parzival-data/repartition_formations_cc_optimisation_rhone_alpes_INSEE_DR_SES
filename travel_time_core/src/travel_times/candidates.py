"""Generation des couples commune-pivot candidats."""

from __future__ import annotations

from travel_times.distance import haversine_km
from travel_times.models import COMMUNE_PC, COMMUNE_TPC, CandidateRoute, CityRecord


def candidate_count_for_type(commune_type: str, *, k_default: int, k_pc: int, k_tpc: int) -> int:
    """Retourne le nombre de candidats selon le type de commune.

    Parameters
    ----------
    commune_type : str
        Type de la commune origine.
    k_default : int
        Nombre de candidats par defaut.
    k_pc : int
        Nombre de candidats pour une commune PC.
    k_tpc : int
        Nombre de candidats pour une commune TPC.

    Returns
    -------
    int
        Nombre de pivots candidats a conserver.
    """

    if commune_type == COMMUNE_PC:
        return k_pc
    if commune_type == COMMUNE_TPC:
        return k_tpc
    return k_default


def build_candidate_routes(
    cities: list[CityRecord],
    *,
    k_default: int = 150,
    k_pc: int = 120,
    k_tpc: int = 100,
) -> list[CandidateRoute]:
    """Construit les couples commune-pivot les plus proches a vol d'oiseau.

    Parameters
    ----------
    cities : list[CityRecord]
        Communes avec coordonnees disponibles.
    k_default : int, default=150
        Nombre de candidats pour une commune standard.
    k_pc : int, default=120
        Nombre de candidats pour une commune PC.
    k_tpc : int, default=100
        Nombre de candidats pour une commune TPC.

    Returns
    -------
    list[CandidateRoute]
        Couples orientes classes par commune origine et distance.
    """

    geocoded = [city for city in cities if city.lat is not None and city.lon is not None]
    routes: list[CandidateRoute] = []
    max_possible = max(len(geocoded) - 1, 0)
    for origin in geocoded:
        k = min(
            candidate_count_for_type(
                origin.commune_type,
                k_default=k_default,
                k_pc=k_pc,
                k_tpc=k_tpc,
            ),
            max_possible,
        )
        distances: list[tuple[float, CityRecord]] = []
        for destination in geocoded:
            if origin.insee_code == destination.insee_code:
                continue
            distances.append(
                (
                    haversine_km(origin.lat, origin.lon, destination.lat, destination.lon),
                    destination,
                )
            )
        distances.sort(key=lambda item: (item[0], item[1].insee_code))
        policy = f"k={k};type={origin.commune_type}"
        for rank, (distance_km, destination) in enumerate(distances[:k], start=1):
            routes.append(
                CandidateRoute(
                    origin_insee=origin.insee_code,
                    destination_insee=destination.insee_code,
                    air_distance_km=round(distance_km, 6),
                    air_rank=rank,
                    candidate_policy=policy,
                )
            )
    return routes
