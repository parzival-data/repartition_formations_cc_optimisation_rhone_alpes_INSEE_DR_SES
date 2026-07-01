"""Regles metier appliquees aux exports d'optimisation."""

from __future__ import annotations

from typing import Any

from cc_formation_optimizer.business_postprocess.stats import (
    constraint_warnings_for_pivot,
    constraint_warnings_for_reassignment,
    int_value,
    lower_fill_warnings,
    session_stats,
    synthetic_assignment_for_pivot,
    travel_time,
)
from cc_formation_optimizer.business_postprocess.types import (
    BusinessPostprocessContext,
    PROPOSAL_COLUMNS,
    RULE_NAMES,
)


def apply_business_rules(context: BusinessPostprocessContext) -> list[dict[str, Any]]:
    """Applique les trois regles de proposition metier.

    Parameters
    ----------
    context : BusinessPostprocessContext
        Exports et donnees de reference charges.

    Returns
    -------
    list[dict[str, Any]]
        Propositions metier produites par les regles R1, R2 et R3.
    """

    proposals: list[dict[str, Any]] = []
    proposals.extend(rule_internal_tpc_pivot(context))
    proposals.extend(rule_reassign_pivot_to_own_session(context))
    proposals.extend(rule_closer_same_type_pivot(context))
    return proposals


def rule_internal_tpc_pivot(context: BusinessPostprocessContext) -> list[dict[str, Any]]:
    """R1: proposer un pivot interne pour une session TPC a pivot externe.

    Parameters
    ----------
    context : BusinessPostprocessContext
        Contexte de post-traitement charge depuis les exports.

    Returns
    -------
    list[dict[str, Any]]
        Propositions de changement de pivot sans modifier les affectations.
    """

    proposals: list[dict[str, Any]] = []
    for session in context.sessions.values():
        if str(session.get("type_session", "")).upper() != "TPC":
            continue

        session_id = str(session["id_session"])
        pivot_code = str(session["code_pivot"])
        assignments = context.assignments_by_session.get(session_id, [])
        if not assignments or pivot_code in {str(row["code_commune"]) for row in assignments}:
            continue

        candidates: list[tuple[int, int, int, str, dict[str, Any]]] = []
        for candidate in assignments:
            candidate_code = str(candidate["code_commune"])
            times = [travel_time(context, str(row["code_commune"]), candidate_code) for row in assignments]
            if any(value is None for value in times):
                continue
            known_times = [int(value) for value in times if value is not None]
            population = int_value(candidate, "population")
            candidates.append((sum(known_times), max(known_times), -population, candidate_code, candidate))

        if not candidates:
            continue

        total_after, max_after, _population_sort, proposed_code, proposed = min(candidates)
        before_stats = session_stats(assignments)
        current_total = before_stats.total_travel
        current_max = before_stats.max_travel
        warnings = constraint_warnings_for_pivot(context, assignments, proposed_code, "TPC")
        proposal_id = proposal_id_for("R1", len(proposals) + 1)
        proposals.append(
            proposal_row(
                rule_id="R1",
                proposal_id=proposal_id,
                proposal_scope="pivot_change_only",
                current_session_id=session_id,
                current_session_type="TPC",
                current_pivot_code=pivot_code,
                current_pivot_name=session.get("nom_pivot", ""),
                proposed_session_id=session_id,
                proposed_pivot_code=proposed_code,
                proposed_pivot_name=proposed.get("nom_commune", ""),
                current_travel_time_min=current_total,
                proposed_travel_time_min=total_after,
                travel_time_gain_min=current_total - total_after,
                current_session_cc_before=before_stats.cc,
                current_session_cc_after=before_stats.cc,
                proposed_session_cc_before=before_stats.cc,
                proposed_session_cc_after=before_stats.cc,
                current_session_max_travel_time_before=current_max,
                current_session_max_travel_time_after=current_max,
                proposed_session_max_travel_time_before=current_max,
                proposed_session_max_travel_time_after=max_after,
                current_session_total_travel_time_before=current_total,
                current_session_total_travel_time_after=current_total,
                proposed_session_total_travel_time_before=current_total,
                proposed_session_total_travel_time_after=total_after,
                model_constraints_respected=not warnings,
                warning="; ".join(warnings),
                comment=(
                    "La session TPC a un pivot externe a la formation. Un pivot interne est propose "
                    "afin de rendre la formation plus lisible pour les communes participantes."
                ),
            )
        )
    return proposals


