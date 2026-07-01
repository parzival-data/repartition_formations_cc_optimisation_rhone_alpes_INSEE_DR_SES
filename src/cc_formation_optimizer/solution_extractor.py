"""Extraction d'une solution metier depuis le solveur CP-SAT."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from cc_formation_optimizer.config import OptimizerConfig
from cc_formation_optimizer.domain import Commune
from cc_formation_optimizer.model_builder import ModelBundle
from cc_formation_optimizer.solver import SolveResult


class SolutionExtractionError(ValueError):
    """Erreur levee lorsqu'une solution ne peut pas etre extraite.

    L'exception signale notamment un statut solveur sans solution exploitable
    ou une incoherence entre les variables et les communes chargees.
    """


@dataclass(frozen=True)
class OpenSession:
    """Session de formation ouverte extraite de la solution.

    Attributes
    ----------
    id_session : str
        Identifiant stable de session construit a partir du pivot et du rang.
    code_pivot : str
        Code de la commune pivot.
    nom_pivot : str
        Nom de la commune pivot.
    categorie_pivot : str
        Categorie initiale du pivot, ``PC`` ou ``TPC``.
    rang_m : int
        Rang du slot ouvert pour ce pivot.
    type_session : str
        Type de session decide par le modele, ``PC`` ou ``TPC``.
    nombre_communes : int
        Nombre de communes affectees a la session.
    nombre_CC : int
        Nombre total de CC affectes a la session.
    population_min : int
        Population minimale des communes affectees.
    population_max : int
        Population maximale des communes affectees.
    temps_trajet_max : int
        Temps de trajet maximal vers le pivot.
    temps_trajet_moyen : float
        Temps de trajet moyen vers le pivot.
    nombre_CC_TPC_dans_session_PC : int
        Nombre de CC TPC affectes a une session PC.
    d_jm : int
        Valeur de la variable de mixite residuelle.
    """

    id_session: str
    code_pivot: str
    nom_pivot: str
    categorie_pivot: str
    rang_m: int
    type_session: str
    nombre_communes: int
    nombre_CC: int
    population_min: int
    population_max: int
    temps_trajet_max: int
    temps_trajet_moyen: float
    nombre_CC_TPC_dans_session_PC: int
    d_jm: int


@dataclass(frozen=True)
class CommuneAssignment:
    """Affectation d'une commune a une session ouverte.

    Attributes
    ----------
    code_commune : str
        Code de la commune affectee.
    nom_commune : str
        Nom de la commune affectee.
    categorie : str
        Categorie de la commune, ``PC`` ou ``TPC``.
    territoire_EAR : str | None
        Territoire EAR de la commune, si disponible.
    population : int
        Population de la commune.
    logements : int | None
        Nombre de logements, si disponible.
    nombre_CC : int
        Nombre de CC associe a la commune.
    id_session : str
        Identifiant de la session cible.
    code_pivot : str
        Code du pivot de la session.
    nom_pivot : str
        Nom du pivot de la session.
    type_session : str
        Type de la session cible.
    temps_trajet_minutes : int
        Temps de trajet de la commune vers le pivot.
    """

    code_commune: str
    nom_commune: str
    categorie: str
    territoire_EAR: str | None
    population: int
    logements: int | None
    nombre_CC: int
    id_session: str
    code_pivot: str
    nom_pivot: str
    type_session: str
    temps_trajet_minutes: int


@dataclass(frozen=True)
class ObjectiveBreakdown:
    """Composantes d'objectif recalculees depuis la solution extraite.

    Attributes
    ----------
    Obj_trajet : int
        Composante trajet non ponderee.
    Obj_eligibilite : int
        Composante eligibilite non ponderee.
    Obj_mixite : int
        Composante mixite non ponderee.
    objectif_total : int
        Objectif total pondere avec les poids de configuration.
    solver_objective : float | None
        Objectif brut retourne par CP-SAT si disponible.
    """

    Obj_trajet: int
    Obj_eligibilite: int
    Obj_mixite: int
    objectif_total: int
    solver_objective: float | None


@dataclass(frozen=True)
class ExtractedSolution:
    """Solution metier structuree.

    Attributes
    ----------
    status : str
        Statut solveur ayant permis l'extraction.
    sessions : tuple[OpenSession, ...]
        Sessions ouvertes dans la solution extraite.
    assignments : tuple[CommuneAssignment, ...]
        Affectations de communes aux sessions ouvertes.
    objective : ObjectiveBreakdown
        Composantes d'objectif recalculees.
    """

    status: str
    sessions: tuple[OpenSession, ...]
    assignments: tuple[CommuneAssignment, ...]
    objective: ObjectiveBreakdown


def extract_solution(
    model_bundle: ModelBundle,
    solver_result: SolveResult,
    communes: list[Commune],
    config: OptimizerConfig,
) -> ExtractedSolution:
    """Extrait une solution metier si le solveur a trouve une solution.

    Parameters
    ----------
    model_bundle : ModelBundle
        Modele resolu et variables CP-SAT.
    solver_result : SolveResult
        Resultat de resolution contenant le solveur et le statut.
    communes : list[Commune]
        Communes chargees, utilisees pour enrichir la solution extraite.
    config : OptimizerConfig
        Configuration contenant les poids de l'objectif.

    Returns
    -------
    ExtractedSolution
        Sessions ouvertes, affectations et objectif recalcule.

    Raises
    ------
    SolutionExtractionError
        Si le statut solveur n'est ni ``OPTIMAL`` ni ``FEASIBLE`` ou si une
        commune referencee par une variable est absente des donnees chargees.
    """

    if solver_result.status not in {"OPTIMAL", "FEASIBLE"}:
        raise SolutionExtractionError(f"Impossible d'extraire une solution avec le statut {solver_result.status}.")

    commune_by_id = {commune.commune_id: commune for commune in communes}
    opened_slot_keys = tuple(
        slot_key for slot_key, variable in model_bundle.y.items() if solver_result.solver.Value(variable) == 1
    )

    assignments_by_slot = _extract_assignments_by_slot(model_bundle, solver_result, commune_by_id)
    sessions = tuple(
        _build_open_session(model_bundle, solver_result, commune_by_id, slot_key, assignments_by_slot[slot_key])
        for slot_key in opened_slot_keys
    )
    assignments = tuple(
        assignment
        for slot_key in opened_slot_keys
        for assignment in _build_commune_assignments(
            model_bundle,
            solver_result,
            commune_by_id,
            slot_key,
            assignments_by_slot[slot_key],
        )
    )
    objective = _recalculate_objective(model_bundle, solver_result, assignments, sessions, config)

    return ExtractedSolution(
        status=solver_result.status,
        sessions=sessions,
        assignments=assignments,
        objective=objective,
    )


def _session_id(pivot_id: str, slot_index: int) -> str:
    return f"{pivot_id}_{slot_index}"


def _extract_assignments_by_slot(
    model_bundle: ModelBundle,
    solver_result: SolveResult,
    commune_by_id: dict[str, Commune],
) -> dict[tuple[str, int], list[str]]:
    assignments_by_slot = {slot_key: [] for slot_key in model_bundle.y}
    for (commune_id, pivot_id, slot_index), variable in model_bundle.x.items():
        if solver_result.solver.Value(variable) == 1:
            if commune_id not in commune_by_id:
                raise SolutionExtractionError(f"Commune inconnue dans la solution: {commune_id}.")
            assignments_by_slot[(pivot_id, slot_index)].append(commune_id)
    return assignments_by_slot


def _build_open_session(
    model_bundle: ModelBundle,
    solver_result: SolveResult,
    commune_by_id: dict[str, Commune],
    slot_key: tuple[str, int],
    assigned_commune_ids: list[str],
) -> OpenSession:
    pivot_id, slot_index = slot_key
    pivot = commune_by_id[pivot_id]
    type_session = "TPC" if solver_result.solver.Value(model_bundle.z[slot_key]) == 1 else "PC"
    assigned_communes = [commune_by_id[commune_id] for commune_id in assigned_commune_ids]
    populations = [commune.population for commune in assigned_communes]
    travel_times = [model_bundle.derived.tau_ij[(commune.commune_id, pivot_id)] for commune in assigned_communes]
    tpc_cc_in_pc = 0
    if type_session == "PC":
        tpc_cc_in_pc = sum(
            model_bundle.derived.q_i[commune.commune_id]
            for commune in assigned_communes
            if commune.category == "TPC"
        )

    return OpenSession(
        id_session=_session_id(pivot_id, slot_index),
        code_pivot=pivot_id,
        nom_pivot=pivot.name,
        categorie_pivot=pivot.category,
        rang_m=slot_index,
        type_session=type_session,
        nombre_communes=len(assigned_communes),
        nombre_CC=sum(model_bundle.derived.q_i[commune.commune_id] for commune in assigned_communes),
        population_min=min(populations) if populations else 0,
        population_max=max(populations) if populations else 0,
        temps_trajet_max=max(travel_times) if travel_times else 0,
        temps_trajet_moyen=mean(travel_times) if travel_times else 0.0,
        nombre_CC_TPC_dans_session_PC=tpc_cc_in_pc,
        d_jm=solver_result.solver.Value(model_bundle.d[slot_key]),
    )


def _build_commune_assignments(
    model_bundle: ModelBundle,
    solver_result: SolveResult,
    commune_by_id: dict[str, Commune],
    slot_key: tuple[str, int],
    assigned_commune_ids: list[str],
) -> list[CommuneAssignment]:
    pivot_id, slot_index = slot_key
    pivot = commune_by_id[pivot_id]
    type_session = "TPC" if solver_result.solver.Value(model_bundle.z[slot_key]) == 1 else "PC"

    return [
        CommuneAssignment(
            code_commune=commune.commune_id,
            nom_commune=commune.name,
            categorie=commune.category,
            territoire_EAR=commune.territory_ear,
            population=commune.population,
            logements=commune.housing,
            nombre_CC=model_bundle.derived.q_i[commune.commune_id],
            id_session=_session_id(pivot_id, slot_index),
            code_pivot=pivot_id,
            nom_pivot=pivot.name,
            type_session=type_session,
            temps_trajet_minutes=model_bundle.derived.tau_ij[(commune.commune_id, pivot_id)],
        )
        for commune_id in assigned_commune_ids
        for commune in [commune_by_id[commune_id]]
    ]


def _recalculate_objective(
    model_bundle: ModelBundle,
    solver_result: SolveResult,
    assignments: tuple[CommuneAssignment, ...],
    sessions: tuple[OpenSession, ...],
    config: OptimizerConfig,
) -> ObjectiveBreakdown:
    travel = sum(assignment.nombre_CC * assignment.temps_trajet_minutes for assignment in assignments)
    eligibility = sum(
        model_bundle.derived.e_j_TPC[session.code_pivot]
        if session.type_session == "TPC"
        else model_bundle.derived.e_j_PC[session.code_pivot]
        for session in sessions
    )
    mixing = sum(session.d_jm for session in sessions)
    weights = config.parameters.objective_weights
    total = weights.w_t * travel + weights.w_e * eligibility + weights.w_m * mixing
    return ObjectiveBreakdown(
        Obj_trajet=travel,
        Obj_eligibilite=eligibility,
        Obj_mixite=mixing,
        objectif_total=total,
        solver_objective=solver_result.objective_value,
    )
