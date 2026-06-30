from __future__ import annotations

import sqlite3

from travel_times import db
from travel_times.models import CandidateRoute, CityInput, RouteResult


def test_upsert_sqlite_city_candidate_and_travel_time() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)

    db.upsert_cities(conn, [CityInput("69123", "Lyon", "STANDARD")])
    db.upsert_candidate_routes(conn, [CandidateRoute("69123", "74010", 100.0, 1, "k=1")])
    db.upsert_travel_time(
        conn,
        RouteResult(
            origin_insee="69123",
            destination_insee="74010",
            route_status="ok",
            duration_sec=3600,
            distance_m=100000,
        ),
    )

    city = conn.execute("SELECT * FROM cities WHERE insee_code = '69123'").fetchone()
    travel_time = db.get_travel_time(conn, "69123", "74010")
    assert city["name"] == "Lyon"
    assert travel_time is not None
    assert travel_time["duration_sec"] == 3600
