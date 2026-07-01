"""Lecture et ecriture ODS pour les communes et exports de trajets."""

from __future__ import annotations

import logging
import re
import unicodedata
from numbers import Real
from pathlib import Path
from typing import Any

from odf.opendocument import OpenDocumentSpreadsheet
from odf.table import Table, TableCell, TableRow
from odf.text import P
import pandas as pd

from travel_times.models import (
    COMMUNE_PC,
    COMMUNE_STANDARD,
    COMMUNE_TPC,
    CityInput,
    ColumnMapping,
)

LOGGER = logging.getLogger(__name__)

NAME_COLUMNS = {"nom", "ville", "nom_ville", "commune", "nom_commune"}
INSEE_COLUMNS = {"code_insee", "insee", "code", "code_commune"}
TYPE_COLUMNS = {"precision", "type", "type_commune", "categorie", "taille_commune"}


class InputValidationError(ValueError):
    """Erreur de validation d'un fichier d'entree.

    Parameters
    ----------
    errors : list[str]
        Messages d'erreur collectes pendant la validation.

    Attributes
    ----------
    errors : list[str]
        Messages d'erreur detailles.
    """

    def __init__(self, errors: list[str]) -> None:
        super().__init__("\n".join(errors))
        self.errors = errors


def _normalize_header(value: Any) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def detect_columns(df: pd.DataFrame) -> ColumnMapping:
    """Detecte les colonnes nom, code commune et type dans un tableau.

    Parameters
    ----------
    df : pd.DataFrame
        Donnees lues depuis l'ODS.

    Returns
    -------
    ColumnMapping
        Colonnes detectees.

    Raises
    ------
    InputValidationError
        Si les colonnes obligatoires nom ou code commune sont introuvables.
    """

    normalized = {_normalize_header(column): column for column in df.columns}
    name = next((normalized[key] for key in NAME_COLUMNS if key in normalized), None)
    insee = next((normalized[key] for key in INSEE_COLUMNS if key in normalized), None)
    commune_type = next((normalized[key] for key in TYPE_COLUMNS if key in normalized), None)
    errors: list[str] = []
    if name is None:
        errors.append(f"Colonne nom introuvable. Colonnes acceptees: {sorted(NAME_COLUMNS)}")
    if insee is None:
        errors.append(
            f"Colonne code INSEE introuvable. Colonnes acceptees: {sorted(INSEE_COLUMNS)}"
        )
    if errors:
        raise InputValidationError(errors)
    return ColumnMapping(
        name=str(name),
        insee_code=str(insee),
        commune_type=str(commune_type) if commune_type else None,
    )


def normalize_insee(value: Any) -> str:
    """Normalise un code commune lu depuis un tableur.

    Parameters
    ----------
    value : Any
        Valeur brute du code commune.

    Returns
    -------
    str
        Code nettoye, ou chaine vide si absent.
    """

    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    text = re.sub(r"\s+", "", text)
    return text


def normalize_commune_type(value: Any) -> str:
    """Normalise le type de commune.

    Parameters
    ----------
    value : Any
        Valeur brute de type.

    Returns
    -------
    str
        ``PC``, ``TPC`` ou ``STANDARD``.
    """

    if value is None or pd.isna(value):
        return COMMUNE_STANDARD
    text = str(value).strip().upper()
    if text in {"", "STD", "STANDARD"}:
        return COMMUNE_STANDARD
    if text in {COMMUNE_PC, COMMUNE_TPC}:
        return text
    LOGGER.warning("Type de commune non reconnu %r: utilisation de STANDARD", value)
    return COMMUNE_STANDARD


def read_cities_ods(path: Path, sheet_name: str | int | None = None) -> list[CityInput]:
    """Lit les communes d'un fichier ODS.

    Parameters
    ----------
    path : Path
        Chemin du fichier ODS.
    sheet_name : str | int | None, default=None
        Feuille a lire, ou premiere feuille par defaut.

    Returns
    -------
    list[CityInput]
        Communes valides.

    Raises
    ------
    InputValidationError
        Si le fichier est absent ou si les lignes contiennent des erreurs.
    """

    if not path.exists():
        raise InputValidationError([f"Fichier introuvable: {path}"])
    selected_sheet = 0 if sheet_name is None else sheet_name
    df = pd.read_excel(path, engine="odf", dtype=str, sheet_name=selected_sheet)
    mapping = detect_columns(df)
    rows: list[CityInput] = []
    errors: list[str] = []
    seen: dict[str, int] = {}
    for index, row in df.iterrows():
        line_no = index + 2
        name = "" if pd.isna(row[mapping.name]) else str(row[mapping.name]).strip()
        insee = normalize_insee(row[mapping.insee_code])
        commune_type = (
            normalize_commune_type(row[mapping.commune_type])
            if mapping.commune_type
            else COMMUNE_STANDARD
        )
        if not name:
            errors.append(f"Ligne {line_no}: nom de commune vide")
        if not insee:
            errors.append(f"Ligne {line_no}: code INSEE vide")
        if insee:
            if insee in seen:
                errors.append(
                    f"Ligne {line_no}: doublon du code INSEE {insee} "
                    f"deja vu ligne {seen[insee]}"
                )
            else:
                seen[insee] = line_no
        if name and insee:
            rows.append(CityInput(insee_code=insee, name=name, commune_type=commune_type))
    if errors:
        raise InputValidationError(errors)
    return rows


def write_ods(path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    """Ecrit un classeur ODS a partir de DataFrames.

    Parameters
    ----------
    path : Path
        Chemin du fichier ODS a ecrire.
    sheets : dict[str, pd.DataFrame]
        Feuilles a produire, indexees par nom.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    doc = OpenDocumentSpreadsheet()
    for sheet_name, df in sheets.items():
        table = Table(name=(sheet_name[:31] or "Sheet1"))
        _append_ods_row(table, list(df.columns))
        for row in df.itertuples(index=False, name=None):
            _append_ods_row(table, list(row))
        doc.spreadsheet.addElement(table)

    doc.save(str(tmp_path), addsuffix=False)
    tmp_path.replace(path)


def _append_ods_row(table: Table, values: list[Any]) -> None:
    row = TableRow()
    empty_run = 0
    for value in values:
        if _is_empty_cell(value):
            empty_run += 1
            continue
        if empty_run:
            row.addElement(TableCell(numbercolumnsrepeated=empty_run))
            empty_run = 0
        row.addElement(_ods_cell(value))
    if empty_run:
        row.addElement(TableCell(numbercolumnsrepeated=empty_run))
    table.addElement(row)


def _ods_cell(value: Any) -> TableCell:
    if isinstance(value, bool):
        cell = TableCell(valuetype="boolean", booleanvalue=str(value).lower())
        cell.addElement(P(text="TRUE" if value else "FALSE"))
        return cell
    if isinstance(value, Real):
        cell = TableCell(valuetype="float", value=float(value))
        cell.addElement(P(text=str(value)))
        return cell
    text = str(value)
    cell = TableCell(valuetype="string")
    cell.addElement(P(text=text))
    return cell


def _is_empty_cell(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value == ""
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False
