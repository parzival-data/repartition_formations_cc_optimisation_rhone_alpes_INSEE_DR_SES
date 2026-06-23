from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from cc_formation_optimizer.config import load_config
from cc_formation_optimizer.data_loading import load_communes, load_compatibilities, load_travel_times
from cc_formation_optimizer.data_preparation import DataPreparationError, prepare_data
from cc_formation_optimizer.map_export import export_solution_map
from cc_formation_optimizer.model_builder import build_model
from cc_formation_optimizer.parameters import build_derived_parameters
from cc_formation_optimizer.solution_extractor import extract_solution
from cc_formation_optimizer.solver import solve_model
from cc_formation_optimizer.validation import validate_solution


def _write_config(
    tmp_path: Path,
    communes_file: str = "communes_raw.csv",
    travel_file: str = "trajets_raw.csv",
    coordinates_file: str | None = None,
) -> Path:
    config_path = tmp_path / "config_prepare.yaml"
    output_root = str(tmp_path / "outputs").replace("\\", "/")
    coordinates_section = ""
    if coordinates_file is not None:
        coordinates_section = f"""
  coordinates:
    file: {coordinates_file}
    columns:
      code_commune: insee
      nom_commune: nom
      latitude: lat
      longitude: lon
"""
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
{coordinates_section}
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


def _write_coordinates(raw_dir: Path, rows: list[dict[str, str]]) -> None:
    with (raw_dir / "coords_raw.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["insee", "nom", "lat", "lon"])
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


def test_coordinates_file_is_joined_to_clean_communes_with_normalized_codes(tmp_path: Path) -> None:
    config_path, raw_dir, output_dir = _prepare_fixture(tmp_path)
    _write_coordinates(
        raw_dir,
        [
            {"insee": "00001", "nom": "Commune PC", "lat": "45.11", "lon": "4.22"},
            {"insee": "2", "nom": "Commune TPC", "lat": "45,33", "lon": "4,44"},
        ],
    )
    config_path = _write_config(tmp_path, coordinates_file="coords_raw.csv")

    result = prepare_data(config_path, input_dir=raw_dir, output_dir=output_dir)

    rows = list(csv.DictReader((output_dir / "communes_clean.csv").open(encoding="utf-8")))
    assert rows[0]["latitude"] == "45.11"
    assert rows[0]["longitude"] == "4.22"
    assert rows[1]["latitude"] == "45.33"
    assert rows[1]["longitude"] == "4.44"
    assert result.stats["communes_with_coordinates"] == 2
    assert result.stats["communes_without_coordinates"] == 0


def test_commune_without_coordinates_is_accepted_after_join(tmp_path: Path) -> None:
    config_path, raw_dir, output_dir = _prepare_fixture(tmp_path)
    _write_coordinates(raw_dir, [{"insee": "1", "nom": "Commune PC", "lat": "45.11", "lon": "4.22"}])
    config_path = _write_config(tmp_path, coordinates_file="coords_raw.csv")

    result = prepare_data(config_path, input_dir=raw_dir, output_dir=output_dir)

    rows = list(csv.DictReader((output_dir / "communes_clean.csv").open(encoding="utf-8")))
    assert rows[1]["latitude"] == ""
    assert result.stats["communes_with_coordinates"] == 1
    assert result.stats["communes_without_coordinates"] == 1
    assert result.blocking_issues == ()


def test_invalid_latitude_longitude_duplicate_and_outside_scope_are_reported(tmp_path: Path) -> None:
    config_path, raw_dir, output_dir = _prepare_fixture(tmp_path)
    _write_coordinates(
        raw_dir,
        [
            {"insee": "1", "nom": "Commune PC", "lat": "91", "lon": "4.22"},
            {"insee": "2", "nom": "Commune TPC", "lat": "45.33", "lon": "181"},
            {"insee": "2", "nom": "Commune TPC duplicate", "lat": "45.34", "lon": "4.44"},
            {"insee": "99999", "nom": "Hors perimetre", "lat": "45.0", "lon": "4.0"},
        ],
    )
    config_path = _write_config(tmp_path, coordinates_file="coords_raw.csv")

    result = prepare_data(config_path, input_dir=raw_dir, output_dir=output_dir)

    blocking = [issue.message for issue in result.blocking_issues]
    non_blocking = [issue.message for issue in result.non_blocking_issues]
    assert any("latitude" in message and "hors plage" in message for message in blocking)
    assert any("longitude" in message and "hors plage" in message for message in blocking)
    assert any("Coordonnees dupliquees" in message for message in blocking)
    assert any("hors perimetre" in message for message in non_blocking)
    assert result.stats["coordinates_outside_scope"] == 1


def test_coordinate_report_and_stats_are_generated(tmp_path: Path) -> None:
    config_path, raw_dir, output_dir = _prepare_fixture(tmp_path)
    _write_coordinates(raw_dir, [{"insee": "1", "nom": "Commune PC", "lat": "45.11", "lon": "4.22"}])
    config_path = _write_config(tmp_path, coordinates_file="coords_raw.csv")

    prepare_data(config_path, input_dir=raw_dir, output_dir=output_dir, report=True)

    report_path = tmp_path / "outputs" / "reports" / "rapport_preparation_donnees.md"
    stats_path = tmp_path / "outputs" / "reports" / "statistiques_preparation_donnees.json"
    report = report_path.read_text(encoding="utf-8").lower()
    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    assert "coordonnees" in report
    assert stats["communes_with_coordinates"] == 1
    assert stats["communes_without_coordinates"] == 1
    assert stats["coordinates_valid"] == 1


def test_prepared_coordinates_can_feed_map_export(tmp_path: Path) -> None:
    config_path, raw_dir, output_dir = _prepare_fixture(tmp_path)
    _write_coordinates(
        raw_dir,
        [
            {"insee": "1", "nom": "Commune PC", "lat": "45.11", "lon": "4.22"},
            {"insee": "2", "nom": "Commune TPC", "lat": "45.33", "lon": "4.44"},
        ],
    )
    prepare_config = _write_config(tmp_path, coordinates_file="coords_raw.csv")
    prepare_data(prepare_config, input_dir=raw_dir, output_dir=output_dir)

    fixture_config = Path("tests/fixtures/config_minimal.yaml").read_text(encoding="utf-8")
    fixture_config = fixture_config.replace("tests/fixtures/communes_minimal.csv", str(output_dir / "communes_clean.csv").replace("\\", "/"))
    fixture_config = fixture_config.replace("tests/fixtures/temps_trajet_minimal.csv", str(output_dir / "temps_trajet_clean.csv").replace("\\", "/"))
    fixture_config = fixture_config.replace("origin_id: commune_origine", "origin_id: code_commune_origine")
    fixture_config = fixture_config.replace("destination_id: commune_destination", "destination_id: code_commune_pivot")
    solver_config = tmp_path / "config_solver.yaml"
    solver_config.write_text(fixture_config, encoding="utf-8")

    config = load_config(solver_config)
    communes = load_communes(config)
    travel_times = load_travel_times(config)
    compatibilities = load_compatibilities(config)
    derived = build_derived_parameters(communes, travel_times, compatibilities, config)
    bundle = build_model(derived, config)
    solver_result = solve_model(bundle, config)
    solution = extract_solution(bundle, solver_result, communes, config)
    validation = validate_solution(solution, bundle, config)

    map_result = export_solution_map(solution, validation, bundle, config, communes, tmp_path / "map_outputs")

    assert map_result.mapped_points == 2
    assert map_result.missing_coordinates == 0


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
