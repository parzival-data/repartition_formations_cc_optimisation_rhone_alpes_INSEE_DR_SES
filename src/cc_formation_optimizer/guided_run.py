"""Assistant interactif pour executer le pipeline complet."""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from typing import Any, Callable

from cc_formation_optimizer.business_postprocess import postprocess_business_rules
from cc_formation_optimizer.config import ConfigError, OptimizerConfig, config_from_dict, load_config
from cc_formation_optimizer.data_loading import DataLoadingError, load_communes, load_compatibilities, load_travel_times
from cc_formation_optimizer.data_preparation import DataPreparationError, prepare_data
from cc_formation_optimizer.diagnostics import run_pre_solve_diagnostics
from cc_formation_optimizer.export import ExportError, export_solution
from cc_formation_optimizer.map_export import MapExportError, export_solution_map, render_map_from_exports
from cc_formation_optimizer.model_builder import build_model
from cc_formation_optimizer.parameters import build_derived_parameters
from cc_formation_optimizer.relaxation import export_relaxation_reports, run_relaxation_workflow
from cc_formation_optimizer.solution_extractor import SolutionExtractionError, extract_solution
from cc_formation_optimizer.solver import solve_model
from cc_formation_optimizer.validation import SolutionValidationError, validate_solution


class GuidedRunError(ValueError):
    """Erreur lisible pour l'utilisateur de la commande guidee."""


@dataclass(frozen=True)
class GuidedRunOptions:
    """Options d'execution de la commande guidee."""

    config_path: Path
    yes: bool = False
    skip_travel_times: bool = False
    skip_solve: bool = False
    skip_map: bool = False
    skip_postprocess: bool = False
    input_dir: Path | None = None
    processed_dir: Path | None = None
    output_dir: Path | None = None


@dataclass(frozen=True)
class RuntimePaths:
    """Chemins principaux utilises par l'execution guidee."""

    input_dir: Path
    processed_dir: Path
    output_dir: Path
    communes_csv: Path
    travel_times_csv: Path


@dataclass(frozen=True)
class DiagonalFixReport:
    """Bilan de verification et correction des diagonales."""

    communes_checked: int
    missing_added: int
    non_zero_found: int
    non_zero_corrected: int
    duplicate_diagonal_rows: int
    report_path: Path


InputFunc = Callable[[str], str]
OutputFunc = Callable[[str], None]


def run_guided(options: GuidedRunOptions, input_func: InputFunc | None = None, output: OutputFunc = print) -> int:
    """Execute l'assistant interactif complet.

    Parameters
    ----------
    options : GuidedRunOptions
        Options CLI deja parsees.
    input_func : Callable[[str], str], default=input
        Fonction de lecture, injectable dans les tests.
    output : Callable[[str], None], default=print
        Fonction d'affichage, injectable dans les tests.

    Returns
    -------
    int
        Code de sortie de la commande.
    """

    if input_func is None:
        input_func = input

    config, paths = _load_runtime(options)
    _print_intro(paths, output)
    _check_environment(options.config_path, config, paths, output)
    if not _confirm("Continuer vers la preparation des donnees ? [O/n] ", options, input_func, output):
        output("Arret demande par l'utilisateur. Aucune etape lourde n'a ete lancee.")
        return 0

    _prepare_or_reuse_data(options, config, paths, input_func, output)
    config = _runtime_config(config, options, paths)
    _print_processed_statistics(config, output)
    _fix_diagonal_step(config, paths, options, input_func, output)
    if not _confirm("Continuer vers l'etape temps de trajet ? [O/n] ", options, input_func, output):
        output("Arret demande par l'utilisateur apres la preparation.")
        return 0

    if not options.skip_travel_times:
        _travel_time_step(config, paths, options, input_func, output)
    else:
        output("Etape temps de trajet ignoree (--skip-travel-times).")
    if not _confirm("Continuer vers le diagnostic avant optimisation ? [O/n] ", options, input_func, output):
        output("Arret demande par l'utilisateur apres les temps de trajet.")
        return 0

    diagnostic_ok = _diagnostic_step(config, paths, options, input_func, output)
    if not diagnostic_ok:
        output("Le diagnostic n'a pas pu etre execute. Corrigez les fichiers avant de lancer l'optimisation.")
        return 2
    if not _confirm("Continuer vers l'optimisation ? [O/n] ", options, input_func, output):
        output("Arret demande par l'utilisateur apres le diagnostic.")
        return 0

    solved = False
    if options.skip_solve:
        output("Optimisation ignoree (--skip-solve). Aucun solveur n'est lance.")
    else:
        solved = _solve_step(config, paths, options, input_func, output)

    _exports_step(config, paths, options, input_func, output, solved)
    if not _confirm("Continuer vers la surcouche metier post-optimisation ? [O/n] ", options, input_func, output):
        output("Arret demande par l'utilisateur apres la verification des exports.")
        return 0
    if not options.skip_postprocess:
        _postprocess_step(config, paths, options, input_func, output)
    else:
        output("Surcouche metier ignoree (--skip-postprocess).")
    _final_summary(paths, output)
    return 0


