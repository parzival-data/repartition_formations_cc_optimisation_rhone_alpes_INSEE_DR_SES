"""Diagnostics pre-resolution."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from cc_formation_optimizer.config import OptimizerConfig
from cc_formation_optimizer.parameters import DerivedParameters


@dataclass(frozen=True)
class PreSolveDiagnostic:
    """Synthese du diagnostic structurel avant resolution."""

    total_communes: int
    pc_count: int
    tpc_count: int
    total_cc: int
    min_required_formations: int
    slot_count: int
    admissible_travel_count: int
    orphan_communes: tuple[str, ...]
    pc_without_pc_pivot: tuple[str, ...]
    budget_warning: str | None


def run_pre_solve_diagnostics(derived: DerivedParameters, config: OptimizerConfig) -> PreSolveDiagnostic:
    """Execute les diagnostics structurels avant resolution."""

    total_cc = sum(derived.q_i.values())
    min_required_formations = ceil(total_cc / config.parameters.Q)
    budgets = config.parameters.formation_budgets

    orphan_communes = tuple(
        commune_id
        for commune_id in derived.C
        if not any(_is_reachable(derived, commune_id, pivot_id) for pivot_id in derived.F)
    )

    pc_without_pc_pivot = tuple(
        commune_id
        for commune_id in derived.P
        if not any(
            _is_reachable(derived, commune_id, pivot_id)
            and derived.e_j_PC[pivot_id] < config.parameters.eligibility_costs.infinity
            for pivot_id in derived.F
        )
    )

    budget_warning = None
    if budgets.B < min_required_formations:
        budget_warning = (
            f"B={budgets.B} est inferieur a ceil(total_CC / Q)={min_required_formations}; "
            "le probleme est structurellement infaisable avec cette capacite."
        )

    return PreSolveDiagnostic(
        total_communes=len(derived.C),
        pc_count=len(derived.P),
        tpc_count=len(derived.T),
        total_cc=total_cc,
        min_required_formations=min_required_formations,
        slot_count=len(derived.S),
        admissible_travel_count=sum(derived.a_ij.values()),
        orphan_communes=orphan_communes,
        pc_without_pc_pivot=pc_without_pc_pivot,
        budget_warning=budget_warning,
    )


def _is_reachable(derived: DerivedParameters, commune_id: str, pivot_id: str) -> bool:
    return derived.a_ij[(commune_id, pivot_id)] == 1 and derived.b_ij[(commune_id, pivot_id)] == 1
