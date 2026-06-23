from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from cc_formation_optimizer.data_preparation import DataPreparationError, prepare_data


def _write_config(tmp_path: Path, communes_file: str = "communes_raw.csv", travel_file: str = "trajets_raw.csv") -> Path:
    config_path = tmp_path / "config_prepare.yaml"
    output_root = str(tmp_path / "outputs").replace("\\", "/")
    config_path.write_text(
        f"""
metadata:
  name: test_prepare
exports:
  output_dir: {output_root}
data_preparation:
  communes:
    file: {communes_file}
    columns:
      code_commune: code
      nom_commune: nom
      categorie: type
      territoire_EAR: territoire
      population: pop
      logements: logements
      latitude: latitude
      longitude: longitude
    category_mapping:
      principale: PC
      tpc: TPC
  travel_times:
    file: {travel_file}
    origin_column: origine
    destination_column: pivot
    minutes_column: duree
""",
        encoding="utf-8",
    )
    return config_path


def _write_communes(raw_dir: Path, rows: list[dict[str, str]]) -> None:
    with (raw_dir / "communes_raw.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["code", "nom", "type", "territoire", "pop", "logements", "latitude", "longitude", "ignoree"],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_travels(raw_dir: Path, rows: list[dict[str, str]]) -> None:
    with (raw_dir / "trajets_raw.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["origine", "pivot", "duree"])
        writer.writeheader()
        writer.writerows(rows)


def _valid_communes() -> list[dict[str, str]]:
    return [
        {
            "code": "1",
            "nom": "Commune PC",
            "type": "principale",
            "territoire": "Nord",
            "pop": "6000",
            "logements": "2500",
            "latitude": "45,1",
            "longitude": "4.2",
            "ignoree": "x",
        },
        {
            "code": "2",
            "nom": "Commune TPC",
            "type": "tpc",
            "territoire": "Sud",
            "pop": "400",
            "logements": "180",
            "latitude": "",
            "longitude": "",
            "ignoree": "y",
        },
    ]


def _prepare_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    raw_dir = tmp_path / "raw"
    output_dir = tmp_path / "processed"
    raw_dir.mkdir()
    _write_communes(raw_dir, _valid_communes())
    _write_travels(
        raw_dir,
        [
            {"origine": "1", "pivot": "1", "duree": "0"},
            {"origine": "1", "pivot": "2", "duree": "10.2"},
            {"origine": "2", "pivot": "1", "duree": "9"},
        ],
    )
    return _write_config(tmp_path), raw_dir, output_dir


def test_communes_raw_file_is_transformed_to_clean_csv(tmp_path: Path) -> None:
    config_path, raw_dir, output_dir = _prepare_fixture(tmp_path)

    result = prepare_data(config_path, input_dir=raw_dir, output_dir=output_dir)

    output = output_dir / "communes_clean.csv"
    assert output.exists()
    rows = list(csv.DictReader(output.open(encoding="utf-8")))
    assert rows[0]["code_commune"] == "00001"
    assert rows[0]["categorie"] == "PC"
    assert rows[1]["categorie"] == "TPC"
    assert rows[1]["latitude"] == ""
    assert result.stats["communes_without_coordinates"] == 1


def test_unknown_category_and_duplicate_communes_are_reported(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    output_dir = tmp_path / "processed"
    raw_dir.mkdir()
    rows = _valid_communes()
    rows.append({**rows[0], "nom": "Doublon"})
    rows.append({**rows[1], "code": "3", "type": "inconnue"})
    _write_communes(raw_dir, rows)
    _write_travels(raw_dir, [{"origine": "1", "pivot": "2", "duree": "5"}])
    config_path = _write_config(tmp_path)

    result = prepare_data(config_path, input_dir=raw_dir, output_dir=output_dir)

    messages = [issue.message for issue in result.blocking_issues]
    assert any("Commune dupliquee" in message for message in messages)
    assert any("Categorie inconnue" in message for message in messages)


def test_travel_unknown_commune_negative_time_and_duplicate_are_reported(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    output_dir = tmp_path / "processed"
    raw_dir.mkdir()
    _write_communes(raw_dir, _valid_communes())
    _write_travels(
        raw_dir,
        [
            {"origine": "1", "pivot": "2", "duree": "5"},
            {"origine": "1", "pivot": "2", "duree": "7"},
            {"origine": "1", "pivot": "999", "duree": "5"},
            {"origine": "2", "pivot": "1", "duree": "-1"},
        ],
    )
    config_path = _write_config(tmp_path)

    result = prepare_data(config_path, input_dir=raw_dir, output_dir=output_dir)

    messages = [issue.message for issue in result.blocking_issues]
    assert any("Trajet duplique" in message for message in messages)
    assert any("commune inconnue" in message for message in messages)
    assert any("Valeur negative interdite" in message for message in messages)


def test_dry_run_does_not_create_outputs(tmp_path: Path) -> None:
    config_path, raw_dir, output_dir = _prepare_fixture(tmp_path)

    prepare_data(config_path, input_dir=raw_dir, output_dir=output_dir, report=True, dry_run=True)

    assert not output_dir.exists()
    assert not (tmp_path / "outputs" / "reports").exists()


def test_strict_fails_with_blocking_issues(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    output_dir = tmp_path / "processed"
    raw_dir.mkdir()
    rows = _valid_communes()
    rows[0]["type"] = "inconnue"
    _write_communes(raw_dir, rows)
    _write_travels(raw_dir, [{"origine": "1", "pivot": "2", "duree": "5"}])
    config_path = _write_config(tmp_path)

    with pytest.raises(DataPreparationError, match="mode strict"):
        prepare_data(config_path, input_dir=raw_dir, output_dir=output_dir, strict=True)


def test_reports_are_generated(tmp_path: Path) -> None:
    config_path, raw_dir, output_dir = _prepare_fixture(tmp_path)

    prepare_data(config_path, input_dir=raw_dir, output_dir=output_dir, report=True)

    report_path = tmp_path / "outputs" / "reports" / "rapport_preparation_donnees.md"
    stats_path = tmp_path / "outputs" / "reports" / "statistiques_preparation_donnees.json"
    assert report_path.exists()
    assert stats_path.exists()
    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    assert stats["communes_count"] == 2
    assert "trajets absents" in report_path.read_text(encoding="utf-8").lower()
