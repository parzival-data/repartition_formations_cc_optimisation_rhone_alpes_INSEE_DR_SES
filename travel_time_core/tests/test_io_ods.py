from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from travel_times.io_ods import (
    detect_columns,
    normalize_commune_type,
    normalize_insee,
    read_cities_ods,
)


def test_detect_columns_with_synonyms() -> None:
    df = pd.DataFrame(columns=["Commune", "Code commune", "Categorie"])
    mapping = detect_columns(df)
    assert mapping.name == "Commune"
    assert mapping.insee_code == "Code commune"
    assert mapping.commune_type == "Categorie"


def test_detect_columns_with_real_accented_header() -> None:
    df = pd.DataFrame(
        columns=[
            "Code commune",
            "Commune",
            "Catégorie",
            "Territoire EAR 2027",
            "Population 2023",
        ]
    )
    mapping = detect_columns(df)
    assert mapping.name == "Commune"
    assert mapping.insee_code == "Code commune"
    assert mapping.commune_type == "Catégorie"


def test_normalize_insee_preserves_text() -> None:
    assert normalize_insee("01004") == "01004"
    assert normalize_insee(" 69123 ") == "69123"
    assert normalize_insee("69123.0") == "69123"


def test_normalize_commune_type() -> None:
    assert normalize_commune_type(" pc ") == "PC"
    assert normalize_commune_type("TPC") == "TPC"
    assert normalize_commune_type("") == "STANDARD"
    assert normalize_commune_type("autre") == "STANDARD"


def test_read_cities_ods(tmp_path: Path) -> None:
    path = tmp_path / "villes.ods"
    df = pd.DataFrame(
        [
            {"nom_ville": "Lyon", "code_insee": "69123", "precision": ""},
            {"nom_ville": "Annecy", "code_insee": "74010", "precision": "PC"},
        ]
    )
    with pd.ExcelWriter(path, engine="odf") as writer:
        df.to_excel(writer, index=False)

    cities = read_cities_ods(path)

    assert len(cities) == 2
    assert cities[0].insee_code == "69123"
    assert cities[1].commune_type == "PC"


def test_read_cities_ods_with_explicit_sheet_name(tmp_path: Path) -> None:
    path = tmp_path / "villes.ods"
    df = pd.DataFrame(
        [
            {"Code commune": "01001", "Commune": "Abergement", "Catégorie": "PC"},
            {"Code commune": "01002", "Commune": "Varey", "Catégorie": "TPC"},
        ]
    )
    with pd.ExcelWriter(path, engine="odf") as writer:
        pd.DataFrame([{"ignore": "me"}]).to_excel(writer, index=False, sheet_name="Ignore")
        df.to_excel(writer, index=False, sheet_name="Feuille1")

    cities = read_cities_ods(path, sheet_name="Feuille1")

    assert [city.insee_code for city in cities] == ["01001", "01002"]
    assert [city.commune_type for city in cities] == ["PC", "TPC"]


def test_read_cities_ods_rejects_duplicate(tmp_path: Path) -> None:
    path = tmp_path / "villes.ods"
    df = pd.DataFrame(
        [
            {"nom_ville": "Lyon", "code_insee": "69123"},
            {"nom_ville": "Lyon bis", "code_insee": "69123"},
        ]
    )
    with pd.ExcelWriter(path, engine="odf") as writer:
        df.to_excel(writer, index=False)

    with pytest.raises(ValueError, match="doublon"):
        read_cities_ods(path)
