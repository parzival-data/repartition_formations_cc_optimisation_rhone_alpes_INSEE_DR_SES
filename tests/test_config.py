from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from cc_formation_optimizer.config import ConfigError, load_config


FIXTURES = Path(__file__).parent / "fixtures"


def test_load_minimal_config_uses_model_notation() -> None:
    config = load_config(FIXTURES / "config_minimal.yaml")

    params = config.parameters

    assert params.T == 90
    assert params.Q == 11
    assert params.L == 1
    assert params.formation_budgets.B == 55
    assert params.formation_budgets.f == 45
    assert params.formation_budgets.k == 10
    assert params.pivot_slots.M_PC == 3
    assert params.pivot_slots.M_TPC == 1
    assert params.objective_weights.w_t == 100
    assert params.objective_weights.w_e == 1000
    assert params.objective_weights.w_m == 20


def test_main_config_is_valid() -> None:
    config = load_config(Path("config/config_ear2027.yaml"))

    budgets = config.parameters.formation_budgets

    assert budgets.B == budgets.f + budgets.k
    assert config.parameters.T == 60
    assert config.parameters.Q == 14
    assert config.parameters.L == 6
    assert config.solver["time_limit_seconds"] == 1200


def test_rejects_budget_inconsistent_with_model(tmp_path: Path) -> None:
    raw = yaml.safe_load((FIXTURES / "config_minimal.yaml").read_text(encoding="utf-8"))
    raw["parameters"]["formation_budgets"]["B"] = 54
    invalid_config = tmp_path / "invalid_budget.yaml"
    invalid_config.write_text(yaml.safe_dump(raw), encoding="utf-8")

    with pytest.raises(ConfigError, match="B = f \\+ k"):
        load_config(invalid_config)


def test_rejects_invalid_pivot_slots(tmp_path: Path) -> None:
    raw = yaml.safe_load((FIXTURES / "config_minimal.yaml").read_text(encoding="utf-8"))
    raw["parameters"]["pivot_slots"]["M_PC"] = 2
    invalid_config = tmp_path / "invalid_slots.yaml"
    invalid_config.write_text(yaml.safe_dump(raw), encoding="utf-8")

    with pytest.raises(ConfigError, match="M_PC = 3"):
        load_config(invalid_config)


def test_rejects_invalid_cc_threshold(tmp_path: Path) -> None:
    raw = yaml.safe_load((FIXTURES / "config_minimal.yaml").read_text(encoding="utf-8"))
    raw["parameters"]["cc_count"]["threshold_population"] = 4000
    invalid_config = tmp_path / "invalid_threshold.yaml"
    invalid_config.write_text(yaml.safe_dump(raw), encoding="utf-8")

    with pytest.raises(ConfigError, match="seuil de population"):
        load_config(invalid_config)