def rule_reassign_pivot_to_own_session(context: BusinessPostprocessContext) -> list[dict[str, Any]]:
    """R2: proposer de rattacher une commune pivot a sa propre session.

    Parameters
    ----------
    context : BusinessPostprocessContext
        Contexte de post-traitement charge depuis les exports.

    Returns
    -------
    list[dict[str, Any]]
        Propositions de reaffectation de pivots vers leur propre session.
    """

    proposals: list[dict[str, Any]] = []
    for target_session in context.sessions.values():
        target_session_id = str(target_session["id_session"])
        pivot_code = str(target_session["code_pivot"])
        target_assignments = context.assignments_by_session.get(target_session_id, [])

        if pivot_code in {str(row["code_commune"]) for row in target_assignments}:
            continue

        pivot_assignment = context.assignment_by_commune.get(pivot_code)
        if pivot_assignment is not None and str(pivot_assignment.get("code_pivot", "")) == pivot_code:
            continue

        source_session_id = str(pivot_assignment.get("id_session", "")) if pivot_assignment else ""
        source_session = context.sessions.get(source_session_id, {})
        source_assignments = context.assignments_by_session.get(source_session_id, [])
        source_after = [row for row in source_assignments if str(row.get("code_commune", "")) != pivot_code]

        synthetic_assignment = synthetic_assignment_for_pivot(target_session, pivot_assignment)
        target_after = [*target_assignments, synthetic_assignment] if synthetic_assignment is not None else target_assignments

        source_before_stats = session_stats(source_assignments)
        source_after_stats = session_stats(source_after)
        target_before_stats = session_stats(target_assignments)
        target_after_stats = session_stats(target_after)

        warnings = []
        if pivot_assignment is None:
            warnings.append("commune pivot absente des affectations exportees")
        else:
            warnings.extend(constraint_warnings_for_reassignment(context, pivot_assignment, target_session, target_after))
            if source_session_id:
                warnings.extend(lower_fill_warnings(context, source_session_id, source_after_stats))

        proposal_id = proposal_id_for("R2", len(proposals) + 1)
        proposals.append(
            proposal_row(
                rule_id="R2",
                proposal_id=proposal_id,
                proposal_scope="commune_reassignment",
                current_session_id=source_session_id,
                current_session_type=source_session.get("type_session", ""),
                current_pivot_code=source_session.get("code_pivot", ""),
                current_pivot_name=source_session.get("nom_pivot", ""),
                commune_code=pivot_code,
                commune_name=target_session.get("nom_pivot", ""),
                proposed_session_id=target_session_id,
                proposed_pivot_code=pivot_code,
                proposed_pivot_name=target_session.get("nom_pivot", ""),
                current_travel_time_min=pivot_assignment.get("temps_trajet_minutes", "") if pivot_assignment else "",
                proposed_travel_time_min=0 if pivot_assignment else "",
                travel_time_gain_min=int_value(pivot_assignment, "temps_trajet_minutes") if pivot_assignment else "",
                current_session_cc_before=source_before_stats.cc,
                current_session_cc_after=source_after_stats.cc,
                proposed_session_cc_before=target_before_stats.cc,
                proposed_session_cc_after=target_after_stats.cc,
                current_session_max_travel_time_before=source_before_stats.max_travel,
                current_session_max_travel_time_after=source_after_stats.max_travel,
                proposed_session_max_travel_time_before=target_before_stats.max_travel,
                proposed_session_max_travel_time_after=target_after_stats.max_travel,
                current_session_total_travel_time_before=source_before_stats.total_travel,
                current_session_total_travel_time_after=source_after_stats.total_travel,
                proposed_session_total_travel_time_before=target_before_stats.total_travel,
                proposed_session_total_travel_time_after=target_after_stats.total_travel,
                model_constraints_respected=not warnings,
                warning="; ".join(warnings),
                comment=(
                    "La commune pivot ne participe pas a sa propre session et n'est pas affectee a une autre "
                    "session ou elle serait pivot. Une reaffectation vers sa propre session est proposee pour "
                    "ameliorer la lisibilite metier, meme si elle peut depasser certaines limites du modele."
                ),
            )
        )
    return proposals


