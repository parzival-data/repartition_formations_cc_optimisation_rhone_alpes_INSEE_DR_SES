"""Resolution avec assouplissement hierarchique reproductible."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from typing import Any

import yaml

from cc_formation_optimizer.config import OptimizerConfig, config_from_dict
from cc_formation_optimizer.domain import Compatibility, Commune, TravelTime
from cc_formation_optimizer.model_builder import ModelBundle, build_model
from cc_formation_optimizer.parameters import build_derived_parameters
from cc_formation_optimizer.solution_extractor import ExtractedSolution, extract_solution
from cc_formation_optimizer.solver import SolveResult, solve_model
from cc_formation_optimizer.validation import SolutionValidationError, ValidationReport, validate_solution


PC_TO_TPC_CONSTRAINT_MESSAGE = (
    "La contrainte stricte PC -> session TPC est conservee a tous les niveaux "
    "et n'est jamais relachee automatiquement."
)


@dataclass(frozen=True)
class ParameterChange:
    """Modification explicite d'un parametre pour une tentative.

    Attributes
    ----------
    parameter : str
        Chemin du parametre modifie dans le YAML.
    old_value : Any
        Valeur initiale.
    new_value : Any
        Valeur testee pour la tentative.
    reason : str
        Justification metier de l'assouplissement.
    """

    parameter: str
    old_value: Any
    new_value: Any
    reason: str


@dataclass(frozen=True)
class RelaxationAttempt:
    """Journal structure d'une tentative de resolution.

    Attributes
    ----------
    attempt_id : int
        Identifiant sequentiel de la tentative.
    level : int
        Niveau hierarchique d'assouplissement.
    level_name : str
        Nom lisible du niveau.
    parameter_changes : tuple[ParameterChange, ...]
        Modifications appliquees pour cette tentative.
    solver_status : str
        Statut CP-SAT obtenu.
    validation_status : str
        Statut de validation post-solution.
    objective_total : int | None
        Objectif total si une solution a ete extraite.
    obj_trajet : int | None
        Composante trajet si disponible.
    obj_eligibilite : int | None
        Composante eligibilite si disponible.
    obj_mixite : int | None
        Composante mixite si disponible.
    solve_time_seconds : float
        Temps solveur de la tentative.
    is_solution_accepted : bool
        Indique si la tentative est la premiere solution valide retenue.
    error_message : str | None
        Erreur de construction, extraction ou validation.
    """

    attempt_id: int
    level: int
    level_name: str
    parameter_changes: tuple[ParameterChange, ...]
    solver_status: str
    validation_status: str
    objective_total: int | None
    obj_trajet: int | None
    obj_eligibilite: int | None
    obj_mixite: int | None
    solve_time_seconds: float
    is_solution_accepted: bool
    error_message: str | None


@dataclass(frozen=True)
class RelaxationResult:
    """Resultat global du workflow d'assouplissement.

    Attributes
    ----------
    attempts : tuple[RelaxationAttempt, ...]
        Tentatives executees dans l'ordre hierarchique.
    accepted_attempt : RelaxationAttempt | None
        Tentative retenue, si une solution valide existe.
    final_config : OptimizerConfig | None
        Configuration finale associee a la tentative retenue.
    final_model_bundle : ModelBundle | None
        Modele de la tentative retenue.
    final_solver_result : SolveResult | None
        Resultat solveur de la tentative retenue.
    final_solution : ExtractedSolution | None
        Solution extraite de la tentative retenue.
    final_validation_report : ValidationReport | None
        Rapport de validation de la solution retenue.
    pc_to_tpc_constraint_note : str
        Rappel de la contrainte dure non relachee.
    """

    attempts: tuple[RelaxationAttempt, ...]
    accepted_attempt: RelaxationAttempt | None
    final_config: OptimizerConfig | None
    final_model_bundle: ModelBundle | None
    final_solver_result: SolveResult | None
    final_solution: ExtractedSolution | None
    final_validation_report: ValidationReport | None
    pc_to_tpc_constraint_note: str


def run_relaxation_workflow(
    initial_config: OptimizerConfig,
    communes: list[Commune],
    travel_times: list[TravelTime],
    compatibilities: list[Compatibility],
) -> RelaxationResult:
    """Execute les tentatives dans l'ordre de la hierarchie configuree.

    Chaque tentative reconstruit les parametres derives, le modele CP-SAT,
    puis relance resolution, extraction et validation. La premiere solution
    validee est retenue.

    Parameters
    ----------
    initial_config : OptimizerConfig
        Configuration initiale non modifiee en place.
    communes : list[Commune]
        Communes chargees.
    travel_times : list[TravelTime]
        Temps de trajet propres.
    compatibilities : list[Compatibility]
        Compatibilites metier.

    Returns
    -------
    RelaxationResult
        Journal des tentatives et artefacts de la solution retenue, le cas
        echeant.
    """

    attempts: list[RelaxationAttempt] = []
    for attempt_id, candidate in enumerate(_candidate_configurations(initial_config)):
        attempt, bundle, solver_result, solution, validation_report = _run_single_attempt(
            attempt_id,
            candidate["level"],
            candidate["level_name"],
            candidate["changes"],
            candidate["config"],
            communes,
            travel_times,
            compatibilities,
        )
        attempts.append(attempt)
        if attempt.is_solution_accepted:
            return RelaxationResult(
                attempts=tuple(attempts),
                accepted_attempt=attempt,
                final_config=candidate["config"],
                final_model_bundle=bundle,
                final_solver_result=solver_result,
                final_solution=solution,
                final_validation_report=validation_report,
                pc_to_tpc_constraint_note=PC_TO_TPC_CONSTRAINT_MESSAGE,
            )

    return RelaxationResult(
        attempts=tuple(attempts),
        accepted_attempt=None,
        final_config=None,
        final_model_bundle=None,
        final_solver_result=None,
        final_solution=None,
        final_validation_report=None,
        pc_to_tpc_constraint_note=PC_TO_TPC_CONSTRAINT_MESSAGE,
    )


def export_relaxation_reports(
    result: RelaxationResult,
    initial_config_path: str | Path,
    output_dir: str | Path | None,
) -> dict[str, Path]:
    """Exporte le journal, le rapport Markdown et la configuration finale.

    La fonction ecrit dans ``reports/`` le JSON des tentatives, le rapport
    Markdown et, si une solution est retenue, le YAML de configuration finale.

    Parameters
    ----------
    result : RelaxationResult
        Resultat du workflow d'assouplissement.
    initial_config_path : str | Path
        Chemin de la configuration initiale mentionnee dans le rapport.
    output_dir : str | Path | None
        Racine de sortie optionnelle.

    Returns
    -------
    dict[str, Path]
        Chemins des rapports produits.
    """

    root = Path(output_dir) if output_dir is not None else _default_output_dir(result)
    reports_dir = root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    journal_path = reports_dir / "journal_assouplissements.json"
    report_path = reports_dir / "rapport_assouplissements.md"
    paths = {"journal": journal_path, "report": report_path}

    journal_path.write_text(json.dumps(_attempts_as_dicts(result.attempts), ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_build_markdown_report(result, initial_config_path), encoding="utf-8")

    if result.final_config is not None:
        final_config_path = reports_dir / "config_finale.yaml"
        final_config_path.write_text(yaml.safe_dump(result.final_config.raw, sort_keys=False, allow_unicode=False), encoding="utf-8")
        paths["final_config"] = final_config_path

    return paths


def _candidate_configurations(initial_config: OptimizerConfig) -> list[dict[str, Any]]:
    candidates = [
        {
            "level": 0,
            "level_name": "configuration_initiale",
            "changes": tuple(),
            "config": config_from_dict(copy.deepcopy(initial_config.raw)),
        }
    ]
    if not initial_config.relaxation.get("enabled", True):
        return candidates

    candidates.extend(_level_w_m(initial_config))
    candidates.extend(_level_tpc_eligibility(initial_config))
    candidates.extend(_level_increase_T(initial_config))
    candidates.extend(_level_reduce_L(initial_config))
    candidates.extend(_level_increase_Q(initial_config))
    candidates.extend(_level_increase_budgets(initial_config))
    candidates.extend(_level_replace_large_costs(initial_config))
    return candidates


def _level_w_m(config: OptimizerConfig) -> list[dict[str, Any]]:
    values = config.relaxation.get("w_m_values", [])
    return [
        _candidate(
            config,
            1,
            "ajustement_w_m",
            [("parameters.objective_weights.w_m", config.parameters.objective_weights.w_m, int(value), "Ajuster le poids de mixite.")],
        )
        for value in values
        if int(value) != config.parameters.objective_weights.w_m
    ]


def _level_tpc_eligibility(config: OptimizerConfig) -> list[dict[str, Any]]:
    candidates = []
    for factor in config.relaxation.get("tpc_eligibility_cost_factors", []):
        changes = []
        raw = copy.deepcopy(config.raw)
        bands = raw["parameters"]["eligibility_costs"]["population_bands"]
        for index, band in enumerate(bands):
            old = int(band["e_TPC"])
            new = int(round(old * float(factor)))
            band["e_TPC"] = new
            changes.append(
                ParameterChange(
                    f"parameters.eligibility_costs.population_bands[{index}].e_TPC",
                    old,
                    new,
                    f"Reduire les couts d'eligibilite TPC par facteur {factor}.",
                )
            )
        candidates.append(_candidate_from_raw(raw, 2, "reduction_couts_eligibilite_TPC", tuple(changes)))
    return candidates


def _level_increase_T(config: OptimizerConfig) -> list[dict[str, Any]]:
    candidates = []
    for factor in config.relaxation.get("T_increase_factors", []):
        new_T = int(ceil(config.parameters.T * float(factor)))
        if new_T != config.parameters.T:
            candidates.append(
                _candidate(
                    config,
                    3,
                    "augmentation_T",
                    [("parameters.T", config.parameters.T, new_T, f"Augmenter l'unique seuil de trajet T par facteur {factor}.")],
                )
            )
    return candidates


def _level_reduce_L(config: OptimizerConfig) -> list[dict[str, Any]]:
    minimum_L = int(config.relaxation.get("minimum_L", 1))
    candidates = []
    for step in config.relaxation.get("L_decrease_steps", []):
        new_L = max(minimum_L, config.parameters.L - int(step))
        if new_L != config.parameters.L:
            candidates.append(
                _candidate(
                    config,
                    4,
                    "reduction_L",
                    [("parameters.L", config.parameters.L, new_L, f"Reduire le remplissage minimal L de {step}.")],
                )
            )
    return candidates


def _level_increase_Q(config: OptimizerConfig) -> list[dict[str, Any]]:
    return [
        _candidate(
            config,
            5,
            "augmentation_Q",
            [("parameters.Q", config.parameters.Q, config.parameters.Q + int(step), f"Augmenter la capacite Q de {step}.")],
        )
        for step in config.relaxation.get("Q_increase_steps", [])
        if int(step) > 0
    ]


def _level_increase_budgets(config: OptimizerConfig) -> list[dict[str, Any]]:
    steps = config.relaxation.get("budget_increase_steps", {})
    f_steps = [int(value) for value in steps.get("f", [])]
    k_steps = [int(value) for value in steps.get("k", [])]
    b_steps = [int(value) for value in steps.get("B", [])]
    count = max(len(f_steps), len(k_steps), len(b_steps), 0)
    candidates = []
    old = config.parameters.formation_budgets
    for index in range(count):
        f_inc = f_steps[min(index, len(f_steps) - 1)] if f_steps else 0
        k_inc = k_steps[min(index, len(k_steps) - 1)] if k_steps else 0
        if not f_steps and not k_steps and b_steps:
            f_inc = int(ceil(b_steps[min(index, len(b_steps) - 1)] / 2))
            k_inc = b_steps[min(index, len(b_steps) - 1)] - f_inc
        new_f = old.f + f_inc
        new_k = old.k + k_inc
        new_B = new_f + new_k
        changes = [
            ("parameters.formation_budgets.f", old.f, new_f, "Augmenter le budget PC f."),
            ("parameters.formation_budgets.k", old.k, new_k, "Augmenter le budget TPC k."),
            ("parameters.formation_budgets.B", old.B, new_B, "Maintenir B = f + k apres augmentation des budgets."),
        ]
        candidates.append(_candidate(config, 6, "augmentation_budgets", changes))
    return candidates


def _level_replace_large_costs(config: OptimizerConfig) -> list[dict[str, Any]]:
    if not config.relaxation.get("allow_replace_large_costs", False):
        return []
    threshold = int(config.relaxation["large_cost_threshold"])
    replacement = int(config.relaxation["large_cost_replacement"])
    raw = copy.deepcopy(config.raw)
    changes: list[ParameterChange] = []
    costs = raw["parameters"]["eligibility_costs"]
    if int(costs["infinity"]) >= threshold:
        changes.append(
            ParameterChange(
                "parameters.eligibility_costs.infinity",
                costs["infinity"],
                replacement,
                "Remplacer le cout tres eleve configure en dernier recours.",
            )
        )
        costs["infinity"] = replacement
    for index, band in enumerate(costs["population_bands"]):
        for field in ("e_PC", "e_TPC"):
            if int(band[field]) >= threshold:
                changes.append(
                    ParameterChange(
                        f"parameters.eligibility_costs.population_bands[{index}].{field}",
                        band[field],
                        replacement,
                        "Remplacer un cout tres eleve par une penalite finie configuree.",
                    )
                )
                band[field] = replacement
    return [_candidate_from_raw(raw, 7, "remplacement_couts_tres_eleves", tuple(changes))] if changes else []


def _candidate(
    config: OptimizerConfig,
    level: int,
    level_name: str,
    changes: list[tuple[str, Any, Any, str]],
) -> dict[str, Any]:
    raw = copy.deepcopy(config.raw)
    parameter_changes = []
    for path, old, new, reason in changes:
        _set_path(raw, path, new)
        parameter_changes.append(ParameterChange(path, old, new, reason))
    return _candidate_from_raw(raw, level, level_name, tuple(parameter_changes))


def _candidate_from_raw(
    raw: dict[str, Any],
    level: int,
    level_name: str,
    changes: tuple[ParameterChange, ...],
) -> dict[str, Any]:
    return {"level": level, "level_name": level_name, "changes": changes, "config": config_from_dict(raw)}


def _set_path(raw: dict[str, Any], dotted_path: str, value: Any) -> None:
    current: Any = raw
    parts = dotted_path.split(".")
    for part in parts[:-1]:
        current = current[part]
    current[parts[-1]] = value


def _run_single_attempt(
    attempt_id: int,
    level: int,
    level_name: str,
    changes: tuple[ParameterChange, ...],
    config: OptimizerConfig,
    communes: list[Commune],
    travel_times: list[TravelTime],
    compatibilities: list[Compatibility],
) -> tuple[RelaxationAttempt, ModelBundle | None, SolveResult | None, ExtractedSolution | None, ValidationReport | None]:
    bundle = None
    solver_result = None
    solution = None
    validation_report = None
    validation_status = "NOT_RUN"
    error_message = None
    try:
        derived = build_derived_parameters(communes, travel_times, compatibilities, config)
        bundle = build_model(derived, config)
        solver_result = solve_model(bundle, config)
        if solver_result.status in {"OPTIMAL", "FEASIBLE"}:
            solution = extract_solution(bundle, solver_result, communes, config)
            validation_report = validate_solution(solution, bundle, config)
            validation_status = "OK"
        else:
            validation_status = "NO_FEASIBLE_SOLUTION"
    except (SolutionValidationError, ValueError) as exc:
        error_message = str(exc)
        validation_status = "FAILED"

    accepted = solution is not None and validation_report is not None and validation_report.is_valid
    attempt = RelaxationAttempt(
        attempt_id=attempt_id,
        level=level,
        level_name=level_name,
        parameter_changes=changes,
        solver_status=solver_result.status if solver_result is not None else "MODEL_INVALID",
        validation_status=validation_status,
        objective_total=solution.objective.objectif_total if solution is not None else None,
        obj_trajet=solution.objective.Obj_trajet if solution is not None else None,
        obj_eligibilite=solution.objective.Obj_eligibilite if solution is not None else None,
        obj_mixite=solution.objective.Obj_mixite if solution is not None else None,
        solve_time_seconds=solver_result.wall_time_seconds if solver_result is not None else 0.0,
        is_solution_accepted=accepted,
        error_message=error_message,
    )
    return attempt, bundle, solver_result, solution, validation_report


def _default_output_dir(result: RelaxationResult) -> Path:
    if result.final_config is not None:
        return Path(result.final_config.exports.get("output_dir", "outputs"))
    return Path("outputs")


def _attempts_as_dicts(attempts: tuple[RelaxationAttempt, ...]) -> list[dict[str, Any]]:
    return [
        {
            "attempt_id": attempt.attempt_id,
            "level": attempt.level,
            "level_name": attempt.level_name,
            "parameter_changes": [change.__dict__ for change in attempt.parameter_changes],
            "solver_status": attempt.solver_status,
            "validation_status": attempt.validation_status,
            "objective_total": attempt.objective_total,
            "obj_trajet": attempt.obj_trajet,
            "obj_eligibilite": attempt.obj_eligibilite,
            "obj_mixite": attempt.obj_mixite,
            "solve_time_seconds": attempt.solve_time_seconds,
            "is_solution_accepted": attempt.is_solution_accepted,
            "error_message": attempt.error_message,
        }
        for attempt in attempts
    ]


def _build_markdown_report(result: RelaxationResult, initial_config_path: str | Path) -> str:
    lines = [
        "# Rapport d'assouplissement",
        "",
        f"- Configuration initiale : `{initial_config_path}`",
        f"- Solution acceptee : {'oui' if result.accepted_attempt else 'non'}",
        f"- Niveau retenu : {result.accepted_attempt.level if result.accepted_attempt else 'aucun'}",
        f"- Tentatives executees : {len(result.attempts)}",
        f"- {result.pc_to_tpc_constraint_note}",
        "",
        "## Tentatives",
        "",
        "| ID | Niveau | Nom | Solveur | Validation | Acceptee | Objectif | Temps (s) |",
        "|---:|---:|---|---|---|---|---:|---:|",
    ]
    for attempt in result.attempts:
        lines.append(
            f"| {attempt.attempt_id} | {attempt.level} | {attempt.level_name} | {attempt.solver_status} | "
            f"{attempt.validation_status} | {attempt.is_solution_accepted} | {attempt.objective_total or ''} | "
            f"{attempt.solve_time_seconds:.3f} |"
        )
    lines.extend(["", "## Parametres modifies", ""])
    for attempt in result.attempts:
        lines.append(f"### Tentative {attempt.attempt_id} - {attempt.level_name}")
        if not attempt.parameter_changes:
            lines.append("- Aucune modification.")
        for change in attempt.parameter_changes:
            lines.append(f"- `{change.parameter}` : `{change.old_value}` -> `{change.new_value}`. {change.reason}")
        if attempt.error_message:
            lines.append(f"- Erreur : {attempt.error_message}")
        lines.append("")
    lines.extend(
        [
            "## Lecture",
            "",
            "Les tentatives sont executees dans l'ordre hierarchique configure. A chaque tentative, une copie "
            "independante de la configuration initiale est modifiee, puis toute la chaine parametres -> modele "
            "-> solveur -> extraction -> validation est relancee.",
            "",
            "La premiere tentative validee est retenue. Si aucune tentative ne passe la validation, seul le journal "
            "d'echec est exploitable pour diagnostiquer le blocage.",
        ]
    )
    return "\n".join(lines) + "\n"