def ensure_travel_time_diagonal(
    communes_csv: Path,
    travel_times_csv: Path,
    columns: dict[str, str],
    report_path: Path,
    *,
    fix_non_zero: bool = True,
) -> DiagonalFixReport:
    """Verifie et complete les trajets diagonaux ``i -> i``.

    La fonction ajoute les diagonales manquantes a zero, corrige les diagonales
    non nulles si demande, et n'ajoute jamais une seconde ligne diagonale pour
    une commune deja presente.
    """

    commune_col = columns["commune_id"]
    origin_col = columns["origin_id"]
    destination_col = columns["destination_id"]
    minutes_col = columns["travel_time_minutes"]

    commune_rows, _commune_fields = _read_csv_rows(communes_csv, [commune_col])
    travel_rows, travel_fields = _read_csv_rows(travel_times_csv, [origin_col, destination_col, minutes_col])
    commune_ids = [_clean_id(row[commune_col]) for row in commune_rows if _clean_id(row[commune_col])]

    diagonal_indexes: dict[str, list[int]] = {commune_id: [] for commune_id in commune_ids}
    for index, row in enumerate(travel_rows):
        origin = _clean_id(row.get(origin_col, ""))
        destination = _clean_id(row.get(destination_col, ""))
        if origin == destination and origin in diagonal_indexes:
            diagonal_indexes[origin].append(index)

    missing = [commune_id for commune_id, indexes in diagonal_indexes.items() if not indexes]
    duplicate_count = sum(max(0, len(indexes) - 1) for indexes in diagonal_indexes.values())
    non_zero_indexes = [
        index
        for indexes in diagonal_indexes.values()
        for index in indexes
        if _minutes_value(travel_rows[index].get(minutes_col, "")) != 0
    ]

    changed = False
    for commune_id in missing:
        row = {field: "" for field in travel_fields}
        row[origin_col] = commune_id
        row[destination_col] = commune_id
        row[minutes_col] = "0"
        travel_rows.append(row)
        changed = True

    corrected = 0
    if fix_non_zero:
        for index in non_zero_indexes:
            if str(travel_rows[index].get(minutes_col, "")).strip() != "0":
                travel_rows[index][minutes_col] = "0"
                corrected += 1
                changed = True

    if changed:
        _write_csv_rows(travel_times_csv, travel_fields, travel_rows)

    report = DiagonalFixReport(
        communes_checked=len(commune_ids),
        missing_added=len(missing),
        non_zero_found=len(non_zero_indexes),
        non_zero_corrected=corrected,
        duplicate_diagonal_rows=duplicate_count,
        report_path=report_path,
    )
    _write_diagonal_report(report)
    return report


def _load_runtime(options: GuidedRunOptions) -> tuple[OptimizerConfig, RuntimePaths]:
    if not options.config_path.exists():
        raise GuidedRunError(f"Configuration introuvable: {options.config_path}.")
    try:
        config = load_config(options.config_path)
    except ConfigError as exc:
        raise GuidedRunError(f"Configuration invalide: {exc}") from exc

    paths = _runtime_paths(config, options)
    runtime_config = _runtime_config(config, options, paths)
    return runtime_config, paths


