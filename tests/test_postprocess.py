from __future__ import annotations

import csv
from pathlib import Path

from cc_formation_optimizer.cli import main
from cc_formation_optimizer.config import load_config
from cc_formation_optimizer.business_postprocess import postprocess_business_rules


def test_tpc_session_with_external_pivot_proposes_internal_pivot(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        _write_travel_csv(tmp_path / "travel.csv", [("A", "P1", 20), ("B", "P1", 30), ("B", "A", 10), ("A", "B", 20)]),
    )
    _write_exports(
        tmp_path,
        sessions=[_session("S1", "P1", "Pivot externe", "TPC")],
        assignments=[
            _assignment("A", "Alpha", "TPC", "S1", "P1", "Pivot externe", "TPC", 20),
            _assignment("B", "Beta", "TPC", "S1", "P1", "Pivot externe", "TPC", 30),
        ],
    )

    result = postprocess_business_rules(tmp_path, load_config(config_path), output_dir=tmp_path / "postprocess")

    rows = _read_rows(result.proposals_csv)
    r1_rows = [row for row in rows if row["rule_id"] == "R1"]
    assert len(r1_rows) == 1
    assert r1_rows[0]["proposed_pivot_code"] == "A"
    assert r1_rows[0]["model_constraints_respected"] == "true"
    assert int(r1_rows[0]["travel_time_gain_min"]) == 40


def test_tpc_session_with_internal_pivot_does_not_trigger_rule_1(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, _write_travel_csv(tmp_path / "travel.csv", [("B", "A", 10), ("A", "B", 10)]))
    _write_exports(
        tmp_path,
        sessions=[_session("S1", "A", "Alpha", "TPC")],
        assignments=[
            _assignment("A", "Alpha", "TPC", "S1", "A", "Alpha", "TPC", 0),
            _assignment("B", "Beta", "TPC", "S1", "A", "Alpha", "TPC", 10),
        ],
    )

    result = postprocess_business_rules(tmp_path, load_config(config_path), output_dir=tmp_path / "postprocess")

    rows = _read_rows(result.proposals_csv)
    assert [row for row in rows if row["rule_id"] == "R1"] == []


def test_pivot_absent_from_own_session_triggers_rule_2(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, _write_travel_csv(tmp_path / "travel.csv", [("P1", "X", 12), ("C", "P1", 8)]))
    _write_exports(
        tmp_path,
        sessions=[
            _session("P1_1", "P1", "Pivot un", "PC"),
            _session("X_1", "X", "Pivot deux", "PC"),
        ],
        assignments=[
            _assignment("P1", "Pivot un", "PC", "X_1", "X", "Pivot deux", "PC", 12),
            _assignment("X", "Pivot deux", "PC", "X_1", "X", "Pivot deux", "PC", 0),
            _assignment("C", "Commune", "PC", "P1_1", "P1", "Pivot un", "PC", 8),
        ],
    )

    result = postprocess_business_rules(tmp_path, load_config(config_path), output_dir=tmp_path / "postprocess")

    r2_rows = [row for row in _read_rows(result.proposals_csv) if row["rule_id"] == "R2"]
    assert len(r2_rows) == 1
    assert r2_rows[0]["commune_code"] == "P1"
    assert r2_rows[0]["current_session_id"] == "X_1"
    assert r2_rows[0]["proposed_session_id"] == "P1_1"


def test_commune_closer_to_same_type_pivot_triggers_rule_3(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, _write_travel_csv(tmp_path / "travel.csv", [("C", "A", 30), ("C", "B", 10)]))
    _write_exports(
        tmp_path,
        sessions=[
            _session("A_1", "A", "Alpha", "PC"),
            _session("B_1", "B", "Beta", "PC"),
        ],
        assignments=[
            _assignment("A", "Alpha", "PC", "A_1", "A", "Alpha", "PC", 0),
            _assignment("B", "Beta", "PC", "B_1", "B", "Beta", "PC", 0),
            _assignment("C", "Commune", "PC", "A_1", "A", "Alpha", "PC", 30),
        ],
    )

    result = postprocess_business_rules(tmp_path, load_config(config_path), output_dir=tmp_path / "postprocess")

    r3_rows = [row for row in _read_rows(result.proposals_csv) if row["rule_id"] == "R3" and row["commune_code"] == "C"]
    assert len(r3_rows) == 1
    assert r3_rows[0]["proposed_session_id"] == "B_1"
    assert int(r3_rows[0]["travel_time_gain_min"]) == 20


