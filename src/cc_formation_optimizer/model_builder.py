"""Construction du modele OR-Tools CP-SAT."""

from __future__ import annotations

from dataclasses import dataclass

from ortools.sat.python import cp_model

from cc_formation_optimizer.config import OptimizerConfig
from cc_formation_optimizer.domain import FormationSlot
from cc_formation_optimizer.parameters import DerivedParameters


SlotKey = tuple[str, int]
AssignmentKey = tuple[str, str, int]


@dataclass(frozen=True)
class ModelBundle:
    """Modele CP-SAT et variables utiles a l'extraction de solution."""

    model: cp_model.CpModel
    x: dict[AssignmentKey, cp_model.IntVar]
    y: dict[SlotKey, cp_model.IntVar]
    z: dict[SlotKey, cp_model.IntVar]
    d: dict[SlotKey, cp_model.IntVar]
    derived: DerivedParameters
    slots: tuple[FormationSlot, ...]
    objective_terms: dict[str, cp_model.LinearExpr]


def build_model(derived: DerivedParameters, config: OptimizerConfig) -> ModelBundle:
    """Construit la formulation CP-SAT complete du modele documente."""

    model = cp_model.CpModel()
    slot_keys = tuple((slot.pivot_id, slot.slot_index) for slot in derived.S)

    y = {slot_key: model.NewBoolVar(f"y[{slot_key[0]},{slot_key[1]}]") for slot_key in slot_keys}
    z = {slot_key: model.NewBoolVar(f"z[{slot_key[0]},{slot_key[1]}]") for slot_key in slot_keys}
    d = {slot_key: model.NewIntVar(0, config.parameters.Q, f"d[{slot_key[0]},{slot_key[1]}]") for slot_key in slot_keys}
    x = _create_assignment_variables(model, derived)

    _add_unique_assignment_constraints(model, derived, x)
    _add_opening_constraints(model, x, y)
    _add_capacity_constraints(model, derived, config, x, y, slot_keys)
    _add_z_y_consistency_constraints(model, y, z)
    _add_budget_constraints(model, config, y, z, slot_keys)
    _add_pc_pivot_order_constraints(model, derived, y)
    _add_pc_to_tpc_asymmetry_constraints(model, derived, x, z)
    _add_mixing_constraints(model, derived, config, x, z, d, slot_keys)

    objective_terms = _build_objective_terms(derived, config, x, y, z, d, slot_keys)
    model.Minimize(
        config.parameters.objective_weights.w_t * objective_terms["travel"]
        + config.parameters.objective_weights.w_e * objective_terms["eligibility"]
        + config.parameters.objective_weights.w_m * objective_terms["mixing"]
    )

    return ModelBundle(
        model=model,
        x=x,
        y=y,
        z=z,
        d=d,
        derived=derived,
        slots=derived.S,
        objective_terms=objective_terms,
    )


def _create_assignment_variables(
    model: cp_model.CpModel,
    derived: DerivedParameters,
) -> dict[AssignmentKey, cp_model.IntVar]:
    x: dict[AssignmentKey, cp_model.IntVar] = {}
    for commune_id in derived.C:
        for slot in derived.S:
            pivot_id = slot.pivot_id
            if derived.a_ij[(commune_id, pivot_id)] == 1 and derived.b_ij[(commune_id, pivot_id)] == 1:
                key = (commune_id, pivot_id, slot.slot_index)
                x[key] = model.NewBoolVar(f"x[{commune_id},{pivot_id},{slot.slot_index}]")
    return x


def _add_unique_assignment_constraints(
    model: cp_model.CpModel,
    derived: DerivedParameters,
    x: dict[AssignmentKey, cp_model.IntVar],
) -> None:
    # (1) Chaque commune est affectee exactement une fois.
    for commune_id in derived.C:
        model.Add(sum(var for (i, _, _), var in x.items() if i == commune_id) == 1)


def _add_opening_constraints(
    model: cp_model.CpModel,
    x: dict[AssignmentKey, cp_model.IntVar],
    y: dict[SlotKey, cp_model.IntVar],
) -> None:
    # (2) Pas d'affectation sans ouverture.
    for (_, pivot_id, slot_index), variable in x.items():
        model.Add(variable <= y[(pivot_id, slot_index)])


