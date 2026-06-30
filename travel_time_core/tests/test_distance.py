from __future__ import annotations

from travel_times.distance import haversine_km


def test_haversine_same_point_is_zero() -> None:
    assert haversine_km(45.764, 4.8357, 45.764, 4.8357) == 0


def test_haversine_is_symmetric() -> None:
    lyon = (45.764, 4.8357)
    annecy = (45.8992, 6.1294)
    assert haversine_km(*lyon, *annecy) == haversine_km(*annecy, *lyon)


def test_haversine_lyon_annecy_approx() -> None:
    distance = haversine_km(45.764, 4.8357, 45.8992, 6.1294)
    assert 95 <= distance <= 110
