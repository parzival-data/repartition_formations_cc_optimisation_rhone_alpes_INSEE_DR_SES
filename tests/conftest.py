from __future__ import annotations

from pathlib import Path

import pytest

from cc_formation_optimizer.config import load_config
from cc_formation_optimizer.domain import Commune, TravelTime
from cc_formation_optimizer.model_builder import build_model
from cc_formation_optimizer.parameters import build_derived_parameters
from cc_formation_optimizer.solution_extractor import extract_solution
from cc_formation_optimizer.solver import solve_model
from cc_formation_optimizer.validation import validate_solution


@pytest.fixture
def valid_solution_bundle():
    config_path = Path("tests/fixtures/config_minimal.yaml")
    config = load_config(config_path)
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
    solver_result = solve_model(bundle, config)
    solution = extract_solution(bundle, solver_result, communes, config)
    report = validate_solution(solution, bundle, config)
    return config_path, config, bundle, solution, report, communes
