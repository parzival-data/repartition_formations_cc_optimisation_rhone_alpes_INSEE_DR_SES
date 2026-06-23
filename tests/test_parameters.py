from __future__ import annotations

from pathlib import Path

from cc_formation_optimizer.config import load_config
from cc_formation_optimizer.domain import Commune
from cc_formation_optimizer.parameters import cc_count_for_population, slots_for_commune


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
