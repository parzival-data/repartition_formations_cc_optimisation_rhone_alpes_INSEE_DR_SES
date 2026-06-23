from __future__ import annotations

from pathlib import Path

import yaml

from cc_formation_optimizer.config import load_config
from cc_formation_optimizer.domain import Commune, TravelTime
from cc_formation_optimizer.model_builder import build_model
from cc_formation_optimizer.parameters import build_derived_parameters
from cc_formation_optimizer.solution_extractor import extract_solution
from cc_formation_optimizer.solver import solve_model


FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_solution_returns_sessions_assignments_and_objective() -> None:
    config = load_config(FIXTURES / "config_minimal.yaml")
    communes = _small_communes()
    bundle = build_model(_small_derived(config, communes), config)
    result = solve_model(bundle, config)

    solution = extract_solution(bundle, result, communes, config)

    assert solution.status in {"OPTIMAL", "FEASIBLE"}
    assert solution.sessions
    assert {assignment.code_commune for assignment in solution.assignments} == {"001", "002"}
    assert solution.objective.objectif_total == result.objective_value


def test_extract_solution_uses_z_for_session_type(tmp_path: Path) -> None:
    config = _config_with_budgets(tmp_path, B=1, f=0, k=1)
    communes = [Commune("002", "Commune TPC", 400, "TPC")]
    derived = build_derived_parameters(communes, [TravelTime("002", "002", 0)], [], config)
    bundle = build_model(derived, config)
    result = solve_model(bundle, config)

    solution = extract_solution(bundle, result, communes, config)

    assert [session.type_session for session in solution.sessions] == ["TPC"]
    assert [assignment.type_session for assignment in solution.assignments] == ["TPC"]


def _small_communes() -> list[Commune]:
    return [
        Commune("001", "Commune PC", 6000, "PC", "Est", 2500),
        Commune("002", "Commune TPC", 400, "TPC", "Nord", 180),
    ]


def _small_derived(config, communes):
    return build_derived_parameters(
        communes,
        [
            TravelTime("001", "001", 0),
            TravelTime("001", "002", 10),
            TravelTime("002", "001", 10),
            TravelTime("002", "002", 0),
        ],
        [],
        config,
    )


def _config_with_budgets(tmp_path: Path, B: int, f: int, k: int):
    raw = yaml.safe_load((FIXTURES / "config_minimal.yaml").read_text(encoding="utf-8"))
    raw["parameters"]["formation_budgets"] = {"B": B, "f": f, "k": k}
    raw["solver"]["time_limit_seconds"] = 5
    path = tmp_path / "budget_config.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return load_config(path)
