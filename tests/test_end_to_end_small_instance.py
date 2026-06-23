from __future__ import annotations

from pathlib import Path

from cc_formation_optimizer.config import load_config
from cc_formation_optimizer.data_loading import load_communes, load_compatibilities, load_travel_times
from cc_formation_optimizer.model_builder import build_model
from cc_formation_optimizer.parameters import build_derived_parameters
from cc_formation_optimizer.solution_extractor import extract_solution
from cc_formation_optimizer.solver import solve_model
from cc_formation_optimizer.validation import validate_solution


FIXTURES = Path(__file__).parent / "fixtures"


def test_end_to_end_small_instance_extracts_and_validates_solution() -> None:
    config = load_config(FIXTURES / "config_minimal.yaml")
    communes = load_communes(config)
    travel_times = load_travel_times(config)
    compatibilities = load_compatibilities(config)
    derived = build_derived_parameters(communes, travel_times, compatibilities, config)
    bundle = build_model(derived, config)
    result = solve_model(bundle, config)

    solution = extract_solution(bundle, result, communes, config)
    report = validate_solution(solution, bundle, config)

    assert report.is_valid is True
    assert report.total_assignments == len(communes)
    assert report.total_cc == sum(derived.q_i.values())
