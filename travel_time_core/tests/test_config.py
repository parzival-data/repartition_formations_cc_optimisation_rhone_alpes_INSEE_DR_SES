from __future__ import annotations

from pathlib import Path

from travel_times.config import load_settings
from travel_times.pipeline import validate_settings


def test_load_settings_resolves_paths_against_project_root() -> None:
    settings = load_settings(Path(__file__).parent / "fixtures" / "config_minimal.yaml")

    assert settings.input.communes_csv_path.name == "communes_minimal.csv"
    assert "travel_time_core" in str(settings.input.communes_csv_path)
    assert settings.output.thresholds_minutes == [60, 75, 90, 120]
    validate_settings(settings)
