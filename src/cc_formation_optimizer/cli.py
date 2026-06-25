"""Interface en ligne de commande du projet."""

from __future__ import annotations

import argparse
from pathlib import Path

from cc_formation_optimizer.config import ConfigError, load_config
from cc_formation_optimizer.data_preparation import DataPreparationError, prepare_data
from cc_formation_optimizer.data_loading import DataLoadingError, load_communes, load_compatibilities, load_travel_times
from cc_formation_optimizer.diagnostics import run_pre_solve_diagnostics
from cc_formation_optimizer.export import ExportError, export_solution
from cc_formation_optimizer.map_export import MapExportError, export_solution_map, render_map_from_exports
from cc_formation_optimizer.model_builder import build_model
from cc_formation_optimizer.parameters import build_derived_parameters
from cc_formation_optimizer.business_postprocess import PostprocessError, postprocess_business_rules
from cc_formation_optimizer.relaxation import export_relaxation_reports, run_relaxation_workflow
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

    prepare = subparsers.add_parser("prepare-data", help="Prepare les donnees brutes reelles en CSV propres.")
    prepare.add_argument("--config", type=Path, default=Path("config/config_ear2027.yaml"))
    prepare.add_argument("--input-dir", type=Path, default=None, help="Dossier des donnees brutes.")
    prepare.add_argument("--output-dir", type=Path, default=None, help="Dossier des CSV propres.")
    prepare.add_argument("--report", action="store_true", help="Produit le rapport Markdown et les statistiques JSON.")
    prepare.add_argument("--dry-run", action="store_true", help="Analyse sans ecrire de fichiers.")
    prepare.add_argument("--strict", action="store_true", help="Echoue en presence d'anomalies bloquantes.")

    diagnose = subparsers.add_parser("diagnose", help="Lance le diagnostic pre-resolution sans resoudre.")
    diagnose.add_argument("--config", type=Path, default=Path("config/config_ear2027.yaml"))

    solve = subparsers.add_parser("solve", help="Construit et resout le modele CP-SAT minimal.")
    solve.add_argument("--config", type=Path, default=Path("config/config_ear2027.yaml"))
    solve.add_argument("--export", action="store_true", help="Produit les exports finaux apres validation.")
    solve.add_argument("--map", action="store_true", help="Produit la carte HTML autonome apres validation.")
    solve.add_argument("--output-dir", type=Path, default=None, help="Repertoire racine des exports.")

    solve_relaxed = subparsers.add_parser("solve-relaxed", help="Resout avec assouplissement hierarchique.")
    solve_relaxed.add_argument("--config", type=Path, default=Path("config/config_ear2027.yaml"))
    solve_relaxed.add_argument("--export", action="store_true", help="Produit les exports de la solution retenue.")
    solve_relaxed.add_argument("--map", action="store_true", help="Produit la carte HTML autonome avec --export.")
    solve_relaxed.add_argument("--output-dir", type=Path, default=None, help="Repertoire racine des exports.")

    render_map = subparsers.add_parser("render-map", help="Regenere la carte depuis des exports existants, sans solveur.")
    render_map.add_argument("--config", type=Path, default=Path("config/config_ear2027.yaml"))
    render_map.add_argument("--solution-dir", type=Path, default=None, help="Racine contenant solutions/ et reports/.")
    render_map.add_argument("--sessions", type=Path, default=None, help="CSV sessions existant.")
    render_map.add_argument("--assignments", type=Path, default=None, help="CSV communes affectees existant.")
    render_map.add_argument("--stats", type=Path, default=None, help="JSON statistiques solution existant.")
    render_map.add_argument("--output", type=Path, default=None, help="Fichier HTML de sortie.")

    postprocess = subparsers.add_parser(
        "postprocess-business-rules",
        help="Analyse les exports existants et produit des propositions metier post-optimisation.",
    )
    postprocess.add_argument("--config", type=Path, default=Path("config/config_ear2027.yaml"))
    postprocess.add_argument("--input-dir", type=Path, default=Path("outputs"), help="Racine contenant solutions/.")
    postprocess.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Dossier des CSV de propositions. Par defaut: <input-dir>/postprocess.",
    )
    postprocess.add_argument(
        "--min-travel-time-gain-min",
        type=int,
        default=5,
        help="Gain minimal en minutes pour proposer un rattachement a un autre pivot de meme type.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Point d'entree CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "prepare-data":
        try:
            result = prepare_data(
                args.config,
                input_dir=args.input_dir,
                output_dir=args.output_dir,
                report=args.report,
                dry_run=args.dry_run,
                strict=args.strict,
            )
        except DataPreparationError as exc:
            parser.exit(status=2, message=f"Erreur de preparation des donnees: {exc}\n")

        print(f"Dossier brut: {result.input_dir}")
        print(f"Dossier propre: {result.output_dir}")
        print(f"Communes: {result.stats.get('communes_count', 0)}")
        print(f"PC: {result.stats.get('pc_count', 0)}")
        print(f"TPC: {result.stats.get('tpc_count', 0)}")
        print(f"Trajets: {result.stats.get('travel_times_count', 0)}")
        print(f"Compatibilites: {'chargees' if result.stats.get('compatibilities_loaded') else 'absentes'}")
        print(f"Anomalies bloquantes: {len(result.blocking_issues)}")
        print(f"Anomalies non bloquantes: {len(result.non_blocking_issues)}")
        if args.report and not args.dry_run:
            print(f"Rapport: {result.report_dir / 'rapport_preparation_donnees.md'}")
            print(f"Statistiques: {result.report_dir / 'statistiques_preparation_donnees.json'}")
        if args.dry_run:
            print("Dry-run: aucun fichier ecrit.")
        return 0

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

    if args.command == "diagnose":
        try:
            communes = load_communes(config)
            travel_times = load_travel_times(config)
            compatibilities = load_compatibilities(config)
            derived = build_derived_parameters(communes, travel_times, compatibilities, config)
            diagnostic = run_pre_solve_diagnostics(derived, config)
        except (DataLoadingError, ValueError) as exc:
            parser.exit(status=2, message=f"Erreur de donnees ou de diagnostic: {exc}\n")

        coords_available = sum(1 for commune in communes if commune.latitude is not None and commune.longitude is not None)
        print(f"Communes: {diagnostic.total_communes}")
        print(f"PC: {diagnostic.pc_count}")
        print(f"TPC: {diagnostic.tpc_count}")
        print(f"Total CC: {diagnostic.total_cc}")
        print(f"Borne minimale ceil(total_CC / Q): {diagnostic.min_required_formations}")
        print(f"Slots: {diagnostic.slot_count}")
        print(f"Trajets admissibles: {diagnostic.admissible_travel_count}")
        print(f"Communes orphelines: {len(diagnostic.orphan_communes)}")
        print(f"PC sans pivot compatible PC: {len(diagnostic.pc_without_pc_pivot)}")
        print(
            "Coherence B, f, k: "
            f"B={config.parameters.formation_budgets.B}, "
            f"f={config.parameters.formation_budgets.f}, "
            f"k={config.parameters.formation_budgets.k}"
        )
        print(f"Coordonnees carte: {coords_available}/{len(communes)}")
        if diagnostic.budget_warning:
            print(f"Alerte budget: {diagnostic.budget_warning}")
        return 0

    if args.command == "render-map":
        try:
            map_result = render_map_from_exports(
                config,
                solution_dir=args.solution_dir,
                sessions_path=args.sessions,
                assignments_path=args.assignments,
                stats_path=args.stats,
                output_path=args.output,
            )
        except (DataLoadingError, MapExportError, ValueError) as exc:
            parser.exit(status=2, message=f"Erreur de generation de carte: {exc}\n")

        print(f"Carte: {map_result.html_path}")
        print(f"Points cartographies: {map_result.mapped_points}")
        print(f"Communes sans coordonnees: {map_result.missing_coordinates}")
        print("Solveur: non relance")
        return 0

    if args.command == "postprocess-business-rules":
        try:
            result = postprocess_business_rules(
                input_dir=args.input_dir,
                config=config,
                output_dir=args.output_dir,
                min_travel_time_gain_min=args.min_travel_time_gain_min,
            )
        except (DataLoadingError, PostprocessError, ValueError) as exc:
            parser.exit(status=2, message=f"Erreur de post-traitement metier: {exc}\n")

        print("Business post-processing completed.")
        print(f"Proposals written to: {result.proposals_csv}")
        print(f"Summary written to: {result.summary_csv}")
        print("Original optimization exports were not modified.")
        print(f"Number of proposals: {result.proposal_count}")
        print("Solveur: non relance")
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
                if args.export:
                    export_result = export_solution(
                        solution,
                        validation_report,
                        model_bundle,
                        config,
                        args.config,
                        communes,
                        args.output_dir,
                    )
                if args.map:
                    map_result = export_solution_map(
                        solution,
                        validation_report,
                        model_bundle,
                        config,
                        communes,
                        args.output_dir,
                    )
        except (
            DataLoadingError,
            ExportError,
            MapExportError,
            SolutionExtractionError,
            SolutionValidationError,
            ValueError,
        ) as exc:
            parser.exit(status=2, message=f"Erreur de donnees ou de modele: {exc}\n")

        print(f"Statut: {result.status}")
        if solution is not None and validation_report is not None:
            print(f"Objectif total: {solution.objective.objectif_total}")
            print(f"Sessions ouvertes: {len(solution.sessions)}")
            print(f"Communes affectees: {len(solution.assignments)}")
            print(f"Total CC: {validation_report.total_cc}")
            print("Validation: OK")
            if args.export:
                print(f"Exports: {export_result.sessions_csv.parent.parent}")
            if args.map:
                print(f"Carte: {map_result.html_path}")
        elif result.objective_value is not None:
            print(f"Objectif: {result.objective_value}")
        print(f"Temps solveur: {result.wall_time_seconds:.3f}s")
        return 0

    if args.command == "solve-relaxed":
        try:
            communes = load_communes(config)
            travel_times = load_travel_times(config)
            compatibilities = load_compatibilities(config)
            relaxation_result = run_relaxation_workflow(config, communes, travel_times, compatibilities)
            relaxation_paths = export_relaxation_reports(relaxation_result, args.config, args.output_dir)

            export_result = None
            map_result = None
            if args.export and relaxation_result.final_solution is not None:
                final_config_path = relaxation_paths.get("final_config", args.config)
                export_result = export_solution(
                    relaxation_result.final_solution,
                    relaxation_result.final_validation_report,
                    relaxation_result.final_model_bundle,
                    relaxation_result.final_config,
                    final_config_path,
                    communes,
                    args.output_dir,
                )
                if args.map:
                    map_result = export_solution_map(
                        relaxation_result.final_solution,
                        relaxation_result.final_validation_report,
                        relaxation_result.final_model_bundle,
                        relaxation_result.final_config,
                        communes,
                        args.output_dir,
                    )
        except (
            DataLoadingError,
            ExportError,
            MapExportError,
            SolutionExtractionError,
            SolutionValidationError,
            ValueError,
        ) as exc:
            parser.exit(status=2, message=f"Erreur de donnees ou de modele: {exc}\n")

        accepted = relaxation_result.accepted_attempt
        print(f"Tentatives: {len(relaxation_result.attempts)}")
        print(f"Solution acceptee: {'oui' if accepted else 'non'}")
        if accepted is not None:
            print(f"Niveau retenu: {accepted.level} ({accepted.level_name})")
            print(f"Statut solveur: {accepted.solver_status}")
            print(f"Objectif total: {accepted.objective_total}")
        print(f"Journal: {relaxation_paths['journal']}")
        print(f"Rapport: {relaxation_paths['report']}")
        if "final_config" in relaxation_paths:
            print(f"Configuration finale: {relaxation_paths['final_config']}")
        if export_result is not None:
            print(f"Exports: {export_result.sessions_csv.parent.parent}")
        if map_result is not None:
            print(f"Carte: {map_result.html_path}")
        return 0

    parser.error(f"Commande inconnue: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