def _runtime_paths(config: OptimizerConfig, options: GuidedRunOptions) -> RuntimePaths:
    preparation = config.raw.get("data_preparation", {}) if isinstance(config.raw.get("data_preparation", {}), dict) else {}
    input_dir = Path(options.input_dir or preparation.get("input_dir") or "donnee_brut_EAR27")
    processed_dir = Path(
        options.processed_dir
        or preparation.get("output_dir")
        or config.inputs.communes_path.parent
        or "data/processed"
    )
    output_dir = Path(options.output_dir or config.exports.get("output_dir", "outputs"))
    communes_csv = processed_dir / "communes_clean.csv" if options.processed_dir is not None else config.inputs.communes_path
    travel_times_csv = (
        processed_dir / "temps_trajet_clean.csv" if options.processed_dir is not None else config.inputs.travel_times_path
    )
    return RuntimePaths(
        input_dir=input_dir,
        processed_dir=processed_dir,
        output_dir=output_dir,
        communes_csv=communes_csv,
        travel_times_csv=travel_times_csv,
    )


def _runtime_config(config: OptimizerConfig, options: GuidedRunOptions, paths: RuntimePaths) -> OptimizerConfig:
    raw = dict(config.raw)
    raw["exports"] = dict(raw.get("exports", {}))
    raw["exports"]["output_dir"] = str(paths.output_dir)
    if options.processed_dir is not None:
        raw["inputs"] = dict(raw["inputs"])
        raw["inputs"]["communes_path"] = str(paths.communes_csv)
        raw["inputs"]["travel_times_path"] = str(paths.travel_times_csv)
        compatibility_path = paths.processed_dir / "compatibilites_clean.csv"
        if compatibility_path.exists():
            raw["inputs"]["compatibility_path"] = str(compatibility_path)
    return config_from_dict(raw)


def _print_intro(paths: RuntimePaths, output: OutputFunc) -> None:
    output("")
    output("Execution guidee du projet cc-formation-optimizer")
    output("Cet assistant va vous guider depuis les fichiers d'entree jusqu'aux exports finaux.")
    output("Aucune etape longue ou importante ne sera lancee sans confirmation explicite.")
    output("")
    output("Dossiers utilises :")
    output(f"- Fichiers bruts : {paths.input_dir}")
    output(f"- Fichiers prepares : {paths.processed_dir}")
    output(f"- Exports finaux : {paths.output_dir}")
    output("")


def _check_environment(
    config_path: Path,
    config: OptimizerConfig,
    paths: RuntimePaths,
    output: OutputFunc,
) -> None:
    output("1. Verification de l'environnement")
    if not Path("pyproject.toml").exists() or not Path("src/cc_formation_optimizer/cli.py").exists():
        raise GuidedRunError(
            "La commande doit etre lancee depuis la racine du depot cc-formation-optimizer "
            "(le dossier qui contient pyproject.toml)."
        )
    output(f"- Configuration trouvee : {config_path}")
    output("- Depot Python detecte : src/cc_formation_optimizer")

    _print_expected_files(config, paths, output)
    paths.processed_dir.mkdir(parents=True, exist_ok=True)
    paths.output_dir.mkdir(parents=True, exist_ok=True)

    missing = _missing_required_raw_files(config, paths)
    processed_ready = paths.communes_csv.exists() and paths.travel_times_csv.exists()
    if missing and not processed_ready:
        formatted = "\n".join(f"  - {path}" for path in missing)
        raise GuidedRunError(
            "Fichiers d'entree manquants.\n"
            f"{formatted}\n"
            "Deposez ces fichiers dans le dossier indique, puis relancez la commande."
        )
    if missing:
        output("- Certains fichiers bruts manquent, mais des CSV prepares existent deja. Ils pourront etre reutilises.")
    output("- Verification environnement terminee.")


