"""Calculs de distances geographiques."""

from __future__ import annotations

import math


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcule la distance a vol d'oiseau entre deux coordonnees.

    Parameters
    ----------
    lat1 : float
        Latitude du premier point.
    lon1 : float
        Longitude du premier point.
    lat2 : float
        Latitude du second point.
    lon2 : float
        Longitude du second point.

    Returns
    -------
    float
        Distance haversine en kilometres.
    """

    radius_km = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * radius_km * math.atan2(math.sqrt(a), math.sqrt(1 - a))
