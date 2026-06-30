from __future__ import annotations

from pathlib import Path

from travel_times.io_ods import InputValidationError, read_cities_ods
from travel_times.models import CityInput


def validate_input_file(path: Path, sheet_name: str | int | None = None) -> list[CityInput]:
    try:
        return read_cities_ods(path, sheet_name=sheet_name)
    except InputValidationError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise InputValidationError([f"Impossible de lire le fichier ODS {path}: {exc}"]) from exc
