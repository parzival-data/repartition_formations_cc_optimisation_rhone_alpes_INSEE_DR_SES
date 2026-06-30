from __future__ import annotations

import sqlite3

from travel_times import db
from travel_times.export import (
    filter_sparse_by_duration,
    travel_times_matrix_minutes_df,
    travel_times_sparse_df,
)
from travel_times.models import CandidateRoute, CityInput, RouteResult


def test_export_sparse_dataframe() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    db.upsert_cities(
        conn,
        [
            CityInput("69123", "Lyon", "STANDARD"),
            CityInput("74010", "Annecy", "PC"),
        ],
    )
    db.upsert_candidate_routes(conn, [CandidateRoute("69123", "74010", 101.0, 1, "k=150")])
    db.upsert_travel_time(
        conn,
        RouteResult(
            origin_insee="69123",
            destination_insee="74010",
            route_status="ok",
            duration_sec=5400,
            distance_m=145000,
            requested_by_user=True,
        ),
    )

    df = travel_times_sparse_df(conn)

    assert list(df["origin_insee"]) == ["69123"]
    assert list(df["destination_type"]) == ["PC"]
    assert list(df["duration_min"]) == [90.0]


def test_export_matrix_accepts_numeric_minutes() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    db.upsert_cities(
        conn,
        [
            CityInput("69123", "Lyon", "STANDARD"),
            CityInput("74010", "Annecy", "PC"),
        ],
    )
    db.upsert_travel_time(
        conn,
        RouteResult(
            origin_insee="69123",
            destination_insee="74010",
            route_status="ok",
            duration_sec=824,
            distance_m=12000,
        ),
    )

    df = travel_times_matrix_minutes_df(conn)

    origin_row = df[df["origin"] == "Lyon (69123)"].iloc[0]
    assert origin_row["Annecy (74010)"] == 13.73


def test_export_matrix_filters_above_threshold() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    db.upsert_cities(
        conn,
        [
            CityInput("69123", "Lyon", "STANDARD"),
            CityInput("74010", "Annecy", "PC"),
            CityInput("38185", "Grenoble", "PC"),
        ],
    )
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
    db.upsert_travel_time(
        conn,
        RouteResult(
            origin_insee="69123",
            destination_insee="38185",
            route_status="ok",
            duration_sec=7200,
            distance_m=200000,
        ),
    )

    df = travel_times_matrix_minutes_df(conn, max_minutes=90)

    origin_row = df[df["origin"] == "Lyon (69123)"].iloc[0]
    assert origin_row["Annecy (74010)"] == 60.0
    assert origin_row["Grenoble (38185)"] == ""


def test_filter_sparse_by_duration_keeps_only_ok_under_threshold() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    db.upsert_cities(
        conn,
        [
            CityInput("69123", "Lyon", "STANDARD"),
            CityInput("74010", "Annecy", "PC"),
            CityInput("38185", "Grenoble", "PC"),
        ],
    )
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
    db.upsert_travel_time(
        conn,
        RouteResult(
            origin_insee="69123",
            destination_insee="38185",
            route_status="ok",
            duration_sec=7200,
            distance_m=200000,
        ),
    )

    sparse = travel_times_sparse_df(conn)
    filtered = filter_sparse_by_duration(sparse, 90)

    assert list(filtered["destination_insee"]) == ["74010"]