def test_commune_closer_to_different_type_pivot_does_not_trigger_rule_3(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, _write_travel_csv(tmp_path / "travel.csv", [("C", "A", 30), ("C", "B", 10)]))
    _write_exports(
        tmp_path,
        sessions=[
            _session("A_1", "A", "Alpha", "PC"),
            _session("B_1", "B", "Beta", "TPC"),
        ],
        assignments=[
            _assignment("A", "Alpha", "PC", "A_1", "A", "Alpha", "PC", 0),
            _assignment("B", "Beta", "TPC", "B_1", "B", "Beta", "TPC", 0),
            _assignment("C", "Commune", "PC", "A_1", "A", "Alpha", "PC", 30),
        ],
    )

    result = postprocess_business_rules(tmp_path, load_config(config_path), output_dir=tmp_path / "postprocess")

    assert [row for row in _read_rows(result.proposals_csv) if row["rule_id"] == "R3" and row["commune_code"] == "C"] == []


def test_capacity_violation_is_kept_and_marked_as_not_respecting_constraints(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        _write_travel_csv(tmp_path / "travel.csv", [("C", "A", 30), ("C", "B", 10)]),
        capacity=1,
    )
    _write_exports(
        tmp_path,
        sessions=[
            _session("A_1", "A", "Alpha", "PC", cc=2),
            _session("B_1", "B", "Beta", "PC", cc=1),
        ],
        assignments=[
            _assignment("A", "Alpha", "PC", "A_1", "A", "Alpha", "PC", 0),
            _assignment("B", "Beta", "PC", "B_1", "B", "Beta", "PC", 0),
            _assignment("C", "Commune", "PC", "A_1", "A", "Alpha", "PC", 30),
        ],
    )

    result = postprocess_business_rules(tmp_path, load_config(config_path), output_dir=tmp_path / "postprocess")

    r3_rows = [row for row in _read_rows(result.proposals_csv) if row["rule_id"] == "R3" and row["commune_code"] == "C"]
    assert len(r3_rows) == 1
    assert r3_rows[0]["model_constraints_respected"] == "false"
    assert "capacite depassee" in r3_rows[0]["warning"]


def test_postprocess_does_not_modify_original_exports(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, _write_travel_csv(tmp_path / "travel.csv", [("C", "A", 30), ("C", "B", 10)]))
    _write_exports(
        tmp_path,
        sessions=[_session("A_1", "A", "Alpha", "PC"), _session("B_1", "B", "Beta", "PC")],
        assignments=[
            _assignment("A", "Alpha", "PC", "A_1", "A", "Alpha", "PC", 0),
            _assignment("B", "Beta", "PC", "B_1", "B", "Beta", "PC", 0),
            _assignment("C", "Commune", "PC", "A_1", "A", "Alpha", "PC", 30),
        ],
    )
    sessions_path = tmp_path / "solutions" / "sessions.csv"
    assignments_path = tmp_path / "solutions" / "communes_affectees.csv"
    before_sessions = sessions_path.read_text(encoding="utf-8")
    before_assignments = assignments_path.read_text(encoding="utf-8")

    postprocess_business_rules(tmp_path, load_config(config_path), output_dir=tmp_path / "postprocess")

    assert sessions_path.read_text(encoding="utf-8") == before_sessions
    assert assignments_path.read_text(encoding="utf-8") == before_assignments


