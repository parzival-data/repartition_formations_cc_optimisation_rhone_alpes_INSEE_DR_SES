from __future__ import annotations

import csv
from pathlib import Path

from typer.testing import CliRunner

from travel_times.cli import app


def _write_config(tmp_path: Path, fixture_csv: Path) -> Path:
    config_path = tmp_path / "config_travel_times.yaml"
    config_path.write_text(
        "\n".join(
            [
                "input:",
                '  format: "csv"',
                f'  communes_csv_path: "{fixture_csv.as_posix()}"',
                '  default_ods_path: "unused.ods"',
                "columns:",
                '  code_commune: "code_commune"',
                '  nom_commune: "nom_commune"',
                '  categorie: "categorie"',
                '  latitude: "latitude"',
                '  longitude: "longitude"',
                '  population: "population"',
                "database:",
                f'  sqlite_path: "{(tmp_path / "cache" / "travel.sqlite").as_posix()}"',
                "candidates:",
                "  k_default: 2",
                "  k_pc: 2",
                "  k_tpc: 2",
                "runtime:",
                '  mode: "offline"',
                "  allow_network: false",
                "  max_couples: 4",
                "  offline_speed_kmh: 60",
                "  offline_distance_factor: 1.2",
                "output:",
                f'  directory: "{(tmp_path / "output").as_posix()}"',
                f'  compatible_csv_path: "{(tmp_path / "output" / "temps_trajet_clean.csv").as_posix()}"',
                f'  report_json_path: "{(tmp_path / "output" / "generation_report.json").as_posix()}"',
                "  thresholds_minutes: [60, 75, 90, 120]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return config_path


def test_cli_run_pipeline_exports_optimizer_compatible_csv(tmp_path: Path) -> None:
    fixture_csv = (Path(__file__).parent / "fixtures" / "communes_minimal.csv").resolve()
    config_path = _write_config(tmp_path, fixture_csv)
    runner = CliRunner()

    result = runner.invoke(app, ["--config", str(config_path), "run-pipeline"])

    assert result.exit_code == 0, result.output
    compatible = tmp_path / "output" / "temps_trajet_clean.csv"
    assert compatible.exists()
    rows = list(csv.DictReader(compatible.open("r", encoding="utf-8")))
    assert rows
    assert set(rows[0]) == {"code_commune_origine", "code_commune_pivot", "temps_minutes"}
    for threshold in [60, 75, 90, 120]:
        assert (tmp_path / "output" / f"travel_times_matrix_minutes_max_{threshold}min.csv").exists()
    assert (tmp_path / "output" / "generation_report.json").exists()
