from __future__ import annotations

from pathlib import Path

from travel_times.config import load_settings
from travel_times.data_loading import read_communes_csv


def test_read_communes_csv_fixture() -> None:
    settings = load_settings(Path(__file__).parent / "fixtures" / "config_minimal.yaml")

    cities = read_communes_csv(settings.input.communes_csv_path, settings.columns)

    assert [city.insee_code for city in cities] == ["69123", "74010", "38185"]
    assert cities[0].lat == 45.7578
    assert cities[1].commune_type == "TPC"