def _print_expected_files(config: OptimizerConfig, paths: RuntimePaths, output: OutputFunc) -> None:
    output("")
    output("Fichiers a deposer avant la preparation :")
    preparation = config.raw.get("data_preparation", {}) if isinstance(config.raw.get("data_preparation", {}), dict) else {}
    communes_file = _nested_value(preparation, "communes", "file")
    travel_file = _nested_value(preparation, "travel_times", "file")
    coordinates_file = _nested_value(preparation, "coordinates", "file")
    compat_file = _nested_value(preparation, "compatibilities", "file")
    if communes_file:
        output(f"- Communes : {paths.input_dir / str(communes_file)}")
    else:
        output("- Communes : aucun fichier brut configure; le CSV prepare sera utilise s'il existe.")
    if travel_file:
        output(f"- Temps de trajet importes : {paths.input_dir / str(travel_file)}")
    else:
        output("- Temps de trajet : aucun fichier brut configure dans prepare-data.")
    if coordinates_file:
        output(f"- Coordonnees optionnelles : {paths.input_dir / str(coordinates_file)}")
    if compat_file:
        output(f"- Compatibilites optionnelles : {paths.input_dir / str(compat_file)}")
    output("")
    output("Fichiers prepares attendus par l'optimiseur :")
    output(f"- Communes preparees : {paths.communes_csv}")
    output(f"- Temps de trajet prepares : {paths.travel_times_csv}")
    output("")
    _print_travel_time_core_hint(output)


def _print_travel_time_core_hint(output: OutputFunc) -> None:
    core_config = Path("travel_time_core/config/config_travel_times.yaml")
    if core_config.exists():
        output("Sous-projet temps de trajet detecte :")
        output(f"- Configuration : {core_config}")
        output("- Commande existante reutilisable : travel-time-core --config travel_time_core/config/config_travel_times.yaml run-pipeline")
        output("- Export compatible attendu : travel_time_core/data/output/temps_trajet_clean.csv")
        output("")


def _prepare_or_reuse_data(
    options: GuidedRunOptions,
    config: OptimizerConfig,
    paths: RuntimePaths,
    input_func: InputFunc,
    output: OutputFunc,
) -> None:
    output("2. Preparation des donnees")
    processed_ready = paths.communes_csv.exists() and paths.travel_times_csv.exists()
    if processed_ready:
        output("- Des fichiers prepares existent deja.")
        output(f"  Communes : {paths.communes_csv}")
        output(f"  Temps : {paths.travel_times_csv}")
        if _confirm("Les reutiliser sans relancer prepare-data ? [O/n] ", options, input_func, output):
            output("- Preparation non relancee.")
            return

    if not _confirm("Lancer prepare-data maintenant ? [O/n] ", options, input_func, output):
        output("- Preparation ignoree. Les fichiers prepares existants seront utilises si possible.")
        return

    try:
        result = prepare_data(
            options.config_path,
            input_dir=paths.input_dir,
            output_dir=paths.processed_dir,
            report=True,
        )
    except DataPreparationError as exc:
        raise GuidedRunError(f"Preparation des donnees impossible: {exc}") from exc

    output("- prepare-data termine.")
    output(f"- Fichiers lus dans : {result.input_dir}")
    output(f"- Fichiers crees dans : {result.output_dir}")
    output(f"- Communes : {result.stats.get('communes_count', 0)}")
    output(f"- PC : {result.stats.get('pc_count', 0)}")
    output(f"- TPC : {result.stats.get('tpc_count', 0)}")
    output(f"- Trajets : {result.stats.get('travel_times_count', 0)}")
    output(f"- Anomalies bloquantes : {len(result.blocking_issues)}")
    output(f"- Anomalies non bloquantes : {len(result.non_blocking_issues)}")
    if not paths.communes_csv.exists() or not paths.travel_times_csv.exists():
        raise GuidedRunError(
            "La preparation est terminee, mais les CSV attendus ne sont pas tous presents. "
            f"Verifiez {paths.processed_dir}."
        )


def _print_processed_statistics(config: OptimizerConfig, output: OutputFunc) -> None:
    try:
        communes = load_communes(config)
    except DataLoadingError as exc:
        raise GuidedRunError(f"Impossible de lire les communes preparees: {exc}") from exc
    pc_count = sum(1 for commune in communes if commune.category == "PC")
    tpc_count = sum(1 for commune in communes if commune.category == "TPC")
    total_cc = sum(1 if commune.population <= 5000 else 2 for commune in communes)
    coordinates = sum(1 for commune in communes if commune.latitude is not None and commune.longitude is not None)
    output("")
    output("Statistiques des communes preparees :")
    output(f"- Communes : {len(communes)}")
    output(f"- PC : {pc_count}")
    output(f"- TPC : {tpc_count}")
    output(f"- Nombre theorique de CC : {total_cc}")
    output(f"- Coordonnees disponibles : {coordinates}/{len(communes)}")


