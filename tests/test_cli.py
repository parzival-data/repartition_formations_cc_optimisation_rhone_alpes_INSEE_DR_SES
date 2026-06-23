from __future__ import annotations

from cc_formation_optimizer.cli import main


def test_solve_command_runs_on_minimal_fixture(capsys) -> None:
    status_code = main(["solve", "--config", "tests/fixtures/config_minimal.yaml"])

    captured = capsys.readouterr()

    assert status_code == 0
    assert "Statut: OPTIMAL" in captured.out or "Statut: FEASIBLE" in captured.out
