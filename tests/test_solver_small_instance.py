from __future__ import annotations

from pathlib import Path

import yaml

from cc_formation_optimizer.config import load_config
from cc_formation_optimizer.domain import Commune, TravelTime
from cc_formation_optimizer.model_builder import build_model
from cc_formation_optimizer.parameters import build_derived_parameters
from cc_formation_optimizer.solver import solve_model


FIXTURES = Path(__file__).parent / "fixtures"


def test_solver_finds_solution_for_small_feasible_instance() -> None:
    config = load_config(FIXTURES / "config_minimal.yaml")
    derived = _small_feasible_derived(config)

    result = solve_model(build_model(derived, config), config)

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.objective_value is not None


def test_solver_detects_infeasible_budget_instance(tmp_path: Path) -> None:
    config = _config_with_zero_budgets(tmp_path)
    derived = _small_feasible_derived(config)

    result = solve_model(build_model(derived, config), config)

    assert result.status in {"INFEASIBLE", "MODEL_INVALID", "UNKNOWN"}
    assert result.objective_value is None


def test_solution_respects_capacity_and_budget_indirectly() -> None:
    config = load_config(FIXTURES / "config_minimal.yaml")
    derived = _small_feasible_derived(config)
    bundle = build_model(derived, config)

    result = solve_model(bundle, config)

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    opened_slots = [slot_key for slot_key, variable in bundle.y.items() if result.solver.Value(variable) == 1]
    pc_slots = sum(result.solver.Value(bundle.y[key]) - result.solver.Value(bundle.z[key]) for key in bundle.y)
    tpc_slots = sum(result.solver.Value(bundle.z[key]) for key in bundle.z)

    assert opened_slots
    assert pc_slots <= config.parameters.formation_budgets.f
    assert tpc_slots <= config.parameters.formation_budgets.k
    for pivot_id, slot_index in opened_slots:
        load = sum(
            derived.q_i[commune_id] * result.solver.Value(variable)
            for (commune_id, j, m), variable in bundle.x.items()
            if j == pivot_id and m == slot_index
        )
        assert config.parameters.L <= load <= config.parameters.Q


def _small_feasible_derived(config):
    communes = [
        Commune("001", "PC", 6000, "PC"),
        Commune("002", "TPC", 400, "TPC"),
    ]
    travel_times = [
        TravelTime("001", "001", 0),
        TravelTime("001", "002", 10),
        TravelTime("002", "001", 10),
        TravelTime("002", "002", 0),
    ]
    return build_derived_parameters(communes, travel_times, [], config)


def _config_with_zero_budgets(tmp_path: Path):
    raw = yaml.safe_load((FIXTURES / "config_minimal.yaml").read_text(encoding="utf-8"))
    raw["parameters"]["formation_budgets"] = {"B": 0, "f": 0, "k": 0}
    raw["solver"]["time_limit_seconds"] = 5
    raw["solver"]["log_search_progress"] = False
    path = tmp_path / "zero_budgets.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return load_config(path)
