from __future__ import annotations

from pathlib import Path

from cc_formation_optimizer.cli import main


def test_solve_command_with_map_creates_html(tmp_path: Path, capsys) -> None:
    status_code = main(
        [
            "solve",
            "--config",
            "tests/fixtures/config_minimal.yaml",
            "--export",
            "--map",
            "--output-dir",
            str(tmp_path),
        ]
    )

    captured = capsys.readouterr()

    assert status_code == 0
    assert "Validation: OK" in captured.out
    assert "Carte:" in captured.out
    assert (tmp_path / "maps" / "solution_map.html").exists()
    assert (tmp_path / "solutions" / "sessions.csv").exists()


def test_solve_command_with_export_without_map_still_works(tmp_path: Path, capsys) -> None:
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
    assert "Exports:" in captured.out
    assert "Carte:" not in captured.out
    assert (tmp_path / "solutions" / "sessions.csv").exists()
    assert not (tmp_path / "maps" / "solution_map.html").exists()
