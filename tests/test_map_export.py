from __future__ import annotations

import json
import re
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
    assert "https://data.geopf.fr/wmts" in html
    assert "SERVICE=WMTS" in html
    assert "TILEMATRIX=${z}" in html
    assert "TILEROW=${y}" in html
    assert "TILECOL=${x}" in html
    assert "Fond de carte non chargé. Vérifier l’accès réseau à data.geopf.fr." in html
    assert "Debug carte" in html
    assert "points_avec_coordonnees" in html
    assert "lonLatToWorld" in html
    assert "worldToScreen" in html
    assert "drawTiles" in html
    assert "drawPoints" in html
    assert "tileLayer" in html


def test_map_export_documents_missing_coordinates(tmp_path: Path, valid_solution_bundle) -> None:
    _config_path, config, bundle, solution, report, communes_without_coordinates = valid_solution_bundle

    result = export_solution_map(solution, report, bundle, config, communes_without_coordinates, tmp_path)
    html = result.html_path.read_text(encoding="utf-8")

    assert result.mapped_points == 0
    assert result.missing_coordinates == 2
    assert "Aucune coordonnee latitude/longitude disponible" in html
    assert '"communes_sans_coordonnees": 2' in html


def test_map_export_embeds_numeric_non_inverted_coordinates_and_bounds(tmp_path: Path) -> None:
    config, bundle, solution, report, communes = _valid_solution_with_coordinates()

    result = export_solution_map(solution, report, bundle, config, communes, tmp_path)
    html = result.html_path.read_text(encoding="utf-8")
    points = _extract_js_payload(html, "points")

    assert points
    assert all(isinstance(point["lat"], float) for point in points)
    assert all(isinstance(point["lon"], float) for point in points)
    assert {point["lat"] for point in points} == {45.76, 45.85}
    assert {point["lon"] for point in points} == {4.84, 4.9}
    assert min(point["lat"] for point in points) == 45.76
    assert max(point["lat"] for point in points) == 45.85
    assert min(point["lon"] for point in points) == 4.84
    assert max(point["lon"] for point in points) == 4.9


def test_map_export_keeps_points_available_when_tiles_fail(tmp_path: Path) -> None:
    config, bundle, solution, report, communes = _valid_solution_with_coordinates()

    result = export_solution_map(solution, report, bundle, config, communes, tmp_path)
    html = result.html_path.read_text(encoding="utf-8")

    assert "img.onerror" in html
    assert "updateTileFallback" in html
    assert "drawPoints(data)" in html
    assert "const points =" in html


def test_map_export_pivots_only_filter_uses_boolean_pivot_flag(tmp_path: Path) -> None:
    config, bundle, solution, report, communes = _valid_solution_with_coordinates()

    result = export_solution_map(solution, report, bundle, config, communes, tmp_path)
    html = result.html_path.read_text(encoding="utf-8")
    points = _extract_js_payload(html, "points")

    assert any(point["is_pivot"] is True for point in points)
    assert any(point["is_pivot"] is False for point in points)
    assert all(isinstance(point["is_pivot"], bool) for point in points)
    assert '"is_pivot": true' in html
    assert '"is_pivot": "true"' not in html
    assert '"is_pivot": 1' not in html
    assert '<input id="pivotOnly" type="checkbox">' in html
    assert "Afficher les pivots seulement" in html
    assert "'pivotOnly','showLinks','selectedOnly'" in html
    assert "addEventListener('change', render)" in html
    assert "if (pivotsOnly && p.is_pivot !== true) return false;" in html
    assert "drawPoints(data)" in html
    assert "function drawPoints(data)" in html
    assert "showLinks').checked && !pivotsOnly" in html


def _extract_js_payload(html: str, name: str):
    match = re.search(rf"const {name} = (.*?);", html, flags=re.DOTALL)
    assert match is not None
    return json.loads(match.group(1))


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
