"""Interface en ligne de commande du projet."""

from __future__ import annotations

import argparse
from pathlib import Path

from cc_formation_optimizer.config import ConfigError, load_config
from cc_formation_optimizer.data_loading import DataLoadingError, load_communes, load_compatibilities, load_travel_times
from cc_formation_optimizer.model_builder import build_model
from cc_formation_optimizer.parameters import build_derived_parameters
from cc_formation_optimizer.solution_extractor import SolutionExtractionError, extract_solution
from cc_formation_optimizer.solver import solve_model
from cc_formation_optimizer.validation import SolutionValidationError, validate_solution


def build_parser() -> argparse.ArgumentParser:
    """Construit le parseur CLI."""

    parser = argparse.ArgumentParser(prog="cc-formation-optimizer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-config", help="Valide un fichier de configuration YAML.")
    validate.add_argument("--config", type=Path, default=Path("config/config_ear2027.yaml"))

    show = subparsers.add_parser("show-config", help="Affiche un resume de la configuration.")
    show.add_argument("--config", type=Path, default=Path("config/config_ear2027.yaml"))

    solve = subparsers.add_parser("solve", help="Construit et resout le modele CP-SAT minimal.")
    solve.add_argument("--config", type=Path, default=Path("config/config_ear2027.yaml"))

    return parser


def main(argv: list[str] | None = None) -> int:
    """Point d'entree CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        parser.exit(status=2, message=f"Erreur de configuration: {exc}\n")

    if args.command == "validate-config":
        print(f"Configuration valide: {args.config}")
        return 0

    if args.command == "show-config":
        params = config.parameters
        budgets = params.formation_budgets
        print(f"Configuration: {config.metadata.get('name')} ({config.metadata.get('version')})")
        print(f"T={params.T}, Q={params.Q}, L={params.L}")
        print(f"B={budgets.B}, f={budgets.f}, k={budgets.k}")
        print(f"M_PC={params.pivot_slots.M_PC}, M_TPC={params.pivot_slots.M_TPC}")
        return 0

    if args.command == "solve":
        try:
            communes = load_communes(config)
            travel_times = load_travel_times(config)
            compatibilities = load_compatibilities(config)
            derived = build_derived_parameters(communes, travel_times, compatibilities, config)
            model_bundle = build_model(derived, config)
            result = solve_model(model_bundle, config)
            solution = None
            validation_report = None
            if result.status in {"OPTIMAL", "FEASIBLE"}:
                solution = extract_solution(model_bundle, result, communes, config)
                validation_report = validate_solution(solution, model_bundle, config)
        except (DataLoadingError, SolutionExtractionError, SolutionValidationError, ValueError) as exc:
            parser.exit(status=2, message=f"Erreur de donnees ou de modele: {exc}\n")

        print(f"Statut: {result.status}")
        if solution is not None and validation_report is not None:
            print(f"Objectif total: {solution.objective.objectif_total}")
            print(f"Sessions ouvertes: {len(solution.sessions)}")
            print(f"Communes affectees: {len(solution.assignments)}")
            print(f"Total CC: {validation_report.total_cc}")
            print("Validation: OK")
        elif result.objective_value is not None:
            print(f"Objectif: {result.objective_value}")
        print(f"Temps solveur: {result.wall_time_seconds:.3f}s")
        return 0

    parser.error(f"Commande inconnue: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
