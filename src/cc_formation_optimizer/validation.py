"""Validation automatique des solutions produites."""

from __future__ import annotations

from dataclasses import dataclass

from cc_formation_optimizer.config import OptimizerConfig
from cc_formation_optimizer.model_builder import ModelBundle
from cc_formation_optimizer.solution_extractor import ExtractedSolution


class SolutionValidationError(ValueError):
    """Erreur explicite lorsque la solution viole le modele.

    L'exception est levee des qu'un controle post-solution detecte une
    affectation, une session, un trajet ou un objectif incoherent.
    """


@dataclass(frozen=True)
class ValidationReport:
    """Rapport de validation d'une solution.

    Attributes
    ----------
    is_valid : bool
        Indique si tous les controles ont reussi.
    checked_constraints : tuple[str, ...]
        Identifiants des familles de contraintes controlees.
    total_sessions : int
        Nombre de sessions ouvertes dans la solution.
    total_assignments : int
        Nombre de communes affectees.
    total_cc : int
        Nombre total de CC affectes.
    """

    is_valid: bool
    checked_constraints: tuple[str, ...]
    total_sessions: int
    total_assignments: int
    total_cc: int


def validate_solution(
    solution: ExtractedSolution,
    model_bundle: ModelBundle,
    config: OptimizerConfig,
    tolerance: float = 1e-6,
) -> ValidationReport:
    """Valide une solution extraite contre les contraintes du modele.

    La fonction suppose une solution deja extraite depuis un statut solveur
    faisable. Elle controle les affectations uniques, ouvertures, capacites,
    budgets, trajets admissibles, compatibilites, types de sessions, mixite et
    objectif recalcule.

    Parameters
    ----------
    solution : ExtractedSolution
        Solution extraite a controler.
    model_bundle : ModelBundle
        Modele et parametres derives ayant produit la solution.
    config : OptimizerConfig
        Configuration contenant les seuils, budgets et poids d'objectif.
    tolerance : float, default=1e-6
        Tolerance de comparaison avec l'objectif retourne par le solveur.

    Returns
    -------
    ValidationReport
        Rapport synthetique si tous les controles passent.

    Raises
    ------
    SolutionValidationError
        Si une contrainte controlee est violee.
    """

    sessions_by_id = {session.id_session: session for session in solution.sessions}
    assignments_by_commune: dict[str, list] = {}
    for assignment in solution.assignments:
        assignments_by_commune.setdefault(assignment.code_commune, []).append(assignment)

    _validate_unique_assignment(assignments_by_commune, model_bundle)
    _validate_open_sessions(solution, sessions_by_id)
    _validate_capacity(solution, config)
    _validate_budgets(solution, config)
    _validate_pc_to_tpc_asymmetry(solution)
    _validate_travel_and_compatibility(solution, model_bundle, config)
    _validate_session_types(solution)
    _validate_mixing(solution, model_bundle, config)
    _validate_objective(solution, model_bundle, config, tolerance)

    return ValidationReport(
        is_valid=True,
        checked_constraints=(
            "unique_assignment",
            "opening",
            "capacity",
            "budgets",
            "pc_to_tpc_asymmetry",
            "travel",
            "compatibility",
            "session_type",
            "mixing",
            "objective",
        ),
        total_sessions=len(solution.sessions),
        total_assignments=len(solution.assignments),
        total_cc=sum(assignment.nombre_CC for assignment in solution.assignments),
    )


def _validate_unique_assignment(assignments_by_commune: dict[str, list], model_bundle: ModelBundle) -> None:
    expected = set(model_bundle.derived.C)
    observed = set(assignments_by_commune)

    missing = expected - observed
    if missing:
        raise SolutionValidationError(f"Communes oubliees dans la solution: {', '.join(sorted(missing))}.")

    unexpected = observed - expected
    if unexpected:
        raise SolutionValidationError(f"Communes inconnues dans la solution: {', '.join(sorted(unexpected))}.")

    duplicated = sorted(commune_id for commune_id, assignments in assignments_by_commune.items() if len(assignments) != 1)
    if duplicated:
        raise SolutionValidationError(f"Communes affectees plusieurs fois: {', '.join(duplicated)}.")


def _validate_open_sessions(solution: ExtractedSolution, sessions_by_id: dict) -> None:
    for assignment in solution.assignments:
        if assignment.id_session not in sessions_by_id:
            raise SolutionValidationError(
                f"La commune {assignment.code_commune} est affectee a une session fermee ou inconnue: "
                f"{assignment.id_session}."
            )


def _validate_capacity(solution: ExtractedSolution, config: OptimizerConfig) -> None:
    for session in solution.sessions:
        if session.nombre_CC < config.parameters.L:
            raise SolutionValidationError(
                f"La session {session.id_session} est sous le remplissage minimal L={config.parameters.L}."
            )
        if session.nombre_CC > config.parameters.Q:
            raise SolutionValidationError(
                f"La session {session.id_session} depasse la capacite Q={config.parameters.Q}."
            )


