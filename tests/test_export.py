from __future__ import annotations

import csv
import json
from dataclasses import replace
from pathlib import Path

import pytest

from cc_formation_optimizer.export import ASSIGNMENT_COLUMNS, SESSION_COLUMNS, ExportError, export_solution


FIXTURES = Path(__file__).parent / "fixtures"


def test_export_solution_creates_csv_json_report_and_config_copy(tmp_path: Path, valid_solution_bundle) -> None:
    config_path, config, bundle, solution, report, communes = valid_solution_bundle

    result = export_solution(solution, report, bundle, config, config_path, communes, tmp_path)

    assert result.sessions_csv.exists()
    assert result.assignments_csv.exists()
    assert result.report_markdown.exists()
    assert result.statistics_json.exists()
    assert result.used_config_yaml.exists()
    assert result.used_config_yaml.read_text(encoding="utf-8") == config_path.read_text(encoding="utf-8")


def test_export_csv_files_contain_expected_columns(tmp_path: Path, valid_solution_bundle) -> None:
    config_path, config, bundle, solution, report, communes = valid_solution_bundle

    result = export_solution(solution, report, bundle, config, config_path, communes, tmp_path)

    with result.sessions_csv.open("r", encoding="utf-8", newline="") as stream:
        assert csv.DictReader(stream).fieldnames == SESSION_COLUMNS
    with result.assignments_csv.open("r", encoding="utf-8", newline="") as stream:
        assert csv.DictReader(stream).fieldnames == ASSIGNMENT_COLUMNS


def test_export_statistics_json_contains_required_keys(tmp_path: Path, valid_solution_bundle) -> None:
    config_path, config, bundle, solution, report, communes = valid_solution_bundle

    result = export_solution(solution, report, bundle, config, config_path, communes, tmp_path)
    payload = json.loads(result.statistics_json.read_text(encoding="utf-8"))

    assert payload["solver_status"] in {"OPTIMAL", "FEASIBLE"}
    assert payload["validation_status"] == "OK"
    assert payload["objective_total"] == solution.objective.objectif_total
    assert payload["sessions_ouvertes"] == len(solution.sessions)
    assert payload["Q"] == config.parameters.Q
    assert payload["T"] == config.parameters.T


def test_export_refuses_invalid_validation_report(tmp_path: Path, valid_solution_bundle) -> None:
    config_path, config, bundle, solution, report, communes = valid_solution_bundle
    invalid_report = replace(report, is_valid=False)

    with pytest.raises(ExportError, match="validation"):
        export_solution(solution, invalid_report, bundle, config, config_path, communes, tmp_path)

    assert not (tmp_path / "solutions").exists()
    assert not (tmp_path / "reports").exists()