def _fix_diagonal_step(
    config: OptimizerConfig,
    paths: RuntimePaths,
    options: GuidedRunOptions,
    input_func: InputFunc,
    output: OutputFunc,
) -> None:
    output("")
    output("3. Controle des trajets diagonaux")
    if not paths.communes_csv.exists() or not paths.travel_times_csv.exists():
        raise GuidedRunError("Impossible de verifier les diagonales: fichiers prepares absents.")

    preview = ensure_travel_time_diagonal(
        paths.communes_csv,
        paths.travel_times_csv,
        config.columns,
        paths.output_dir / "reports" / "rapport_diagonale_temps_trajet.json",
        fix_non_zero=False,
    )
    if preview.non_zero_found == 0:
        output(f"- Communes controlees : {preview.communes_checked}")
        output(f"- Diagonales ajoutees : {preview.missing_added}")
        output(f"- Diagonales dupliquees deja presentes : {preview.duplicate_diagonal_rows}")
        output(f"- Rapport : {preview.report_path}")
        return

    output(f"- {preview.non_zero_found} diagonale(s) ont un temps non nul.")
    if _confirm("Corriger ces diagonales a 0 minute ? [O/n] ", options, input_func, output):
        report = ensure_travel_time_diagonal(
            paths.communes_csv,
            paths.travel_times_csv,
            config.columns,
            paths.output_dir / "reports" / "rapport_diagonale_temps_trajet.json",
            fix_non_zero=True,
        )
        output(f"- Diagonales corrigees : {report.non_zero_corrected}")
        output(f"- Rapport : {report.report_path}")
    else:
        output("- Correction des diagonales non nulles ignoree.")


def _travel_time_step(
    config: OptimizerConfig,
    paths: RuntimePaths,
    options: GuidedRunOptions,
    input_func: InputFunc,
    output: OutputFunc,
) -> None:
    output("")
    output("4. Temps de trajet")
    if paths.travel_times_csv.exists():
        output(f"- Un fichier de temps de trajet existe deja : {paths.travel_times_csv}")
        choice = _choice(
            "Que voulez-vous faire ? [1=reutiliser, 2=recalculer avec travel_time_core, 3=arreter] ",
            {"1", "2", "3"},
            "1",
            options,
            input_func,
            output,
        )
        if choice == "1":
            output("- Temps de trajet reutilises.")
            return
        if choice == "3":
            raise GuidedRunError("Arret demande pour verifier les temps de trajet.")
    else:
        output("- Aucun fichier de temps de trajet prepare n'a ete trouve.")
        choice = "2"

    if choice == "2":
        _run_travel_time_core(paths, options, input_func, output)
        generated = Path("travel_time_core/data/output/temps_trajet_clean.csv")
        if generated.exists() and _confirm(
            f"Copier {generated} vers {paths.travel_times_csv} ? [O/n] ",
            options,
            input_func,
            output,
        ):
            paths.travel_times_csv.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(generated, paths.travel_times_csv)
            output(f"- Temps de trajet copies vers : {paths.travel_times_csv}")


def _run_travel_time_core(
    paths: RuntimePaths,
    options: GuidedRunOptions,
    input_func: InputFunc,
    output: OutputFunc,
) -> None:
    core_dir = Path("travel_time_core")
    core_config = core_dir / "config" / "config_travel_times.yaml"
    if not core_config.exists():
        raise GuidedRunError("Sous-projet travel_time_core introuvable ou configuration absente.")
    output("Le calcul des temps de trajet peut etre long, surtout en mode IGN.")
    if not _confirm("Lancer travel_time_core run-pipeline maintenant ? [o/N] ", options, input_func, output, default=False, long_step=True):
        output("- Calcul des temps de trajet non lance.")
        return
    command = [
        sys.executable,
        "-m",
        "travel_times.cli",
        "--config",
        "config/config_travel_times.yaml",
        "run-pipeline",
    ]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(core_dir / "src") + os.pathsep + env.get("PYTHONPATH", "")
    output(f"- Commande lancee dans {core_dir}: {' '.join(command)}")
    completed = subprocess.run(command, cwd=core_dir, env=env, check=False)
    if completed.returncode != 0:
        raise GuidedRunError("travel_time_core a echoue. Verifiez sa configuration et ses fichiers d'entree.")
    output("- travel_time_core termine.")


