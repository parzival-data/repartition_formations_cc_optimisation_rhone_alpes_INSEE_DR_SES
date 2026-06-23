from __future__ import annotations

import csv
from pathlib import Path

from cc_formation_optimizer.cli import main


def test_prepare_data_command_generates_outputs(tmp_path: Path, capsys) -> None:
    raw_dir = tmp_path / "raw"
    output_dir = tmp_path / "processed"
    report_root = tmp_path / "outputs"
    raw_dir.mkdir()

    with (raw_dir / "communes_raw.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["code", "nom", "type", "pop"])
        writer.writeheader()
        writer.writerow({"code": "1", "nom": "Commune PC", "type": "PC", "pop": "6000"})
        writer.writerow({"code": "2", "nom": "Commune TPC", "type": "TPC", "pop": "400"})

    with (raw_dir / "trajets_raw.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["origine", "pivot", "duree"])
        writer.writeheader()
        writer.writerow({"origine": "1", "pivot": "1", "duree": "0"})
        writer.writerow({"origine": "1", "pivot": "2", "duree": "12"})
        writer.writerow({"origine": "2", "pivot": "1", "duree": "12"})

    with (raw_dir / "coords_raw.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["insee", "lat", "lon"])
        writer.writeheader()
        writer.writerow({"insee": "1", "lat": "45.1", "lon": "4.2"})
        writer.writerow({"insee": "2", "lat": "45.3", "lon": "4.4"})

    config_path = tmp_path / "config_prepare.yaml"
    report_root_text = str(report_root).replace("\\", "/")
    config_path.write_text(
        f"""
exports:
  output_dir: {report_root_text}
data_preparation:
  communes:
    file: communes_raw.csv
    columns:
      code_commune: code
      nom_commune: nom
      categorie: type
      population: pop
  travel_times:
    file: trajets_raw.csv
    origin_column: origine
    destination_column: pivot
    minutes_column: duree
  coordinates:
    file: coords_raw.csv
    columns:
      code_commune: insee
      latitude: lat
      longitude: lon
""",
        encoding="utf-8",
    )

    status = main(
        [
            "prepare-data",
            "--config",
            str(config_path),
            "--input-dir",
            str(raw_dir),
            "--output-dir",
            str(output_dir),
            "--report",
        ]
    )

    captured = capsys.readouterr()
    assert status == 0
    assert "Communes: 2" in captured.out
    assert (output_dir / "communes_clean.csv").exists()
    assert (output_dir / "temps_trajet_clean.csv").exists()
    assert (report_root / "reports" / "rapport_preparation_donnees.md").exists()
    rows = list(csv.DictReader((output_dir / "communes_clean.csv").open(encoding="utf-8")))
    assert rows[0]["latitude"] == "45.1"