def _add_capacity_constraints(
    model: cp_model.CpModel,
    derived: DerivedParameters,
    config: OptimizerConfig,
    x: dict[AssignmentKey, cp_model.IntVar],
    y: dict[SlotKey, cp_model.IntVar],
    slot_keys: tuple[SlotKey, ...],
) -> None:
    # (4) Capacite maximale et remplissage minimal.
    for pivot_id, slot_index in slot_keys:
        load = sum(
            derived.q_i[commune_id] * variable
            for (commune_id, j, m), variable in x.items()
            if j == pivot_id and m == slot_index
        )
        model.Add(load >= config.parameters.L * y[(pivot_id, slot_index)])
        model.Add(load <= config.parameters.Q * y[(pivot_id, slot_index)])


def _add_z_y_consistency_constraints(
    model: cp_model.CpModel,
    y: dict[SlotKey, cp_model.IntVar],
    z: dict[SlotKey, cp_model.IntVar],
) -> None:
    # (5) z_jm n'a de sens que si la formation est ouverte.
    for slot_key in y:
        model.Add(z[slot_key] <= y[slot_key])


def _add_budget_constraints(
    model: cp_model.CpModel,
    config: OptimizerConfig,
    y: dict[SlotKey, cp_model.IntVar],
    z: dict[SlotKey, cp_model.IntVar],
    slot_keys: tuple[SlotKey, ...],
) -> None:
    # (6) Budgets linearises : PC = y_jm - z_jm, TPC = z_jm.
    budgets = config.parameters.formation_budgets
    model.Add(sum(y[slot_key] - z[slot_key] for slot_key in slot_keys) <= budgets.f)
    model.Add(sum(z[slot_key] for slot_key in slot_keys) <= budgets.k)


def _add_pc_pivot_order_constraints(
    model: cp_model.CpModel,
    derived: DerivedParameters,
    y: dict[SlotKey, cp_model.IntVar],
) -> None:
    # (7) Ordre d'ouverture uniquement pour les pivots PC.
    for pivot_id in derived.P:
        for slot_index in range(1, derived.M_j[pivot_id]):
            model.Add(y[(pivot_id, slot_index + 1)] <= y[(pivot_id, slot_index)])


def _add_pc_to_tpc_asymmetry_constraints(
    model: cp_model.CpModel,
    derived: DerivedParameters,
    x: dict[AssignmentKey, cp_model.IntVar],
    z: dict[SlotKey, cp_model.IntVar],
) -> None:
    # (8) Une commune PC ne peut jamais etre affectee a une formation TPC.
    for (commune_id, pivot_id, slot_index), variable in x.items():
        if commune_id in derived.P:
            model.Add(variable <= 1 - z[(pivot_id, slot_index)])


def _add_mixing_constraints(
    model: cp_model.CpModel,
    derived: DerivedParameters,
    config: OptimizerConfig,
    x: dict[AssignmentKey, cp_model.IntVar],
    z: dict[SlotKey, cp_model.IntVar],
    d: dict[SlotKey, cp_model.IntVar],
    slot_keys: tuple[SlotKey, ...],
) -> None:
    # (9) Mixite residuelle : TPC placees dans une formation de type PC.
    for pivot_id, slot_index in slot_keys:
        tpc_load = sum(
            derived.q_i[commune_id] * variable
            for (commune_id, j, m), variable in x.items()
            if commune_id in derived.T and j == pivot_id and m == slot_index
        )
        model.Add(d[(pivot_id, slot_index)] >= tpc_load - config.parameters.Q * z[(pivot_id, slot_index)])


def _build_objective_terms(
    derived: DerivedParameters,
    config: OptimizerConfig,
    x: dict[AssignmentKey, cp_model.IntVar],
    y: dict[SlotKey, cp_model.IntVar],
    z: dict[SlotKey, cp_model.IntVar],
    d: dict[SlotKey, cp_model.IntVar],
    slot_keys: tuple[SlotKey, ...],
) -> dict[str, cp_model.LinearExpr]:
    travel = sum(
        derived.q_i[commune_id] * derived.tau_ij[(commune_id, pivot_id)] * variable
        for (commune_id, pivot_id, _), variable in x.items()
    )
    eligibility = sum(
        derived.e_j_PC[pivot_id] * y[(pivot_id, slot_index)]
        + (derived.e_j_TPC[pivot_id] - derived.e_j_PC[pivot_id]) * z[(pivot_id, slot_index)]
        for pivot_id, slot_index in slot_keys
    )
    mixing = sum(d[slot_key] for slot_key in slot_keys)
    return {"travel": travel, "eligibility": eligibility, "mixing": mixing}
