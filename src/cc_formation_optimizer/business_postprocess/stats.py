"""Calculs de statistiques et controles indicatifs des contraintes."""

from __future__ import annotations

from statistics import mean
from typing import Any

from cc_formation_optimizer.business_postprocess.types import BusinessPostprocessContext, SessionStats


def session_stats(assignments: list[dict[str, Any]]) -> SessionStats:
    """Recalcule charge, temps maximal, temps moyen et temps total."""

    travel_times = [int_value(row, "temps_trajet_minutes") for row in assignments]
    return SessionStats(
        commune_count=len(assignments),
        cc=sum(int_value(row, "nombre_CC") for row in assignments),
        max_travel=max(travel_times) if travel_times else 0,
        mean_travel=round(mean(travel_times), 2) if travel_times else 0.0,
        total_travel=sum(travel_times),
    )


def constraint_warnings_for_pivot(
    context: BusinessPostprocessContext,
    assignments: list[dict[str, Any]],
    pivot_code: str,
    session_type: str,
) -> list[str]:
    """Controle les contraintes detectables si le pivot d'une session change."""

    warnings: list[str] = []
    for assignment in assignments:
        commune_code = str(assignment["code_commune"])
        time = travel_time(context, commune_code, pivot_code)
        if time is None:
            warnings.append(f"temps de trajet manquant: {commune_code}->{pivot_code}")
        elif time > context.config.parameters.T:
            warnings.append(f"temps de trajet superieur a T pour {commune_code}->{pivot_code}")
        if compatibility(context, commune_code, pivot_code) == 0:
            warnings.append(f"compatibilite interdite: {commune_code}->{pivot_code}")
        if str(assignment.get("categorie", "")).upper() == "PC" and session_type == "TPC":
            warnings.append("commune PC dans une session TPC")
    return sorted(set(warnings))


def constraint_warnings_for_reassignment(
    context: BusinessPostprocessContext,
    assignment: dict[str, Any],
    target_session: dict[str, Any],
    target_after: list[dict[str, Any]],
) -> list[str]:
    """Controle les contraintes detectables si une commune change de session."""

    warnings: list[str] = []
    target_stats = session_stats(target_after)
    commune_code = str(assignment["code_commune"])
    target_pivot = str(target_session["code_pivot"])
    target_type = str(target_session.get("type_session", "")).upper()
    category = str(assignment.get("categorie", "")).upper()

    if target_stats.cc > context.config.parameters.Q:
        warnings.append(f"capacite depassee: {target_stats.cc}>{context.config.parameters.Q}")
    if target_stats.cc < context.config.parameters.L:
        warnings.append(f"session cible sous le minimum L: {target_stats.cc}<{context.config.parameters.L}")
    proposed_time = travel_time(context, commune_code, target_pivot)
    if proposed_time is None:
        warnings.append(f"temps de trajet manquant: {commune_code}->{target_pivot}")
    elif proposed_time > context.config.parameters.T:
        warnings.append(f"temps de trajet superieur a T: {proposed_time}>{context.config.parameters.T}")
    if compatibility(context, commune_code, target_pivot) == 0:
        warnings.append(f"compatibilite interdite: {commune_code}->{target_pivot}")
    if category == "PC" and target_type == "TPC":
        warnings.append("commune PC dans une session TPC")
    return sorted(set(warnings))


def lower_fill_warnings(
    context: BusinessPostprocessContext,
    session_id: str,
    stats_after: SessionStats,
) -> list[str]:
    """Signale si une session source passe sous le minimum L apres retrait."""

    if not session_id:
        return []
    if stats_after.cc < context.config.parameters.L:
        return [f"session source sous le minimum L apres retrait: {stats_after.cc}<{context.config.parameters.L}"]
    return []


def synthetic_assignment_for_pivot(
    target_session: dict[str, Any],
    pivot_assignment: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Construit une affectation simulee du pivot vers sa propre session."""

    if pivot_assignment is None:
        return None
    row = dict(pivot_assignment)
    row["id_session"] = target_session["id_session"]
    row["code_pivot"] = target_session["code_pivot"]
    row["nom_pivot"] = target_session["nom_pivot"]
    row["type_session"] = target_session["type_session"]
    row["temps_trajet_minutes"] = 0
    row["is_pivot"] = "True"
    row["is_same_territory_as_pivot"] = "True"
    return row


def travel_time(context: BusinessPostprocessContext, commune_code: str, pivot_code: str) -> int | None:
    """Retourne le temps de trajet connu, avec diagonale nulle."""

    if commune_code == pivot_code:
        return 0
    return context.travel_times.get((commune_code, pivot_code))


def compatibility(context: BusinessPostprocessContext, commune_code: str, pivot_code: str) -> int:
    """Retourne la compatibilite orientee, autorisee par defaut."""

    return context.compatibilities.get((commune_code, pivot_code), 1)


def int_value(row: dict[str, Any] | None, key: str) -> int:
    """Convertit une valeur CSV numerique en entier tolerant."""

    if row is None:
        return 0
    value = row.get(key, 0)
    if value in ("", None):
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0
