"""Validation des fichiers d'entree ODS de communes."""

from __future__ import annotations

from pathlib import Path

from travel_times.io_ods import InputValidationError, read_cities_ods
from travel_times.models import CityInput


def validate_input_file(path: Path, sheet_name: str | int | None = None) -> list[CityInput]:
    """Valide et lit un fichier ODS de communes.

    Parameters
    ----------
    path : Path
        Chemin du fichier ODS.
    sheet_name : str | int | None, default=None
        Feuille a lire.

    Returns
    -------
    list[CityInput]
        Communes valides extraites du fichier.

    Raises
    ------
    InputValidationError
        Si le fichier ne peut pas etre lu ou contient des donnees invalides.
    """

    try:
        return read_cities_ods(path, sheet_name=sheet_name)
    except InputValidationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise InputValidationError([f"Impossible de lire le fichier ODS {path}: {exc}"]) from exc
