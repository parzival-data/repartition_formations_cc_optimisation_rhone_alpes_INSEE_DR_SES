from __future__ import annotations

from travel_times.geocode import parse_geo_api_response


def test_parse_geo_api_response_prefers_mairie() -> None:
    result = parse_geo_api_response(
        "69123",
        [
            {
                "code": "69123",
                "mairie": {"type": "Point", "coordinates": [4.8357, 45.764]},
                "centre": {"type": "Point", "coordinates": [4.84, 45.76]},
                "population": 500000,
                "codeDepartement": "69",
                "codeRegion": "84",
            }
        ],
    )

    assert result.status == "ok"
    assert result.coord_source == "mairie"
    assert result.lon == 4.8357
    assert result.lat == 45.764


def test_parse_geo_api_response_falls_back_to_centre() -> None:
    result = parse_geo_api_response(
        "74010",
        [{"code": "74010", "centre": {"type": "Point", "coordinates": [6.1294, 45.8992]}}],
    )

    assert result.status == "ok"
    assert result.coord_source == "centre"


def test_parse_geo_api_response_not_found() -> None:
    result = parse_geo_api_response("99999", [])
    assert result.status == "not_found"