def _diagnostic_step(
    config: OptimizerConfig,
    paths: RuntimePaths,
    options: GuidedRunOptions,
    input_func: InputFunc,
    output: OutputFunc,
) -> bool:
    output("")
    output("5. Diagnostic avant optimisation")
    output("- validate-config : configuration chargee et valide.")
    output(
        "- show-config : "
        f"T={config.parameters.T}, Q={config.parameters.Q}, L={config.parameters.L}, "
        f"B={config.parameters.formation_budgets.B}, f={config.parameters.formation_budgets.f}, "
        f"k={config.parameters.formation_budgets.k}"
    )
    if not _confirm("Lancer le diagnostic des donnees preparees ? [O/n] ", options, input_func, output):
        output("- Diagnostic ignore.")
        return False
    try:
        communes = load_communes(config)
        travel_times = load_travel_times(config)
        compatibilities = load_compatibilities(config)
        derived = build_derived_parameters(communes, travel_times, compatibilities, config)
        diagnostic = run_pre_solve_diagnostics(derived, config)
    except (DataLoadingError, ValueError) as exc:
        output(f"- Diagnostic impossible : {exc}")
        return False

    total_capacity = config.parameters.formation_budgets.B * config.parameters.Q
    output("- Diagnostic termine.")
    output(f"- Nombre de communes : {diagnostic.total_communes}")
    output(f"- Nombre total de CC : {diagnostic.total_cc}")
    output(f"- Capacite totale maximale : {total_capacity} CC")
    output(f"- Nombre maximal de formations : {config.parameters.formation_budgets.B}")
    output(f"- Borne minimale de formations : {ceil(diagnostic.total_cc / config.parameters.Q)}")
    output(f"- Trajets admissibles : {diagnostic.admissible_travel_count}")
    output(f"- Communes sans trajet admissible : {len(diagnostic.orphan_communes)}")
    if diagnostic.orphan_communes:
        output("  Communes concernees : " + ", ".join(diagnostic.orphan_communes))
    if diagnostic.pc_without_pc_pivot:
        output(f"- PC sans pivot compatible PC : {len(diagnostic.pc_without_pc_pivot)}")
    if diagnostic.budget_warning:
        output(f"- Risque de non-faisabilite : {diagnostic.budget_warning}")
    return True


def _solve_step(
    config: OptimizerConfig,
    paths: RuntimePaths,
    options: GuidedRunOptions,
    input_func: InputFunc,
    output: OutputFunc,
) -> bool:
    output("")
    output("6. Optimisation")
    output("Cette etape peut prendre du temps.")
    if not _confirm("Lancer l'optimisation normale avec exports et carte ? [o/N] ", options, input_func, output, default=False, long_step=True):
        output("- Optimisation non lancee.")
        return False
    status = _run_strict_solve(config, options.config_path, paths, output)
    _explain_solver_status(status, output)
    if status in {"OPTIMAL", "FEASIBLE"}:
        return True
    if _confirm("Essayer solve-relaxed avec assouplissements configures ? [o/N] ", options, input_func, output, default=False, long_step=True):
        relaxed_status = _run_relaxed_solve(config, options.config_path, paths, output)
        _explain_solver_status(relaxed_status, output)
        return relaxed_status in {"OPTIMAL", "FEASIBLE"}
    return False


def _run_strict_solve(config: OptimizerConfig, config_path: Path, paths: RuntimePaths, output: OutputFunc) -> str:
    try:
        communes = load_communes(config)
        travel_times = load_travel_times(config)
        compatibilities = load_compatibilities(config)
        derived = build_derived_parameters(communes, travel_times, compatibilities, config)
        model_bundle = build_model(derived, config)
        result = solve_model(model_bundle, config)
        if result.status in {"OPTIMAL", "FEASIBLE"}:
            solution = extract_solution(model_bundle, result, communes, config)
            validation_report = validate_solution(solution, model_bundle, config)
            export_result = export_solution(solution, validation_report, model_bundle, config, config_path, communes, paths.output_dir)
            map_result = export_solution_map(solution, validation_report, model_bundle, config, communes, paths.output_dir)
            output(f"- Exports : {export_result.sessions_csv.parent.parent}")
            output(f"- Carte : {map_result.html_path}")
        output(f"- Statut solveur : {result.status}")
        return result.status
    except (
        DataLoadingError,
        ExportError,
        MapExportError,
        SolutionExtractionError,
        SolutionValidationError,
        ValueError,
    ) as exc:
        output(f"- Optimisation normale impossible : {exc}")
        return "MODEL_INVALID"