def rule_closer_same_type_pivot(context: BusinessPostprocessContext) -> list[dict[str, Any]]:
    """R3: proposer une session de meme type avec un pivot plus proche.

    Parameters
    ----------
    context : BusinessPostprocessContext
        Contexte de post-traitement charge depuis les exports.

    Returns
    -------
    list[dict[str, Any]]
        Propositions de rattachement vers un pivot plus proche de meme type.
    """

    proposals: list[dict[str, Any]] = []
    for assignment in context.assignments:
        current_session_id = str(assignment["id_session"])
        current_session = context.sessions.get(current_session_id)
        if current_session is None:
            continue

        commune_code = str(assignment["code_commune"])
        current_time = int_value(assignment, "temps_trajet_minutes")
        current_type = str(current_session.get("type_session", "")).upper()
        best: tuple[int, str, dict[str, Any]] | None = None

        for candidate_session in context.sessions.values():
            candidate_session_id = str(candidate_session["id_session"])
            if candidate_session_id == current_session_id:
                continue
            if str(candidate_session.get("type_session", "")).upper() != current_type:
                continue
            candidate_pivot = str(candidate_session["code_pivot"])
            proposed_time = travel_time(context, commune_code, candidate_pivot)
            if proposed_time is None or proposed_time >= current_time:
                continue
            if best is None or (proposed_time, candidate_session_id) < (best[0], best[1]):
                best = (proposed_time, candidate_session_id, candidate_session)

        if best is None:
            continue

        proposed_time, proposed_session_id, proposed_session = best
        gain = current_time - proposed_time
        if gain < context.min_travel_time_gain_min:
            continue

        source_assignments = context.assignments_by_session.get(current_session_id, [])
        target_assignments = context.assignments_by_session.get(proposed_session_id, [])
        source_after = [row for row in source_assignments if str(row.get("code_commune", "")) != commune_code]
        moved_assignment = dict(assignment)
        moved_assignment["id_session"] = proposed_session_id
        moved_assignment["code_pivot"] = proposed_session["code_pivot"]
        moved_assignment["nom_pivot"] = proposed_session["nom_pivot"]
        moved_assignment["type_session"] = proposed_session["type_session"]
        moved_assignment["temps_trajet_minutes"] = proposed_time
        target_after = [*target_assignments, moved_assignment]

        source_before_stats = session_stats(source_assignments)
        source_after_stats = session_stats(source_after)
        target_before_stats = session_stats(target_assignments)
        target_after_stats = session_stats(target_after)
        warnings = constraint_warnings_for_reassignment(context, assignment, proposed_session, target_after)
        warnings.extend(lower_fill_warnings(context, current_session_id, source_after_stats))

        proposal_id = proposal_id_for("R3", len(proposals) + 1)
        proposals.append(
            proposal_row(
                rule_id="R3",
                proposal_id=proposal_id,
                proposal_scope="commune_reassignment",
                current_session_id=current_session_id,
                current_session_type=current_type,
                current_pivot_code=current_session.get("code_pivot", ""),
                current_pivot_name=current_session.get("nom_pivot", ""),
                commune_code=commune_code,
                commune_name=assignment.get("nom_commune", ""),
                proposed_session_id=proposed_session_id,
                proposed_pivot_code=proposed_session.get("code_pivot", ""),
                proposed_pivot_name=proposed_session.get("nom_pivot", ""),
                current_travel_time_min=current_time,
                proposed_travel_time_min=proposed_time,
                travel_time_gain_min=gain,
                current_session_cc_before=source_before_stats.cc,
                current_session_cc_after=source_after_stats.cc,
                proposed_session_cc_before=target_before_stats.cc,
                proposed_session_cc_after=target_after_stats.cc,
                current_session_max_travel_time_before=source_before_stats.max_travel,
                current_session_max_travel_time_after=source_after_stats.max_travel,
                proposed_session_max_travel_time_before=target_before_stats.max_travel,
                proposed_session_max_travel_time_after=target_after_stats.max_travel,
                current_session_total_travel_time_before=source_before_stats.total_travel,
                current_session_total_travel_time_after=source_after_stats.total_travel,
                proposed_session_total_travel_time_before=target_before_stats.total_travel,
                proposed_session_total_travel_time_after=target_after_stats.total_travel,
                model_constraints_respected=not warnings,
                warning="; ".join(warnings),
                comment=(
                    "La commune est plus proche d'un autre pivot de meme type de formation. Le changement "
                    "propose reduit le temps de trajet, sous reserve de validation de la capacite et de la "
                    "coherence metier."
                ),
            )
        )
    return proposals


def proposal_row(**values: Any) -> dict[str, Any]:
    """Construit une ligne de proposition avec toutes les colonnes attendues.

    Parameters
    ----------
    **values : Any
        Valeurs a renseigner dans la ligne de proposition.

    Returns
    -------
    dict[str, Any]
        Ligne complete respectant l'ordre des colonnes d'export.
    """

    row = {column: "" for column in PROPOSAL_COLUMNS}
    row.update(values)
    row["rule_name"] = RULE_NAMES[str(row["rule_id"])]
    row["model_constraints_respected"] = "true" if bool(row["model_constraints_respected"]) else "false"
    return row


def proposal_id_for(rule_id: str, index: int) -> str:
    """Construit un identifiant stable au sein d'une regle.

    Parameters
    ----------
    rule_id : str
        Identifiant de regle, par exemple ``R1``.
    index : int
        Rang de la proposition dans la regle.

    Returns
    -------
    str
        Identifiant de proposition stable.
    """

    return f"{rule_id}-{index:04d}"
