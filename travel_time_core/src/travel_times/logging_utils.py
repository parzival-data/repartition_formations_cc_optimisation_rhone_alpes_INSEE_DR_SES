"""Configuration du logging pour la CLI de calcul de trajets."""

from __future__ import annotations

import logging


def configure_logging(verbose: bool = False) -> None:
    """Configure le logging console.

    Parameters
    ----------
    verbose : bool, default=False
        Active le niveau ``DEBUG`` au lieu de ``INFO``.
    """

    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        datefmt="%H:%M:%S",
    )
