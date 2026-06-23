from __future__ import annotations

import json
from pathlib import Path

from cc_formation_optimizer.cli import main


def test_solve_command_with_map_creates_html(tmp_path: Path, capsys) -> None:
    status_code = main(
        [
            "solve",
            "--config",
            "tests/fixtures/config_minimal.yaml",
            "--export",
            "--map",
            "--output-dir",
            str(tmp_path),
        ]
    )

    captured = capsys.readouterr()

    assert status_code == 0
    assert "Validation: OK" in captured.out
    assert "Carte:" in captured.out
    assert (tmp_path / "maps" / "solution_map.html").exists()
    assert (tmp_path / "solutions" / "sessions.csv").exists()


def test_solve_command_with_export_without_map_still_works(tmp_path: Path, capsys) -> None:
    status_code = main(
        [
            "solve",
            "--config",
            "tests/fixtures/config_minimal.yaml",
            "--export",
            "--output-dir",
            str(tmp_path),
        ]
    )

    captured = capsys.readouterr()

    assert status_code == 0
    assert "Exports:" in captured.out
    assert "Carte:" not in captured.out
    assert (tmp_path / "solutions" / "sessions.csv").exists()
    assert not (tmp_path / "maps" / "solution_map.html").exists()


def test_render_map_command_uses_existing_exports_without_solver(tmp_path: Path, capsys) -> None:
    _write_minimal_exports(tmp_path)

    status_code = main(
        [
            "render-map",
            "--config",
            "tests/fixtures/config_minimal.yaml",
            "--solution-dir",
            str(tmp_path),
        ]
    )

    captured = capsys.readouterr()
    html_path = tmp_path / "maps" / "solution_map.html"
    html = html_path.read_text(encoding="utf-8")

    assert status_code == 0
    assert "Carte:" in captured.out
    assert "Solveur: non relance" in captured.out
    assert html_path.exists()
    assert "const points =" in html
    assert '"lat": 45.76' in html
    assert '"lon": 4.84' in html
    assert "https://data.geopf.fr/wmts" in html
    assert "Debug carte" in html


def _write_minimal_exports(root: Path) -> None:
    solutions = root / "solutions"
    reports = root / "reports"
    solutions.mkdir()
    reports.mkdir()
    (solutions / "sessions.csv").write_text(
        "\n".join(
            [
                "id_session,code_pivot,nom_pivot,categorie_pivot,rang_m,type_session,territoire_majoritaire,nombre_communes,nombre_CC,capacite_Q,taux_remplissage,places_restantes,population_min,population_max,population_moyenne,population_mediane,temps_trajet_min,temps_trajet_moyen,temps_trajet_median,temps_trajet_max,nombre_PC,nombre_TPC,nombre_CC_PC,nombre_CC_TPC,mixite_TPC_dans_session_PC,d_jm,cout_eligibilite_pivot,objectif_trajet_session,objectif_eligibilite_session,objectif_mixite_session,alert_level,alert_reasons",
                "001_1,001,Commune PC,PC,1,PC,Est,2,3,10,0.3,7,400,6000,3200,3200,0,10,10,10,1,1,2,1,1,1,0,20,0,1,OK,",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (solutions / "communes_affectees.csv").write_text(
        "\n".join(
            [
                "code_commune,nom_commune,categorie,territoire_EAR,population,logements,nombre_CC,id_session,code_pivot,nom_pivot,type_session,temps_trajet_minutes,is_pivot,is_same_territory_as_pivot,alert_level,alert_reasons",
                "001,Commune PC,PC,Est,6000,2500,2,001_1,001,Commune PC,PC,0,True,True,OK,",
                "002,Commune TPC,TPC,Nord,400,180,1,001_1,001,Commune PC,PC,10,False,False,WARNING,commune affectee a un pivot d'un territoire different",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (reports / "statistiques_solution.json").write_text(
        json.dumps(
            {
                "solver_status": "FEASIBLE",
                "validation_status": "OK",
                "objective_total": 21,
                "obj_trajet": 20,
                "obj_eligibilite": 0,
                "obj_mixite": 1,
                "nombre_communes": 2,
                "nombre_communes_affectees": 2,
                "nombre_CC": 3,
                "sessions_ouvertes": 1,
                "B": 1,
                "sessions_PC": 1,
                "f": 1,
                "sessions_TPC": 0,
                "k": 0,
                "Q": 10,
                "L": 1,
                "T": 90,
                "temps_moyen_global": 5,
                "temps_max_global": 10,
                "sessions_sous_remplies": 0,
                "sessions_saturees": 0,
                "violations": [],
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )
