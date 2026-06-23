"""Construction des parametres derives du modele."""

from __future__ import annotations

from cc_formation_optimizer.config import OptimizerConfig
from cc_formation_optimizer.domain import Commune, FormationSlot


def cc_count_for_population(population: int, config: OptimizerConfig) -> int:
    """Retourne `q_i` selon la regle configuree."""

    rule = config.parameters.cc_count
    if population <= rule.threshold_population:
        return rule.below_or_equal
    return rule.above


def slots_for_commune(commune: Commune, config: OptimizerConfig) -> list[FormationSlot]:
    """Construit les slots potentiels d'une commune pivot."""

    slots = config.parameters.pivot_slots
    if commune.category == "PC":
        max_slots = slots.M_PC
    elif commune.category == "TPC":
        max_slots = slots.M_TPC
    else:
        raise ValueError(f"Categorie de commune inconnue: {commune.category}")
    return [FormationSlot(commune.commune_id, index) for index in range(1, max_slots + 1)]
