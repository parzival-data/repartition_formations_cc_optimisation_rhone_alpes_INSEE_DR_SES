"""Objets metier partages par les modules du projet."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Commune:
    """Commune a affecter dans une formation."""

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
    """Temps de trajet oriente entre deux communes."""

    origin_id: str
    destination_id: str
    minutes: int


@dataclass(frozen=True)
class Compatibility:
    """Compatibilite metier orientee entre une commune et un pivot."""

    origin_id: str
    destination_id: str
    allowed: int


@dataclass(frozen=True)
class FormationSlot:
    """Slot potentiel de formation `(j,m)`."""

    pivot_id: str
    slot_index: int
