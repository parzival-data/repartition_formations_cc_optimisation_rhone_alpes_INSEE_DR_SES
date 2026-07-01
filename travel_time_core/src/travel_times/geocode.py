"""Client de geocodage des communes via geo.api.gouv.fr."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from travel_times.config import GeocodeSettings
from travel_times.models import GeocodeResult

LOGGER = logging.getLogger(__name__)


class RateLimiter:
    """Limiteur simple d'appels successifs.

    Parameters
    ----------
    rate_per_sec : float
        Nombre maximal d'appels par seconde. Une valeur nulle ou negative
        desactive l'attente.
    """

    def __init__(self, rate_per_sec: float) -> None:
        self.min_interval = 0.0 if rate_per_sec <= 0 else 1.0 / rate_per_sec
        self._last_call = 0.0

    def wait(self) -> None:
        """Attend le delai necessaire avant l'appel suivant."""

        if self.min_interval <= 0:
            return
        now = time.monotonic()
        remaining = self.min_interval - (now - self._last_call)
        if remaining > 0:
            time.sleep(remaining)
        self._last_call = time.monotonic()


class GeoApiGouvClient:
    """Client HTTP de geocodage des communes.

    Parameters
    ----------
    settings : GeocodeSettings
        Parametres d'URL, timeout et cadence.
    client : httpx.Client | None, default=None
        Client HTTP injectable pour les tests.
    rate_limiter : RateLimiter | None, default=None
        Limiteur d'appels injectable.
    """

    def __init__(
        self,
        settings: GeocodeSettings,
        *,
        client: httpx.Client | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self.settings = settings
        self.client = client or httpx.Client(timeout=settings.timeout_sec)
        self.rate_limiter = rate_limiter or RateLimiter(settings.rate_limit_per_sec)

    def geocode_insee(self, insee_code: str) -> GeocodeResult:
        """Geocode une commune par son code.

        Parameters
        ----------
        insee_code : str
            Code commune a geocoder.

        Returns
        -------
        GeocodeResult
            Resultat normalise. Les erreurs HTTP et timeouts sont convertis en
            statuts d'erreur.
        """

        self.rate_limiter.wait()
        try:
            response = self.client.get(
                f"{self.settings.base_url.rstrip('/')}/communes",
                params={
                    "code": insee_code,
                    "fields": "nom,code,centre,mairie,bbox,population,codeDepartement,codeRegion",
                    "format": "json",
                },
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            return GeocodeResult(insee_code=insee_code, status="error", error=f"timeout: {exc}")
        except httpx.HTTPStatusError as exc:
            return GeocodeResult(
                insee_code=insee_code,
                status="error",
                error=f"http {exc.response.status_code}: {exc.response.text[:300]}",
            )
        except httpx.HTTPError as exc:
            return GeocodeResult(insee_code=insee_code, status="error", error=str(exc))
        return parse_geo_api_response(insee_code, response.json())


def parse_geo_api_response(insee_code: str, payload: Any) -> GeocodeResult:
    """Parse la reponse JSON de geo.api.gouv.fr.

    Parameters
    ----------
    insee_code : str
        Code commune demande.
    payload : Any
        Reponse JSON deja decodee.

    Returns
    -------
    GeocodeResult
        Resultat de geocodage normalise.
    """

    if not isinstance(payload, list) or not payload:
        LOGGER.warning("Commune INSEE %s non trouvee par geo.api.gouv.fr", insee_code)
        return GeocodeResult(insee_code=insee_code, status="not_found", error="commune not found")
    item = payload[0]
    if not isinstance(item, dict):
        return GeocodeResult(insee_code=insee_code, status="error", error="invalid response item")

    mairie = _extract_lon_lat(item.get("mairie"))
    if mairie is not None:
        lon, lat = mairie
        source = "mairie"
    else:
        centre = _extract_lon_lat(item.get("centre"))
        if centre is None:
            return GeocodeResult(insee_code=insee_code, status="not_found", error="no coordinates")
        lon, lat = centre
        source = "centre"

    return GeocodeResult(
        insee_code=str(item.get("code") or insee_code),
        status="ok",
        lat=lat,
        lon=lon,
        coord_source=source,
        population=_optional_int(item.get("population")),
        department_code=_optional_str(item.get("codeDepartement")),
        region_code=_optional_str(item.get("codeRegion")),
    )


def _extract_lon_lat(value: Any) -> tuple[float, float] | None:
    if not value:
        return None
    if isinstance(value, dict):
        if (
            "coordinates" in value
            and isinstance(value["coordinates"], list)
            and len(value["coordinates"]) >= 2
        ):
            return float(value["coordinates"][0]), float(value["coordinates"][1])
        if "lon" in value and "lat" in value:
            return float(value["lon"]), float(value["lat"])
        if "longitude" in value and "latitude" in value:
            return float(value["longitude"]), float(value["latitude"])
        geometry = value.get("geometry")
        if isinstance(geometry, dict):
            return _extract_lon_lat(geometry)
    if isinstance(value, list) and len(value) >= 2:
        return float(value[0]), float(value[1])
    return None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
