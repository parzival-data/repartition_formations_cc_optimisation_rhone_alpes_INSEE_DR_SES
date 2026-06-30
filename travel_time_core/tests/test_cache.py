from __future__ import annotations

import sqlite3

from travel_times import db
from travel_times.models import CandidateRoute, CityInput, RouteResult
from travel_times.pipeline import compute_batch


class CountingClient:
    def __init__(self) -> None:
        self.calls = 0

    def route(self, origin, destination, *, requested_by_user=False):  # noqa: ANN001, ANN201
        self.calls += 1
        return RouteResult(
            origin_insee=origin.insee_code,
            destination_insee=destination.insee_code,
            route_status="ok",
            duration_sec=600,
            distance_m=1000,
        )


def test_compute_batch_uses_existing_cache_when_only_missing() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    db.upsert_cities(
        conn,
        [CityInput("A", "A", "PC"), CityInput("B", "B", "TPC")],
    )
    conn.execute("UPDATE cities SET lat = 1, lon = 1, geocode_status = 'ok' WHERE insee_code = 'A'")
    conn.execute("UPDATE cities SET lat = 2, lon = 2, geocode_status = 'ok' WHERE insee_code = 'B'")
    conn.commit()
    db.upsert_candidate_routes(conn, [CandidateRoute("A", "B", 1.0, 1, "k=1")])

    client = CountingClient()
    assert compute_batch(conn, client, only_missing=True) == 1
    assert compute_batch(conn, client, only_missing=True) == 0
    assert client.calls == 1
