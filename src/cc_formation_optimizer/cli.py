"""Interface en ligne de commande du projet."""

from __future__ import annotations

import argparse
from pathlib import Path

from cc_formation_optimizer.config import ConfigError, load_config


def build_parser() -> argparse.ArgumentParser:
    """Construit le parseur CLI."""

    parser = argparse.ArgumentParser(prog="cc-formation-optimizer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-config", help="Valide un fichier de configuration YAML.")
    validate.add_argument("--config", type=Path, default=Path("config/config_ear2027.yaml"))

    show = subparsers.add_parser("show-config", help="Affiche un resume de la configuration.")
    show.add_argument("--config", type=Path, default=Path("config/config_ear2027.yaml"))

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

    parser.error(f"Commande inconnue: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
