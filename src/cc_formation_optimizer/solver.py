"""Orchestration de la resolution CP-SAT."""

from __future__ import annotations

from dataclasses import dataclass

from ortools.sat.python import cp_model

from cc_formation_optimizer.config import OptimizerConfig
from cc_formation_optimizer.model_builder import ModelBundle


@dataclass(frozen=True)
class SolveResult:
    """Resultat minimal d'une resolution CP-SAT.

    Attributes
    ----------
    status : str
        Statut OR-Tools converti en chaine.
    objective_value : float | None
        Valeur d'objectif retournee par le solveur si une solution existe.
    solver : cp_model.CpSolver
        Instance de solveur conservee pour lire les variables.
    wall_time_seconds : float
        Temps de resolution mesure par CP-SAT.
    """

    status: str
    objective_value: float | None
    solver: cp_model.CpSolver
    wall_time_seconds: float


def solve_model(model_bundle: ModelBundle, config: OptimizerConfig) -> SolveResult:
    """Resout un modele CP-SAT avec les parametres du YAML.

    Parameters
    ----------
    model_bundle : ModelBundle
        Modele CP-SAT construit par :func:`build_model`.
    config : OptimizerConfig
        Configuration contenant les options de solveur.

    Returns
    -------
    SolveResult
        Statut, objectif eventuel, solveur et temps de resolution.
    """

    solver = cp_model.CpSolver()
    solver_config = config.solver

    if "time_limit_seconds" in solver_config:
        solver.parameters.max_time_in_seconds = float(solver_config["time_limit_seconds"])
    if "num_workers" in solver_config:
        solver.parameters.num_search_workers = int(solver_config["num_workers"])
    if "random_seed" in solver_config and solver_config["random_seed"] is not None:
        solver.parameters.random_seed = int(solver_config["random_seed"])
    if "log_search_progress" in solver_config:
        solver.parameters.log_search_progress = bool(solver_config["log_search_progress"])

    status_code = solver.Solve(model_bundle.model)
    status = solver.StatusName(status_code)
    objective_value = None
    if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        objective_value = solver.ObjectiveValue()

    return SolveResult(
        status=status,
        objective_value=objective_value,
        solver=solver,
        wall_time_seconds=solver.WallTime(),
    )