def _run_relaxed_solve(config: OptimizerConfig, config_path: Path, paths: RuntimePaths, output: OutputFunc) -> str:
    try:
        communes = load_communes(config)
        travel_times = load_travel_times(config)
        compatibilities = load_compatibilities(config)
        result = run_relaxation_workflow(config, communes, travel_times, compatibilities)
        relaxation_paths = export_relaxation_reports(result, config_path, paths.output_dir)
        if result.final_solution is not None:
            final_config_path = relaxation_paths.get("final_config", config_path)
            export_result = export_solution(
                result.final_solution,
                result.final_validation_report,
                result.final_model_bundle,
                result.final_config,
                final_config_path,
                communes,
                paths.output_dir,
            )
            map_result = export_solution_map(
                result.final_solution,
                result.final_validation_report,
                result.final_model_bundle,
                result.final_config,
                communes,
                paths.output_dir,
            )
            output(f"- Exports : {export_result.sessions_csv.parent.parent}")
            output(f"- Carte : {map_result.html_path}")
            output(f"- Rapport assouplissements : {relaxation_paths['report']}")
            return result.accepted_attempt.solver_status if result.accepted_attempt else "UNKNOWN"
        output(f"- Aucune solution acceptee. Rapport : {relaxation_paths['report']}")
        return "UNKNOWN"
    except (
        DataLoadingError,
        ExportError,
        MapExportError,
        SolutionExtractionError,
        SolutionValidationError,
        ValueError,
    ) as exc:
        output(f"- Optimisation assouplie impossible : {exc}")
        return "MODEL_INVALID"


def _exports_step(
    config: OptimizerConfig,
    paths: RuntimePaths,
    options: GuidedRunOptions,
    input_func: InputFunc,
    output: OutputFunc,
    solved: bool,
) -> None:
    output("")
    output("7. Exports et carte")
    expected = _expected_export_files(paths.output_dir)
    existing = [path for path in expected if path.exists()]
    if len(existing) == len(expected):
        output("- Les exports finaux existent deja :")
    else:
        output("- Exports presents pour le moment :")
    for path in expected:
        status = "OK" if path.exists() else "manquant"
        output(f"  [{status}] {path}")
    if not options.skip_map and (paths.output_dir / "solutions" / "sessions.csv").exists():
        map_path = paths.output_dir / "maps" / "solution_map.html"
        if not map_path.exists() and _confirm("Regenerer uniquement la carte depuis les exports ? [O/n] ", options, input_func, output):
            try:
                result = render_map_from_exports(config, solution_dir=paths.output_dir)
                output(f"- Carte regeneree : {result.html_path}")
            except (DataLoadingError, MapExportError, ValueError) as exc:
                output(f"- Carte non regeneree : {exc}")
    if not solved and len(existing) != len(expected):
        output("- Aucun nouvel export complet n'a ete produit pendant cette execution.")


def _postprocess_step(
    config: OptimizerConfig,
    paths: RuntimePaths,
    options: GuidedRunOptions,
    input_func: InputFunc,
    output: OutputFunc,
) -> None:
    output("")
    output("8. Surcouche metier post-optimisation")
    output("Cette etape lit les exports et produit des propositions. Elle ne modifie pas la solution optimisee.")
    if not (paths.output_dir / "solutions" / "sessions.csv").exists():
        output("- Exports de solution absents : post-traitement non lance.")
        return
    if not _confirm("Lancer le post-traitement metier ? [O/n] ", options, input_func, output):
        output("- Post-traitement ignore.")
        return
    try:
        result = postprocess_business_rules(
            input_dir=paths.output_dir,
            config=config,
            output_dir=paths.output_dir / "postprocess",
            min_travel_time_gain_min=5,
        )
    except (DataLoadingError, ValueError) as exc:
        output(f"- Post-traitement impossible : {exc}")
        return
    output(f"- Propositions : {result.proposals_csv}")
    output(f"- Synthese : {result.summary_csv}")


