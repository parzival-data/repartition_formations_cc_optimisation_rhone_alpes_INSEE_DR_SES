from __future__ import annotations

from pathlib import Path

import pytest

from cc_formation_optimizer.config import load_config
from cc_formation_optimizer.data_loading import (
    DataLoadingError,
    load_communes,
    load_compatibilities,
    load_travel_times,
)


FIXTURES = Path(__file__).parent / "fixtures"


def test_load_communes_uses_configured_columns_and_normalizes_ids() -> None:
    config = load_config(FIXTURES / "config_minimal.yaml")

    communes = load_communes(config)

    assert [commune.commune_id for commune in communes] == ["001", "002"]
    assert communes[0].population == 6000
    assert communes[1].category == "TPC"


def test_load_travel_times_uses_configured_columns() -> None:
    config = load_config(FIXTURES / "config_minimal.yaml")

    travel_times = load_travel_times(config)

    assert travel_times[0].origin_id == "001"
    assert travel_times[0].destination_id == "001"
    assert travel_times[0].minutes == 0


def test_load_compatibilities_returns_empty_when_no_file_is_configured() -> None:
    config = load_config(FIXTURES / "config_minimal.yaml")

    assert load_compatibilities(config) == []


def test_load_compatibilities_reads_optional_file(tmp_path: Path) -> None:
    raw = (FIXTURES / "config_minimal.yaml").read_text(encoding="utf-8")
    raw = raw.replace("compatibility_path: null", "compatibility_path: tests/fixtures/compatibilites_minimal.csv")
    config_path = tmp_path / "config_with_compat.yaml"
    config_path.write_text(raw, encoding="utf-8")
    config = load_config(config_path)

    compatibilities = load_compatibilities(config)

    assert [(item.origin_id, item.destination_id, item.allowed) for item in compatibilities] == [
        ("001", "002", 0),
        ("002", "001", 1),
    ]


def test_missing_required_column_raises_clear_error(tmp_path: Path) -> None:
    bad_csv = tmp_path / "communes_bad.csv"
    bad_csv.write_text("code_commune,nom_commune,categorie\n001,Commune,PC\n", encoding="utf-8")

    raw = (FIXTURES / "config_minimal.yaml").read_text(encoding="utf-8")
    raw = raw.replace("tests/fixtures/communes_minimal.csv", str(bad_csv).replace("\\", "/"))
    config_path = tmp_path / "config_bad_column.yaml"
    config_path.write_text(raw, encoding="utf-8")
    config = load_config(config_path)

    with pytest.raises(DataLoadingError, match="Colonnes obligatoires manquantes"):
        load_communes(config)
