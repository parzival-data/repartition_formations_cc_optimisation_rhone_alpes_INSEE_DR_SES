from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from cc_formation_optimizer.config import load_config
from cc_formation_optimizer.domain import Commune, TravelTime
from cc_formation_optimizer.model_builder import build_model
from cc_formation_optimizer.parameters import build_derived_parameters
from cc_formation_optimizer.solution_extractor import extract_solution
from cc_formation_optimizer.solver import solve_model
from cc_formation_optimizer.validation import SolutionValidationError, validate_solution


FIXTURES = Path(__file__).parent / "fixtures"


def test_validate_solution_accepts_correct_solution() -> None:
    config, bundle, solution = _valid_solution()

    report = validate_solution(solution, bundle, config)

    assert report.is_valid is True
    assert report.total_assignments == 2


def test_validate_solution_rejects_duplicate_commune_assignment() -> None:
    config, bundle, solution = _valid_solution()
    invalid = replace(solution, assignments=solution.assignments + (solution.assignments[0],))

    with pytest.raises(SolutionValidationError, match="plusieurs fois"):
        validate_solution(invalid, bundle, config)


def test_validate_solution_rejects_missing_commune_assignment() -> None:
    config, bundle, solution = _valid_solution()
    invalid = replace(solution, assignments=solution.assignments[:1])

    with pytest.raises(SolutionValidationError, match="oubliees"):
        validate_solution(invalid, bundle, config)


def test_validate_solution_rejects_session_above_Q() -> None:
    config, bundle, solution = _valid_solution()
    invalid_session = replace(solution.sessions[0], nombre_CC=config.parameters.Q + 1)
    invalid = replace(solution, sessions=(invalid_session,) + solution.sessions[1:])

    with pytest.raises(SolutionValidationError, match="depasse la capacite"):
        validate_solution(invalid, bundle, config)


def test_validate_solution_rejects_session_below_L() -> None:
    config, bundle, solution = _valid_solution()
    invalid_session = replace(solution.sessions[0], nombre_CC=0)
    invalid = replace(solution, sessions=(invalid_session,) + solution.sessions[1:])

    with pytest.raises(SolutionValidationError, match="sous le remplissage"):
        validate_solution(invalid, bundle, config)


def test_validate_solution_rejects_pc_assigned_to_tpc_session() -> None:
    config, bundle, solution = _valid_solution()
    pc_assignment = next(assignment for assignment in solution.assignments if assignment.categorie == "PC")
    invalid_assignment = replace(pc_assignment, type_session="TPC")
    invalid_assignments = tuple(
        invalid_assignment if assignment.code_commune == pc_assignment.code_commune else assignment
        for assignment in solution.assignments
    )
    invalid = replace(solution, assignments=invalid_assignments)

    with pytest.raises(SolutionValidationError, match="Communes PC"):
        validate_solution(invalid, bundle, config)


def test_validate_solution_rejects_absent_travel() -> None:
    config, bundle, solution = _valid_solution()
    invalid_assignment = replace(solution.assignments[0], code_pivot="999", temps_trajet_minutes=0)
    invalid = replace(solution, assignments=(invalid_assignment,) + solution.assignments[1:])

    with pytest.raises(SolutionValidationError, match="Trajet absent"):
        validate_solution(invalid, bundle, config)


def test_validate_solution_rejects_travel_above_T() -> None:
    config, bundle, solution = _valid_solution()
    invalid_assignment = replace(solution.assignments[0], temps_trajet_minutes=config.parameters.T + 1)
    invalid = replace(solution, assignments=(invalid_assignment,) + solution.assignments[1:])

    with pytest.raises(SolutionValidationError, match="Trajet superieur"):
        validate_solution(invalid, bundle, config)


@pytest.mark.parametrize(
    ("target_total", "session_type", "message"),
    [
        (56, "PC", "depasse B"),
        (46, "PC", "depasse f"),
        (11, "TPC", "depasse k"),
    ],
)
def test_validate_solution_rejects_budget_overruns(target_total: int, session_type: str, message: str) -> None:
    config, bundle, solution = _valid_solution()
    template = solution.sessions[0]
    existing_of_type = sum(1 for session in solution.sessions if session.type_session == session_type)
    needed = max(0, target_total - existing_of_type)
    sessions = solution.sessions + tuple(
        replace(template, id_session=f"extra_{index}", type_session=session_type) for index in range(needed)
    )
    invalid = replace(solution, sessions=sessions)

    with pytest.raises(SolutionValidationError, match=message):
        validate_solution(invalid, bundle, config)


def _valid_solution() -> tuple:
    config = load_config(FIXTURES / "config_minimal.yaml")
    communes = [
        Commune("001", "Commune PC", 6000, "PC", "Est", 2500),
        Commune("002", "Commune TPC", 400, "TPC", "Nord", 180),
    ]
    derived = build_derived_parameters(
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
    bundle = build_model(derived, config)
    result = solve_model(bundle, config)
    solution = extract_solution(bundle, result, communes, config)
    return config, bundle, solution
