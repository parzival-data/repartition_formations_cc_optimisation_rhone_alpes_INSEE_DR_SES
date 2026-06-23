from __future__ import annotations

from pathlib import Path

from cc_formation_optimizer.config import load_config
from cc_formation_optimizer.domain import Commune, TravelTime
from cc_formation_optimizer.model_builder import build_model
from cc_formation_optimizer.parameters import build_derived_parameters


FIXTURES = Path(__file__).parent / "fixtures"


def test_model_builds_on_small_feasible_instance() -> None:
    config = load_config(FIXTURES / "config_minimal.yaml")
    derived = _small_feasible_derived(config)

    bundle = build_model(derived, config)

    assert bundle.model.Validate() == ""
    assert len(bundle.y) == len(derived.S)
    assert len(bundle.z) == len(derived.S)
    assert len(bundle.d) == len(derived.S)


def test_x_variables_are_created_only_for_admissible_and_present_travel_times() -> None:
    config = load_config(FIXTURES / "config_minimal.yaml")
    communes = [
        Commune("001", "PC", 6000, "PC"),
        Commune("002", "TPC", 400, "TPC"),
    ]
    travel_times = [
        TravelTime("001", "001", 0),
        TravelTime("001", "002", config.parameters.T + 1),
        TravelTime("002", "002", 0),
    ]
    derived = build_derived_parameters(communes, travel_times, [], config)

    bundle = build_model(derived, config)

    assert ("001", "001", 1) in bundle.x
    assert ("001", "002", 1) not in bundle.x
    assert ("002", "001", 1) not in bundle.x
    assert ("002", "002", 1) in bundle.x


def test_y_z_and_d_exist_for_each_slot() -> None:
    config = load_config(FIXTURES / "config_minimal.yaml")
    derived = _small_feasible_derived(config)

    bundle = build_model(derived, config)
    slot_keys = {(slot.pivot_id, slot.slot_index) for slot in derived.S}

    assert set(bundle.y) == slot_keys
    assert set(bundle.z) == slot_keys
    assert set(bundle.d) == slot_keys


def test_model_proto_does_not_contain_variable_products() -> None:
    config = load_config(FIXTURES / "config_minimal.yaml")
    derived = _small_feasible_derived(config)

    bundle = build_model(derived, config)

    assert "int_prod" not in str(bundle.model.Proto())


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
