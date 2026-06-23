from __future__ import annotations

from pathlib import Path

from cc_formation_optimizer.config import load_config
from cc_formation_optimizer.diagnostics import run_pre_solve_diagnostics
from cc_formation_optimizer.domain import Commune, TravelTime
from cc_formation_optimizer.parameters import build_derived_parameters


FIXTURES = Path(__file__).parent / "fixtures"


def test_pre_solve_diagnostic_summarizes_counts_and_detects_orphan() -> None:
    config = load_config(FIXTURES / "config_minimal.yaml")
    communes = [
        Commune("001", "PC", 6000, "PC"),
        Commune("002", "TPC", 400, "TPC"),
    ]
    travel_times = [
        TravelTime("001", "001", 0),
    ]
    derived = build_derived_parameters(communes, travel_times, [], config)

    diagnostic = run_pre_solve_diagnostics(derived, config)

    assert diagnostic.total_communes == 2
    assert diagnostic.pc_count == 1
    assert diagnostic.tpc_count == 1
    assert diagnostic.total_cc == 3
    assert diagnostic.min_required_formations == 1
    assert diagnostic.slot_count == 4
    assert diagnostic.admissible_travel_count == 1
    assert diagnostic.orphan_communes == ("002",)
    assert diagnostic.budget_warning is None


def test_pre_solve_diagnostic_detects_pc_without_pc_capable_pivot() -> None:
    config = load_config(FIXTURES / "config_minimal.yaml")
    communes = [
        Commune("001", "PC", 6000, "PC"),
        Commune("002", "TPC", 400, "TPC"),
    ]
    travel_times = [
        TravelTime("001", "002", 10),
    ]
    derived = build_derived_parameters(communes, travel_times, [], config)

    diagnostic = run_pre_solve_diagnostics(derived, config)

    assert diagnostic.pc_without_pc_pivot == ("001",)
