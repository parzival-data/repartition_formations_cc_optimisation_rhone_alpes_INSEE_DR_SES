from __future__ import annotations

from travel_times.candidates import build_candidate_routes, candidate_count_for_type
from travel_times.models import CityRecord


def test_candidate_count_for_type() -> None:
    assert candidate_count_for_type("STANDARD", k_default=150, k_pc=120, k_tpc=100) == 150
    assert candidate_count_for_type("PC", k_default=150, k_pc=120, k_tpc=100) == 120
    assert candidate_count_for_type("TPC", k_default=150, k_pc=120, k_tpc=100) == 100


def test_build_candidate_routes_selects_nearest_and_excludes_self() -> None:
    cities = [
        CityRecord("A", "A", "STANDARD", lat=0, lon=0),
        CityRecord("B", "B", "STANDARD", lat=0, lon=1),
        CityRecord("C", "C", "STANDARD", lat=0, lon=2),
    ]

    routes = build_candidate_routes(cities, k_default=1, k_pc=1, k_tpc=1)

    assert len(routes) == 3
    assert all(route.origin_insee != route.destination_insee for route in routes)
    assert next(route for route in routes if route.origin_insee == "A").destination_insee == "B"
