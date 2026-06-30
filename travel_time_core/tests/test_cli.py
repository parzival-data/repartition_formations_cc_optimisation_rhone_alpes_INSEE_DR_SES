from __future__ import annotations

import pytest
import typer

from travel_times.cli import _parse_thresholds


def test_parse_thresholds_defaults_shape() -> None:
    assert _parse_thresholds("60,90,120") == [60, 90, 120]


def test_parse_thresholds_ignores_empty_items() -> None:
    assert _parse_thresholds("60, 90, ,120") == [60, 90, 120]


def test_parse_thresholds_rejects_invalid_values() -> None:
    with pytest.raises(typer.BadParameter):
        _parse_thresholds("60,abc")


def test_parse_thresholds_rejects_non_positive_values() -> None:
    with pytest.raises(typer.BadParameter):
        _parse_thresholds("60,0")
