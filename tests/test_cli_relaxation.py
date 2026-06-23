from __future__ import annotations

from cc_formation_optimizer.cli import main


def test_solve_relaxed_with_export_works_on_fixture(tmp_path, capsys) -> None:
    status_code = main(
        [
            "solve-relaxed",
            "--config",
            "tests/fixtures/config_minimal.yaml",
            "--export",
            "--output-dir",
            str(tmp_path),
        ]
    )

    captured = capsys.readouterr()

    assert status_code == 0
    assert "Solution acceptee: oui" in captured.out
    assert (tmp_path / "reports" / "journal_assouplissements.json").exists()
    assert (tmp_path / "reports" / "rapport_assouplissements.md").exists()
    assert (tmp_path / "reports" / "config_finale.yaml").exists()
    assert (tmp_path / "solutions" / "sessions.csv").exists()


def test_solve_relaxed_with_export_and_map_works_on_fixture(tmp_path, capsys) -> None:
    status_code = main(
        [
            "solve-relaxed",
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
    assert "Carte:" in captured.out
    assert (tmp_path / "maps" / "solution_map.html").exists()
