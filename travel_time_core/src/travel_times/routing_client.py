from __future__ import annotations

import math
from typing import Protocol

from travel_times.config import RuntimeSettings
from travel_times.distance import haversine_km
from travel_times.models import CityRecord, RouteResult


class RouteClient(Protocol):
    def route(
        self,
        origin: CityRecord,
        destination: CityRecord,
        *,
        requested_by_user: bool = False,
    ) -> RouteResult:
        ...


class OfflineRouteClient:
    """Deterministic no-network route estimator used for tests and dry offline runs."""

    def __init__(self, settings: RuntimeSettings) -> None:
        self.settings = settings

    def route(
        self,
        origin: CityRecord,
        destination: CityRecord,
        *,
        requested_by_user: bool = False,
    ) -> RouteResult:
        if (
            origin.lat is None
            or origin.lon is None
            or destination.lat is None
            or destination.lon is None
        ):
            return RouteResult(
                origin_insee=origin.insee_code,
                destination_insee=destination.insee_code,
                route_status="skipped",
                api_error="missing origin or destination coordinates",
                requested_by_user=requested_by_user,
                engine="offline-estimator",
            )

        air_km = haversine_km(origin.lat, origin.lon, destination.lat, destination.lon)
        distance_km = air_km * self.settings.offline_distance_factor
        duration_hours = distance_km / self.settings.offline_speed_kmh
        return RouteResult(
            origin_insee=origin.insee_code,
            destination_insee=destination.insee_code,
            route_status="ok",
            duration_sec=max(0, int(math.ceil(duration_hours * 3600))),
            distance_m=max(0, int(math.ceil(distance_km * 1000))),
            requested_by_user=requested_by_user,
            resource="offline-haversine",
            engine="offline-estimator",
        )
