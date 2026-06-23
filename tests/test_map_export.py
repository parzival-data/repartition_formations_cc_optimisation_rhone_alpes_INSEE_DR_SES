from __future__ import annotations

from pathlib import Path

from cc_formation_optimizer.config import load_config
from cc_formation_optimizer.data_loading import load_communes, load_compatibilities, load_travel_times
from cc_formation_optimizer.map_export import export_solution_map
from cc_formation_optimizer.model_builder import build_model
from cc_formation_optimizer.parameters import build_derived_parameters
from cc_formation_optimizer.solution_extractor import extract_solution
from cc_formation_optimizer.solver import solve_model
from cc_formation_optimizer.validation import validate_solution


FIXTURES = Path(__file__).parent / "fixtures"


def test_map_export_creates_html_with_embedded_data(tmp_path: Path) -> None:
    config, bundle, solution, report, communes = _valid_solution_with_coordinates()

    result = export_solution_map(solution, report, bundle, config, communes, tmp_path)
    html = result.html_path.read_text(encoding="utf-8")

    assert result.html_path.exists()
    assert result.mapped_points == 2
    assert "const globalStats =" in html
    assert "const validationChecks =" in html
    assert "const points =" in html
    assert "const summary =" in html
    assert "Commune PC" in html
    assert "Commune TPC" in html
    assert "unique_assignment" in html
    assert "capacity" in html


def test_map_export_documents_missing_coordinates(tmp_path: Path, valid_solution_bundle) -> None:
    _config_path, config, bundle, solution, report, communes_without_coordinates = valid_solution_bundle

    result = export_solution_map(solution, report, bundle, config, communes_without_coordinates, tmp_path)
    html = result.html_path.read_text(encoding="utf-8")

    assert result.mapped_points == 0
    assert result.missing_coordinates == 2
    assert "Aucune coordonnee latitude/longitude disponible" in html
    assert '"communes_sans_coordonnees": 2' in html


def _valid_solution_with_coordinates():
    config = load_config(FIXTURES / "config_minimal.yaml")
    communes = load_communes(config)
    travel_times = load_travel_times(config)
    compatibilities = load_compatibilities(config)
    derived = build_derived_parameters(communes, travel_times, compatibilities, config)
    bundle = build_model(derived, config)
    solver_result = solve_model(bundle, config)
    solution = extract_solution(bundle, solver_result, communes, config)
    report = validate_solution(solution, bundle, config)
    return config, bundle, solution, report, communes