def _validate_budgets(solution: ExtractedSolution, config: OptimizerConfig) -> None:
    budgets = config.parameters.formation_budgets
    pc_sessions = sum(1 for session in solution.sessions if session.type_session == "PC")
    tpc_sessions = sum(1 for session in solution.sessions if session.type_session == "TPC")

    if len(solution.sessions) > budgets.B:
        raise SolutionValidationError(f"Le nombre total de sessions depasse B={budgets.B}.")
    if pc_sessions > budgets.f:
        raise SolutionValidationError(f"Le nombre de sessions PC depasse f={budgets.f}.")
    if tpc_sessions > budgets.k:
        raise SolutionValidationError(f"Le nombre de sessions TPC depasse k={budgets.k}.")


def _validate_pc_to_tpc_asymmetry(solution: ExtractedSolution) -> None:
    offenders = [
        assignment.code_commune
        for assignment in solution.assignments
        if assignment.categorie == "PC" and assignment.type_session == "TPC"
    ]
    if offenders:
        raise SolutionValidationError(
            "Communes PC affectees a une session TPC: " + ", ".join(sorted(offenders)) + "."
        )


def _validate_travel_and_compatibility(
    solution: ExtractedSolution,
    model_bundle: ModelBundle,
    config: OptimizerConfig,
) -> None:
    for assignment in solution.assignments:
        key = (assignment.code_commune, assignment.code_pivot)
        if key not in model_bundle.derived.tau_ij:
            raise SolutionValidationError(
                f"Trajet absent utilise dans la solution: {assignment.code_commune} -> {assignment.code_pivot}."
            )
        if assignment.temps_trajet_minutes > config.parameters.T:
            raise SolutionValidationError(
                f"Trajet superieur a T={config.parameters.T}: {assignment.code_commune} -> {assignment.code_pivot}."
            )
        if model_bundle.derived.tau_ij[key] != assignment.temps_trajet_minutes:
            raise SolutionValidationError(
                f"Temps de trajet incoherent pour {assignment.code_commune} -> {assignment.code_pivot}."
            )
        if model_bundle.derived.b_ij[key] != 1:
            raise SolutionValidationError(
                f"Compatibilite interdite utilisee: {assignment.code_commune} -> {assignment.code_pivot}."
            )


def _validate_session_types(solution: ExtractedSolution) -> None:
    for session in solution.sessions:
        if session.type_session not in {"PC", "TPC"}:
            raise SolutionValidationError(f"Type de session invalide pour {session.id_session}: {session.type_session}.")


def _validate_mixing(solution: ExtractedSolution, model_bundle: ModelBundle, config: OptimizerConfig) -> None:
    assignments_by_session = {
        session.id_session: [assignment for assignment in solution.assignments if assignment.id_session == session.id_session]
        for session in solution.sessions
    }
    for session in solution.sessions:
        z_value = 1 if session.type_session == "TPC" else 0
        tpc_cc = sum(assignment.nombre_CC for assignment in assignments_by_session[session.id_session] if assignment.categorie == "TPC")
        expected_minimum = tpc_cc - config.parameters.Q * z_value
        if session.d_jm < expected_minimum:
            raise SolutionValidationError(
                f"d_jm incoherent pour {session.id_session}: {session.d_jm} < {expected_minimum}."
            )
        if session.type_session == "PC" and session.nombre_CC_TPC_dans_session_PC != tpc_cc:
            raise SolutionValidationError(
                f"Nombre de CC TPC incoherent dans la session PC {session.id_session}."
            )
        if session.type_session == "TPC" and session.nombre_CC_TPC_dans_session_PC != 0:
            raise SolutionValidationError(
                f"Une session TPC ne doit pas declarer de CC TPC dans session PC: {session.id_session}."
            )
        slot_key = (session.code_pivot, session.rang_m)
        if slot_key not in model_bundle.y:
            raise SolutionValidationError(f"Session inconnue du modele: {session.id_session}.")


def _validate_objective(
    solution: ExtractedSolution,
    model_bundle: ModelBundle,
    config: OptimizerConfig,
    tolerance: float,
) -> None:
    travel = sum(assignment.nombre_CC * assignment.temps_trajet_minutes for assignment in solution.assignments)
    eligibility = sum(
        model_bundle.derived.e_j_TPC[session.code_pivot]
        if session.type_session == "TPC"
        else model_bundle.derived.e_j_PC[session.code_pivot]
        for session in solution.sessions
    )
    mixing = sum(session.d_jm for session in solution.sessions)
    weights = config.parameters.objective_weights
    total = weights.w_t * travel + weights.w_e * eligibility + weights.w_m * mixing

    if solution.objective.Obj_trajet != travel:
        raise SolutionValidationError("Obj_trajet recalcule incoherent.")
    if solution.objective.Obj_eligibilite != eligibility:
        raise SolutionValidationError("Obj_eligibilite recalcule incoherent.")
    if solution.objective.Obj_mixite != mixing:
        raise SolutionValidationError("Obj_mixite recalcule incoherent.")
    if solution.objective.objectif_total != total:
        raise SolutionValidationError("Objectif total recalcule incoherent.")
    if solution.objective.solver_objective is not None and abs(solution.objective.solver_objective - total) > tolerance:
        raise SolutionValidationError(
            f"Objectif solveur incoherent: {solution.objective.solver_objective} != {total}."
        )
