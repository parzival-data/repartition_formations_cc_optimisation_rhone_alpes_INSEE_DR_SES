from __future__ import annotations

from pathlib import Path

from cc_formation_optimizer.export import export_solution


FIXTURES = Path(__file__).parent / "fixtures"


def test_markdown_report_contains_business_summary_sections(tmp_path: Path, valid_solution_bundle) -> None:
    config_path, config, bundle, solution, report, communes = valid_solution_bundle

    result = export_solution(solution, report, bundle, config, config_path, communes, tmp_path)
    content = result.report_markdown.read_text(encoding="utf-8")

    assert "# Rapport de solution" in content
    assert "## Contraintes validees" in content
    assert "## Alertes metier" in content
    assert "## Top 10 - temps de trajet maximal" in content
    assert "## Limites connues" in content
