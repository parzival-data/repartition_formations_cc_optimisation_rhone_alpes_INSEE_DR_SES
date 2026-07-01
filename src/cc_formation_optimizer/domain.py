"""Objets metier partages par les modules du projet."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Commune:
    """Commune a affecter a une session.

    Attributes
    ----------
    commune_id : str
        Code de la commune.
    name : str
        Nom de la commune.
    population : int
        Population utilisee pour calculer le nombre de CC.
    category : str
        Categorie de commune, ``PC`` ou ``TPC``.
    territory_ear : str | None
        Territoire EAR de rattachement, si disponible.
    housing : int | None
        Nombre de logements, si disponible.
    latitude : float | None
        Latitude utilisee pour la carte, si disponible.
    longitude : float | None
        Longitude utilisee pour la carte, si disponible.
    """

    commune_id: str
    name: str
    population: int
    category: str
    territory_ear: str | None = None
    housing: int | None = None
    latitude: float | None = None
    longitude: float | None = None


@dataclass(frozen=True)
class TravelTime:
    """Temps de trajet oriente entre une commune et un pivot.

    Attributes
    ----------
    origin_id : str
        Code de la commune origine.
    destination_id : str
        Code de la commune destination candidate comme pivot.
    minutes : int
        Temps de trajet en minutes.
    """

    origin_id: str
    destination_id: str
    minutes: int


@dataclass(frozen=True)
class Compatibility:
    """Compatibilite metier orientee entre une commune et un pivot.

    Attributes
    ----------
    origin_id : str
        Code de la commune origine.
    destination_id : str
        Code du pivot cible.
    allowed : int
        Indicateur binaire, ``1`` si le rattachement est autorise.
    """

    origin_id: str
    destination_id: str
    allowed: int


@dataclass(frozen=True)
class FormationSlot:
    """Slot potentiel de formation ``(j, m)``.

    Attributes
    ----------
    pivot_id : str
        Code de la commune pivot.
    slot_index : int
        Rang du slot pour ce pivot.
    """

    pivot_id: str
    slot_index: int