def _final_summary(paths: RuntimePaths, output: OutputFunc) -> None:
    output("")
    output("Resume final")
    output(f"- Fichiers prepares : {paths.processed_dir}")
    output(f"- Exports : {paths.output_dir}")
    output("- Vous pouvez relancer seulement la carte avec : cc-formation-optimizer render-map --config config/config_ear2027.yaml --solution-dir outputs")


def _confirm(
    prompt: str,
    options: GuidedRunOptions,
    input_func: InputFunc,
    output: OutputFunc,
    *,
    default: bool = True,
    long_step: bool = False,
) -> bool:
    if options.yes and not long_step:
        output(f"{prompt}{'O' if default else 'n'}")
        return default
    answer = input_func(prompt).strip().lower()
    if not answer:
        return default
    return answer in {"o", "oui", "y", "yes"}


def _choice(
    prompt: str,
    allowed: set[str],
    default: str,
    options: GuidedRunOptions,
    input_func: InputFunc,
    output: OutputFunc,
) -> str:
    if options.yes:
        output(f"{prompt}{default}")
        return default
    while True:
        answer = input_func(prompt).strip() or default
        if answer in allowed:
            return answer
        output("Reponse non reconnue. Choisissez: " + ", ".join(sorted(allowed)))


def _missing_required_raw_files(config: OptimizerConfig, paths: RuntimePaths) -> list[Path]:
    preparation = config.raw.get("data_preparation", {}) if isinstance(config.raw.get("data_preparation", {}), dict) else {}
    names = [_nested_value(preparation, "communes", "file")]
    # Le fichier de temps de trajet brut est requis seulement si aucun CSV prepare n'existe.
    if not paths.travel_times_csv.exists():
        names.append(_nested_value(preparation, "travel_times", "file"))
    return [paths.input_dir / str(name) for name in names if name and not (paths.input_dir / str(name)).exists()]


def _nested_value(mapping: dict[str, Any], section: str, key: str) -> Any:
    value = mapping.get(section, {})
    if not isinstance(value, dict):
        return None
    return value.get(key)


def _expected_export_files(output_dir: Path) -> list[Path]:
    return [
        output_dir / "solutions" / "sessions.csv",
        output_dir / "solutions" / "communes_affectees.csv",
        output_dir / "reports" / "rapport_solution.md",
        output_dir / "reports" / "statistiques_solution.json",
        output_dir / "maps" / "solution_map.html",
    ]


def _explain_solver_status(status: str, output: OutputFunc) -> None:
    explanations = {
        "OPTIMAL": "OPTIMAL : une solution faisable a ete trouvee et le solveur a prouve qu'elle est optimale.",
        "FEASIBLE": "FEASIBLE : une solution valide existe, mais elle n'est pas prouvee optimale.",
        "INFEASIBLE": "INFEASIBLE : aucune solution ne respecte toutes les contraintes actuelles.",
        "UNKNOWN": "UNKNOWN : le solveur s'est arrete sans preuve suffisante ou sans solution exploitable.",
        "MODEL_INVALID": "MODEL_INVALID : les donnees ou le modele transmis au solveur sont invalides.",
    }
    output("- " + explanations.get(status, f"{status} : statut solveur non documente par l'assistant."))


def _read_csv_rows(path: Path, required_columns: list[str]) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        raise GuidedRunError(f"Fichier introuvable: {path}.")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise GuidedRunError(f"Fichier CSV vide ou sans en-tete: {path}.")
        missing = [column for column in required_columns if column not in reader.fieldnames]
        if missing:
            raise GuidedRunError(f"Colonnes manquantes dans {path}: {', '.join(missing)}.")
        return [dict(row) for row in reader], list(reader.fieldnames)


def _write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_diagonal_report(report: DiagonalFixReport) -> None:
    report.report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "communes_checked": report.communes_checked,
        "missing_added": report.missing_added,
        "non_zero_found": report.non_zero_found,
        "non_zero_corrected": report.non_zero_corrected,
        "duplicate_diagonal_rows": report.duplicate_diagonal_rows,
    }
    report.report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _clean_id(value: Any) -> str:
    return str(value).strip()


def _minutes_value(value: Any) -> int | None:
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None
