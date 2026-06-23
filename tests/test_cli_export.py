from __future__ import annotations

from pathlib import Path

from cc_formation_optimizer.cli import main


def test_solve_command_with_export_creates_outputs(tmp_path: Path, capsys) -> None:
    status_code = main(
        [
            "solve",
            "--config",
            "tests/fixtures/config_minimal.yaml",
            "--export",
            "--output-dir",
            str(tmp_path),
        ]
    )

    captured = capsys.readouterr()

    assert status_code == 0
    assert "Validation: OK" in captured.out
    assert "Exports:" in captured.out
    assert (tmp_path / "solutions" / "sessions.csv").exists()
    assert (tmp_path / "solutions" / "communes_affectees.csv").exists()
    assert (tmp_path / "reports" / "rapport_solution.md").exists()
    assert (tmp_path / "reports" / "statistiques_solution.json").exists()
    assert (tmp_path / "reports" / "config_utilisee.yaml").exists()
