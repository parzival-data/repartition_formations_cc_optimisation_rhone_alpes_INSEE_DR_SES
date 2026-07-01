"""Orchestration de la surcouche metier post-optimisation."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from cc_formation_optimizer.config import OptimizerConfig

from cc_formation_optimizer.business_postprocess.io import default_output_dir, load_context, write_outputs
from cc_formation_optimizer.business_postprocess.rules import apply_business_rules
from cc_formation_optimizer.business_postprocess.stats import int_value
from cc_formation_optimizer.business_postprocess.types import PostprocessResult, RULE_NAMES


def postprocess_business_rules(
    input_dir: str | Path,
    config: OptimizerConfig,
    output_dir: str | Path | None = None,
    min_travel_time_gain_min: int = 5,
) -> PostprocessResult:
    """Analyse les exports existants et produit des propositions metier.

    Les exports d'origine sont uniquement lus. Les propositions sont ecrites
    dans un dossier separe afin de conserver la solution optimisee comme
    reference non modifiee.

    Parameters
    ----------
    input_dir : str | Path
        Racine contenant les exports ``solutions/``.
    config : OptimizerConfig
        Configuration de reference pour les contraintes et trajets.
    output_dir : str | Path | None, default=None
        Dossier cible des CSV de propositions.
    min_travel_time_gain_min : int, default=5
        Gain minimal en minutes pour proposer un rattachement alternatif.

    Returns
    -------
    PostprocessResult
        Chemins et compteurs des CSV produits.
    """

    context = load_context(
        input_dir=input_dir,
        config=config,
        min_travel_time_gain_min=min_travel_time_gain_min,
    )
    proposals = apply_business_rules(context)
    apply_conflict_hints(proposals)
    summary = build_summary(proposals)
    return write_outputs(output_dir or default_output_dir(input_dir), proposals, summary)


def build_summary(proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Construit la synthese par regle metier.

    Parameters
    ----------
    proposals : list[dict[str, Any]]
        Propositions produites par les regles metier.

    Returns
    -------
    list[dict[str, Any]]
        Lignes de synthese par regle.
    """

    rows: list[dict[str, Any]] = []
    for rule_id in sorted(RULE_NAMES):
        rule_rows = [row for row in proposals if row["rule_id"] == rule_id]
        sessions = {
            value
            for row in rule_rows
            for value in (row.get("current_session_id"), row.get("proposed_session_id"))
            if value
        }
        communes = {row.get("commune_code") for row in rule_rows if row.get("commune_code")}
        rows.append(
            {
                "rule_id": rule_id,
                "rule_name": RULE_NAMES[rule_id],
                "proposal_count": len(rule_rows),
                "sessions_concerned": len(sessions),
                "communes_concerned": len(communes),
                "total_travel_time_gain_min": sum(int_value(row, "travel_time_gain_min") for row in rule_rows),
                "constraints_respected_count": sum(
                    1 for row in rule_rows if row["model_constraints_respected"] == "true"
                ),
                "constraints_violated_count": sum(
                    1 for row in rule_rows if row["model_constraints_respected"] != "true"
                ),
            }
        )
    return rows


def apply_conflict_hints(proposals: list[dict[str, Any]]) -> None:
    """Ajoute une alerte si une commune ou une session apparait plusieurs fois.

    Parameters
    ----------
    proposals : list[dict[str, Any]]
        Propositions modifiees en place avec une indication d'arbitrage.
    """

    commune_counts = Counter(row.get("commune_code") for row in proposals if row.get("commune_code"))
    session_counts = Counter(
        value
        for row in proposals
        for value in (row.get("current_session_id"), row.get("proposed_session_id"))
        if value
    )
    for row in proposals:
        hints: list[str] = []
        commune_code = row.get("commune_code")
        if commune_code and commune_counts[commune_code] > 1:
            hints.append("Cette commune apparait dans plusieurs propositions; arbitrage metier necessaire.")
        sessions = [row.get("current_session_id"), row.get("proposed_session_id")]
        if any(session and session_counts[session] > 1 for session in sessions):
            hints.append("Cette session apparait dans plusieurs propositions; arbitrage metier necessaire.")
        row["conflict_hint"] = " ".join(hints)
