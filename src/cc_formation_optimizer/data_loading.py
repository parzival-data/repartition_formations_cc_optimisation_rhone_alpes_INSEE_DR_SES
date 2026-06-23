"""Chargement des donnees d'entree."""

from __future__ import annotations

from pathlib import Path

from cc_formation_optimizer.config import OptimizerConfig
from cc_formation_optimizer.domain import Commune, TravelTime


def load_communes(config: OptimizerConfig, base_dir: Path | None = None) -> list[Commune]:
    """Charge les communes depuis le fichier configure.

    L'implementation complete sera ajoutee lorsque le format exact des fichiers
    source sera stabilise.
    """

    raise NotImplementedError("Le chargement complet des communes sera implemente dans une etape suivante.")


def load_travel_times(config: OptimizerConfig, base_dir: Path | None = None) -> list[TravelTime]:
    """Charge les temps de trajet depuis le fichier configure."""

    raise NotImplementedError("Le chargement complet des trajets sera implemente dans une etape suivante.")
