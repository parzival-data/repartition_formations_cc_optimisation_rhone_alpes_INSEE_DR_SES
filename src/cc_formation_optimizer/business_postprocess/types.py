"""Types et constantes de la surcouche metier post-optimisation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cc_formation_optimizer.config import OptimizerConfig


class PostprocessError(ValueError):
    """Erreur empechant le post-traitement metier des exports.

    Cette exception signale des exports absents, incomplets ou incoherents
    pour appliquer les regles metier.
    """


@dataclass(frozen=True)
class PostprocessResult:
    """Chemins et compteurs produits par le post-traitement metier.

    Attributes
    ----------
    proposals_csv : Path
        CSV des propositions metier.
    summary_csv : Path
        CSV de synthese par regle.
    proposal_count : int
        Nombre de propositions produites.
    summary_count : int
        Nombre de lignes de synthese produites.
    """

    proposals_csv: Path
    summary_csv: Path
    proposal_count: int
    summary_count: int


@dataclass(frozen=True)
class BusinessPostprocessContext:
    """Donnees chargees depuis les exports et la configuration.

    Attributes
    ----------
    sessions : dict[str, dict[str, Any]]
        Sessions exportees, indexees par identifiant.
    assignments : list[dict[str, Any]]
        Communes affectees lues depuis les exports.
    assignments_by_session : dict[str, list[dict[str, Any]]]
        Affectations regroupees par session.
    assignment_by_commune : dict[str, dict[str, Any]]
        Affectation unique de chaque commune.
    travel_times : dict[tuple[str, str], int]
        Temps de trajet propres disponibles.
    compatibilities : dict[tuple[str, str], int]
        Compatibilites explicites.
    config : OptimizerConfig
        Configuration de reference.
    min_travel_time_gain_min : int
        Gain minimal exige pour proposer un changement de pivot.
    """

    sessions: dict[str, dict[str, Any]]
    assignments: list[dict[str, Any]]
    assignments_by_session: dict[str, list[dict[str, Any]]]
    assignment_by_commune: dict[str, dict[str, Any]]
    travel_times: dict[tuple[str, str], int]
    compatibilities: dict[tuple[str, str], int]
    config: OptimizerConfig
    min_travel_time_gain_min: int


@dataclass(frozen=True)
class SessionStats:
    """Statistiques recalculees pour une session avant ou apres proposition.

    Attributes
    ----------
    commune_count : int
        Nombre de communes dans la session.
    cc : int
        Nombre total de CC dans la session.
    max_travel : int
        Temps de trajet maximal.
    mean_travel : float
        Temps de trajet moyen.
    total_travel : int
        Somme des temps de trajet non ponderes.
    """

    commune_count: int
    cc: int
    max_travel: int
    mean_travel: float
    total_travel: int


PROPOSAL_COLUMNS = [
    "rule_id",
    "rule_name",
    "proposal_id",
    "proposal_scope",
    "current_session_id",
    "current_session_type",
    "current_pivot_code",
    "current_pivot_name",
    "commune_code",
    "commune_name",
    "proposed_session_id",
    "proposed_pivot_code",
    "proposed_pivot_name",
    "current_travel_time_min",
    "proposed_travel_time_min",
    "travel_time_gain_min",
    "current_session_cc_before",
    "current_session_cc_after",
    "proposed_session_cc_before",
    "proposed_session_cc_after",
    "current_session_max_travel_time_before",
    "current_session_max_travel_time_after",
    "proposed_session_max_travel_time_before",
    "proposed_session_max_travel_time_after",
    "current_session_total_travel_time_before",
    "current_session_total_travel_time_after",
    "proposed_session_total_travel_time_before",
    "proposed_session_total_travel_time_after",
    "model_constraints_respected",
    "warning",
    "conflict_hint",
    "comment",
]

SUMMARY_COLUMNS = [
    "rule_id",
    "rule_name",
    "proposal_count",
    "sessions_concerned",
    "communes_concerned",
    "total_travel_time_gain_min",
    "constraints_respected_count",
    "constraints_violated_count",
]

RULE_NAMES = {
    "R1": "Pivot interne pour formation TPC",
    "R2": "Rattacher une commune pivot a sa propre formation",
    "R3": "Commune plus proche d'un autre pivot de meme type",
}
