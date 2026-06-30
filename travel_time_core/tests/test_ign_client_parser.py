from __future__ import annotations

from travel_times.ign_client import parse_ign_route_response


def test_parse_ign_route_response_nested_route() -> None:
    payload = {"route": {"summary": {"duration": 3600, "distance": 100000}}}

    result = parse_ign_route_response(payload)

    assert result["route_status"] == "ok"
    assert result["duration_sec"] == 3600
    assert result["distance_m"] == 100000


def test_parse_ign_route_response_no_route() -> None:
    result = parse_ign_route_response({"message": "No route found"})
    assert result["route_status"] == "no_route"


def test_parse_ign_route_response_invalid() -> None:
    result = parse_ign_route_response([])
    assert result["route_status"] == "parse_error"
