from __future__ import annotations

from pathlib import Path

from cc_formation_optimizer.config import load_config
from cc_formation_optimizer.domain import Commune, TravelTime
from cc_formation_optimizer.parameters import (
    build_derived_parameters,
    cc_count_for_population,
    eligibility_costs_for_population,
    slots_for_commune,
)


FIXTURES = Path(__file__).parent / "fixtures"


def test_cc_count_rule_uses_configured_threshold() -> None:
    config = load_config(FIXTURES / "config_minimal.yaml")

    assert cc_count_for_population(5000, config) == 1
    assert cc_count_for_population(5001, config) == 2


def test_slots_follow_model_values() -> None:
    config = load_config(FIXTURES / "config_minimal.yaml")

    pc = Commune("001", "PC", 6000, "PC")
    tpc = Commune("002", "TPC", 400, "TPC")

    assert len(slots_for_commune(pc, config)) == 3
    assert len(slots_for_commune(tpc, config)) == 1


def test_build_derived_sets_follow_model() -> None:
    config = load_config(FIXTURES / "config_minimal.yaml")
    communes = [
        Commune("001", "PC", 6000, "PC"),
        Commune("002", "TPC", 400, "TPC"),
    ]
    travel_times = [
        TravelTime("001", "001", 0),
        TravelTime("001", "002", 30),
        TravelTime("002", "002", 0),
    ]

    derived = build_derived_parameters(communes, travel_times, [], config)

    assert derived.C == ("001", "002")
    assert derived.P == ("001",)
    assert derived.T == ("002",)
    assert derived.F == derived.C
    assert derived.q_i == {"001": 2, "002": 1}
    assert derived.M_j == {"001": 3, "002": 1}
    assert [(slot.pivot_id, slot.slot_index) for slot in derived.S] == [
        ("001", 1),
        ("001", 2),
        ("001", 3),
        ("002", 1),
    ]


def test_missing_travel_times_are_forbidden_and_T_controls_admissibility() -> None:
    config = load_config(FIXTURES / "config_minimal.yaml")
    communes = [
        Commune("001", "PC", 6000, "PC"),
        Commune("002", "TPC", 400, "TPC"),
    ]
    travel_times = [
        TravelTime("001", "001", 0),
        TravelTime("001", "002", config.parameters.T + 1),
    ]

    derived = build_derived_parameters(communes, travel_times, [], config)

    assert derived.a_ij[("001", "001")] == 1
    assert derived.a_ij[("001", "002")] == 0
    assert derived.a_ij[("002", "001")] == 0
    assert derived.a_ij[("002", "002")] == 0


def test_business_compatibility_defaults_to_one() -> None:
    config = load_config(FIXTURES / "config_minimal.yaml")
    communes = [
        Commune("001", "PC", 6000, "PC"),
        Commune("002", "TPC", 400, "TPC"),
    ]

    derived = build_derived_parameters(communes, [], [], config)

    assert set(derived.b_ij.values()) == {1}


def test_eligibility_costs_use_configured_population_bands() -> None:
    config = load_config(FIXTURES / "config_minimal.yaml")

    assert eligibility_costs_for_population(1600, config) == (0, 0)
    assert eligibility_costs_for_population(1200, config) == (100, 50)
    assert eligibility_costs_for_population(700, config) == (500, 150)
    assert eligibility_costs_for_population(400, config) == (1000000000, 500)
