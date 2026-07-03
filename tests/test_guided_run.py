from __future__ import annotations

import csv
from pathlib import Path

import pytest

from cc_formation_optimizer.cli import main
from cc_formation_optimizer.guided_run import ensure_travel_time_diagonal


def test_guided_run_command_appears_in_help(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])

    captured = capsys.readouterr()

    assert exc.value.code == 0
    assert "guided-run" in captured.out


def test_guided_run_detects_missing_raw_file(tmp_path: Path, capsys) -> None:
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    raw_dir.mkdir()
    config_path = _write_guided_config(tmp_path, raw_dir, processed_dir)

    with pytest.raises(SystemExit) as exc:
        main(
            [
                "guided-run",
                "--config",
                str(config_path),
                "--input-dir",
                str(raw_dir),
                "--processed-dir",
                str(processed_dir),
                "--output-dir",
                str(tmp_path / "outputs"),
                "--yes",
                "--skip-travel-times",
                "--skip-solve",
                "--skip-postprocess",
            ]
        )

    captured = capsys.readouterr()
    assert exc.value.code == 2
    assert "Fichiers d'entree manquants" in captured.err
    assert "communes_raw.csv" in captured.err


def test_guided_run_stops_when_user_answers_no(monkeypatch, capsys) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")

    status = main(
        [
            "guided-run",
            "--config",
            "tests/fixtures/config_minimal.yaml",
            "--skip-travel-times",
            "--skip-solve",
            "--skip-postprocess",
        ]
    )

    captured = capsys.readouterr()
    assert status == 0
    assert "Arret demande par l'utilisateur" in captured.out


def test_ensure_travel_time_diagonal_adds_missing_without_duplicates(tmp_path: Path) -> None:
    communes = tmp_path / "communes.csv"
    travel = tmp_path / "temps.csv"
    report = tmp_path / "report.json"
    communes.write_text("code_commune,nom\n001,A\n002,B\n", encoding="utf-8")
    travel.write_text(
        "origine,destination,temps\n001,001,0\n001,002,12\n002,001,15\n",
        encoding="utf-8",
    )

    result = ensure_travel_time_diagonal(
        communes,
        travel,
        {
            "commune_id": "code_commune",
            "origin_id": "origine",
            "destination_id": "destination",
            "travel_time_minutes": "temps",
        },
        report,
    )

    rows = list(csv.DictReader(travel.open(encoding="utf-8")))
    diagonals = [row for row in rows if row["origine"] == row["destination"]]
    assert result.missing_added == 1
    assert len(diagonals) == 2
    assert {row["origine"] for row in diagonals} == {"001", "002"}
    assert all(row["temps"] == "0" for row in diagonals)


def test_ensure_travel_time_diagonal_corrects_non_zero_and_keeps_single_row(tmp_path: Path) -> None:
    communes = tmp_path / "communes.csv"
    travel = tmp_path / "temps.csv"
    communes.write_text("code_commune,nom\n001,A\n", encoding="utf-8")
    travel.write_text("origine,destination,temps\n001,001,7\n", encoding="utf-8")

    result = ensure_travel_time_diagonal(
        communes,
        travel,
        {
            "commune_id": "code_commune",
            "origin_id": "origine",
            "destination_id": "destination",
            "travel_time_minutes": "temps",
        },
        tmp_path / "report.json",
    )

    rows = list(csv.DictReader(travel.open(encoding="utf-8")))
    assert result.non_zero_found == 1
    assert result.non_zero_corrected == 1
    assert rows == [{"origine": "001", "destination": "001", "temps": "0"}]


def test_guided_run_reports_existing_exports(monkeypatch, tmp_path: Path, capsys) -> None:
    output_dir = tmp_path / "outputs"
    (output_dir / "solutions").mkdir(parents=True)
    (output_dir / "reports").mkdir()
    (output_dir / "maps").mkdir()
    for path in [
        output_dir / "solutions" / "sessions.csv",
        output_dir / "solutions" / "communes_affectees.csv",
        output_dir / "reports" / "rapport_solution.md",
        output_dir / "reports" / "statistiques_solution.json",
        output_dir / "maps" / "solution_map.html",
    ]:
        path.write_text("ok\n", encoding="utf-8")

    status = main(
        [
            "guided-run",
            "--config",
            "tests/fixtures/config_minimal.yaml",
            "--output-dir",
            str(output_dir),
            "--yes",
            "--skip-travel-times",
            "--skip-solve",
            "--skip-postprocess",
        ]
    )

    captured = capsys.readouterr()
    assert status == 0
    assert "Les exports finaux existent deja" in captured.out
    assert "Optimisation ignoree (--skip-solve)" in captured.out


def _write_guided_config(tmp_path: Path, raw_dir: Path, processed_dir: Path) -> Path:
    config_path = tmp_path / "config.yaml"
    raw = str(raw_dir).replace("\\", "/")
    processed = str(processed_dir).replace("\\", "/")
    output = str(tmp_path / "outputs").replace("\\", "/")
    config_path.write_text(
        f"""
metadata:
  name: guided_test
  version: test
inputs:
  communes_path: {processed}/communes_clean.csv
  travel_times_path: {processed}/temps_trajet_clean.csv
  compatibility_path: null
  missing_travel_time_policy: forbidden
columns:
  commune_id: code_commune
  commune_name: nom_commune
  population: population
  category: categorie
  origin_id: code_commune_origine
  destination_id: code_commune_pivot
  travel_time_minutes: temps_minutes
parameters:
  T: 60
  Q: 14
  L: 1
  formation_budgets:
    B: 2
    f: 1
    k: 1
  cc_count:
    threshold_population: 5000
    below_or_equal: 1
    above: 2
  pivot_slots:
    M_PC: 3
    M_TPC: 1
  objective_weights:
    w_t: 100
    w_e: 1000
    w_m: 20
  eligibility_costs:
    infinity: 1000000000
    population_bands:
      - min: 0
        max: null
        e_PC: 0
        e_TPC: 0
data_preparation:
  input_dir: {raw}
  output_dir: {processed}
  communes:
    file: communes_raw.csv
  travel_times:
    file: trajets_raw.csv
exports:
  output_dir: {output}
  alerts:
    capacity_close_ratio: 0.9
    low_fill_ratio: 0.35
    travel_close_ratio: 0.9
    high_tpc_mix_ratio: 0.4
    high_eligibility_cost: 500
    population_dispersion_ratio: 5.0
""",
        encoding="utf-8",
    )
    return config_path
