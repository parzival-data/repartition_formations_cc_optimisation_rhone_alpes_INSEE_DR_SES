from __future__ import annotations

import copy
import json
from pathlib import Path

from cc_formation_optimizer.config import config_from_dict, load_config
from cc_formation_optimizer.domain import Commune, TravelTime
from cc_formation_optimizer.relaxation import PC_TO_TPC_CONSTRAINT_MESSAGE, export_relaxation_reports, run_relaxation_workflow


FIXTURES = Path(__file__).parent / "fixtures"


def test_feasible_instance_stops_at_initial_level(valid_solution_bundle) -> None:
    _config_path, config, _bundle, _solution, _report, communes = valid_solution_bundle
    travel_times = [
        TravelTime("001", "001", 0),
        TravelTime("001", "002", 10),
        TravelTime("002", "001", 10),
        TravelTime("002", "002", 0),
    ]

    result = run_relaxation_workflow(config, communes, travel_times, [])

    assert result.accepted_attempt is not None
    assert result.accepted_attempt.level == 0
    assert len(result.attempts) == 1


def test_infeasible_instance_becomes_feasible_after_T_relaxation() -> None:
    config = _low_T_config()
    original_raw = copy.deepcopy(config.raw)
    communes = _communes()
    travel_times = [
        TravelTime("001", "001", 0),
        TravelTime("002", "001", 10),
        TravelTime("002", "002", 0),
    ]

    result = run_relaxation_workflow(config, communes, travel_times, [])

    assert result.accepted_attempt is not None
    assert result.accepted_attempt.level == 3
    assert any(change.parameter == "parameters.T" for change in result.accepted_attempt.parameter_changes)
    assert config.raw == original_raw
    assert result.pc_to_tpc_constraint_note == PC_TO_TPC_CONSTRAINT_MESSAGE


def test_relaxation_reports_write_journal_final_config_and_report(tmp_path: Path) -> None:
    config = _low_T_config()
    result = run_relaxation_workflow(
        config,
        _communes(),
        [TravelTime("001", "001", 0), TravelTime("002", "001", 10), TravelTime("002", "002", 0)],
        [],
    )

    paths = export_relaxation_reports(result, FIXTURES / "config_minimal.yaml", tmp_path)

    assert paths["journal"].exists()
    assert paths["report"].exists()
    assert paths["final_config"].exists()
    journal = json.loads(paths["journal"].read_text(encoding="utf-8"))
    assert len(journal) == len(result.attempts)
    assert any(item["parameter_changes"] for item in journal)
    assert "PC -> session TPC" in paths["report"].read_text(encoding="utf-8")


def test_relaxation_journal_is_written_even_on_failure(tmp_path: Path) -> None:
    raw = copy.deepcopy(load_config(FIXTURES / "config_minimal.yaml").raw)
    raw["parameters"]["formation_budgets"] = {"B": 0, "f": 0, "k": 0}
    raw["relaxation"] = {"enabled": False}
    config = config_from_dict(raw)

    result = run_relaxation_workflow(config, _communes(), [TravelTime("001", "001", 0)], [])
    paths = export_relaxation_reports(result, FIXTURES / "config_minimal.yaml", tmp_path)

    assert result.accepted_attempt is None
    assert paths["journal"].exists()
    assert "final_config" not in paths


def _low_T_config():
    raw = copy.deepcopy(load_config(FIXTURES / "config_minimal.yaml").raw)
    raw["parameters"]["T"] = 5
    raw["parameters"]["formation_budgets"] = {"B": 1, "f": 1, "k": 0}
    raw["relaxation"] = {
        "enabled": True,
        "w_m_values": [],
        "tpc_eligibility_cost_factors": [],
        "T_increase_factors": [3.0],
        "L_decrease_steps": [],
        "Q_increase_steps": [],
        "budget_increase_steps": {},
        "allow_replace_large_costs": False,
    }
    return config_from_dict(raw)


def _communes() -> list[Commune]:
    return [
        Commune("001", "Commune PC", 6000, "PC", "Est", 2500, 45.76, 4.84),
        Commune("002", "Commune TPC", 400, "TPC", "Nord", 180, 45.85, 4.90),
    ]