def test_postprocess_business_rules_cli_creates_outputs(tmp_path: Path, capsys) -> None:
    config_path = _write_config(tmp_path, _write_travel_csv(tmp_path / "travel.csv", [("C", "A", 30), ("C", "B", 10)]))
    output_dir = tmp_path / "business"
    _write_exports(
        tmp_path,
        sessions=[_session("A_1", "A", "Alpha", "PC"), _session("B_1", "B", "Beta", "PC")],
        assignments=[
            _assignment("A", "Alpha", "PC", "A_1", "A", "Alpha", "PC", 0),
            _assignment("B", "Beta", "PC", "B_1", "B", "Beta", "PC", 0),
            _assignment("C", "Commune", "PC", "A_1", "A", "Alpha", "PC", 30),
        ],
    )

    status_code = main(
        [
            "postprocess-business-rules",
            "--config",
            str(config_path),
            "--input-dir",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ]
    )

    captured = capsys.readouterr()
    assert status_code == 0
    assert "Business post-processing completed." in captured.out
    assert f"Proposals written to: {output_dir / 'business_reallocation_proposals.csv'}" in captured.out
    assert f"Summary written to: {output_dir / 'business_reallocation_summary.csv'}" in captured.out
    assert "Original optimization exports were not modified." in captured.out
    assert "Solveur: non relance" in captured.out
    assert (output_dir / "business_reallocation_proposals.csv").exists()
    assert (output_dir / "business_reallocation_summary.csv").exists()


def test_public_import_uses_business_postprocess_subpackage() -> None:
    assert postprocess_business_rules.__module__ == "cc_formation_optimizer.business_postprocess.runner"


def _write_config(tmp_path: Path, travel_csv: Path, capacity: int = 11) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
metadata:
  name: postprocess_test
  version: test
inputs:
  communes_path: {tmp_path.as_posix()}/communes.csv
  travel_times_path: {travel_csv.as_posix()}
  compatibility_path: null
  missing_travel_time_policy: forbidden
columns:
  commune_id: code_commune
  commune_name: nom_commune
  population: population
  category: categorie
  territory_ear: territoire_EAR
  housing: logements
  latitude: latitude
  longitude: longitude
  origin_id: commune_origine
  destination_id: commune_destination
  travel_time_minutes: temps_minutes
  compatibility_allowed: compatible
parameters:
  T: 90
  Q: {capacity}
  L: 1
  formation_budgets:
    B: 55
    f: 45
    k: 10
  cc_count:
    threshold_population: 5000
    below_or_equal: 1
    above: 2
  pivot_slots:
    M_PC: 3
    M_TPC: 1
  objective_weights:
    w_t: 1
    w_e: 1000
    w_m: 500
  eligibility_costs:
    infinity: 1000000000
    population_bands:
      - min: 0
        max: null
        e_PC: 0
        e_TPC: 0
solver: {{}}
relaxation: {{}}
exports: {{}}
""".lstrip(),
        encoding="utf-8",
    )
    return config_path


def _write_travel_csv(path: Path, rows: list[tuple[str, str, int]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["commune_origine", "commune_destination", "temps_minutes"])
        writer.writeheader()
        for origin, destination, minutes in rows:
            writer.writerow({"commune_origine": origin, "commune_destination": destination, "temps_minutes": minutes})
    return path


def _write_exports(root: Path, sessions: list[dict[str, object]], assignments: list[dict[str, object]]) -> None:
    solutions = root / "solutions"
    solutions.mkdir(parents=True, exist_ok=True)
    _write_csv(solutions / "sessions.csv", ["id_session", "code_pivot", "nom_pivot", "type_session", "nombre_CC", "temps_trajet_max"], sessions)
    _write_csv(
        solutions / "communes_affectees.csv",
        [
            "code_commune",
            "nom_commune",
            "categorie",
            "territoire_EAR",
            "population",
            "nombre_CC",
            "id_session",
            "code_pivot",
            "nom_pivot",
            "type_session",
            "temps_trajet_minutes",
        ],
        assignments,
    )


def _session(session_id: str, pivot_code: str, pivot_name: str, session_type: str, cc: int = 1) -> dict[str, object]:
    return {
        "id_session": session_id,
        "code_pivot": pivot_code,
        "nom_pivot": pivot_name,
        "type_session": session_type,
        "nombre_CC": cc,
        "temps_trajet_max": 0,
    }


def _assignment(
    code: str,
    name: str,
    category: str,
    session_id: str,
    pivot_code: str,
    pivot_name: str,
    session_type: str,
    travel_time: int,
    cc: int = 1,
) -> dict[str, object]:
    return {
        "code_commune": code,
        "nom_commune": name,
        "categorie": category,
        "territoire_EAR": "T1",
        "population": 1000,
        "nombre_CC": cc,
        "id_session": session_id,
        "code_pivot": pivot_code,
        "nom_pivot": pivot_name,
        "type_session": session_type,
        "temps_trajet_minutes": travel_time,
    }


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))
