from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx

from travel_times.config import IgnSettings
from travel_times.geocode import RateLimiter
from travel_times.models import CityRecord, RouteResult

LOGGER = logging.getLogger(__name__)


class IgnRouteClient:
    def __init__(
        self,
        settings: IgnSettings,
        *,
        client: httpx.Client | None = None,
        rate_limiter: RateLimiter | None = None,
        raw_response_dir: Path | None = None,
    ) -> None:
        self.settings = settings
        self.client = client or httpx.Client(timeout=settings.timeout_sec)
        self.rate_limiter = rate_limiter or RateLimiter(settings.rate_limit_per_sec)
        self.raw_response_dir = raw_response_dir

    def route(
        self,
        origin: CityRecord,
        destination: CityRecord,
        *,
        requested_by_user: bool = False,
    ) -> RouteResult:
        if (
            origin.lat is None
            or origin.lon is None
            or destination.lat is None
            or destination.lon is None
        ):
            return RouteResult(
                origin_insee=origin.insee_code,
                destination_insee=destination.insee_code,
                route_status="skipped",
                api_error="missing origin or destination coordinates",
                requested_by_user=requested_by_user,
                resource=self.settings.resource,
            )
        payload = self._build_payload(origin, destination)
        headers = {"Content-Type": "application/json"}
        if self.settings.api_key:
            headers["Authorization"] = f"Bearer {self.settings.api_key}"

        last_error = ""
        for attempt in range(1, self.settings.max_retries + 1):
            self.rate_limiter.wait()
            try:
                response = self.client.post(
                    self.settings.route_url,
                    json=payload,
                    headers=headers,
                    timeout=self.settings.timeout_sec,
                )
                if self.settings.debug_raw_responses:
                    self._write_raw_response(
                        origin.insee_code,
                        destination.insee_code,
                        response.text,
                    )
                if response.status_code >= 500 and attempt < self.settings.max_retries:
                    last_error = f"http {response.status_code}: {response.text[:300]}"
                    time.sleep(self.settings.backoff_initial_sec * (2 ** (attempt - 1)))
                    continue
                if response.status_code >= 400:
                    return RouteResult(
                        origin_insee=origin.insee_code,
                        destination_insee=destination.insee_code,
                        route_status="http_error",
                        api_status_code=response.status_code,
                        api_error=response.text[:1000],
                        requested_by_user=requested_by_user,
                        resource=self.settings.resource,
                    )
                parsed = parse_ign_route_response(response.json())
                return RouteResult(
                    origin_insee=origin.insee_code,
                    destination_insee=destination.insee_code,
                    route_status=parsed["route_status"],
                    duration_sec=parsed.get("duration_sec"),
                    distance_m=parsed.get("distance_m"),
                    api_status_code=response.status_code,
                    api_error=parsed.get("api_error"),
                    requested_by_user=requested_by_user,
                    resource=self.settings.resource,
                )
            except httpx.TimeoutException as exc:
                last_error = f"timeout: {exc}"
                if attempt < self.settings.max_retries:
                    time.sleep(self.settings.backoff_initial_sec * (2 ** (attempt - 1)))
                    continue
                return RouteResult(
                    origin_insee=origin.insee_code,
                    destination_insee=destination.insee_code,
                    route_status="timeout",
                    api_error=last_error,
                    requested_by_user=requested_by_user,
                    resource=self.settings.resource,
                )
            except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
                last_error = str(exc)
                if attempt < self.settings.max_retries:
                    time.sleep(self.settings.backoff_initial_sec * (2 ** (attempt - 1)))
                    continue
                status = (
                    "parse_error"
                    if isinstance(exc, (json.JSONDecodeError, ValueError))
                    else "error"
                )
                return RouteResult(
                    origin_insee=origin.insee_code,
                    destination_insee=destination.insee_code,
                    route_status=status,
                    api_error=last_error,
                    requested_by_user=requested_by_user,
                    resource=self.settings.resource,
                )

        return RouteResult(
            origin_insee=origin.insee_code,
            destination_insee=destination.insee_code,
            route_status="error",
            api_error=last_error or "unknown error",
            requested_by_user=requested_by_user,
            resource=self.settings.resource,
        )

    def _build_payload(self, origin: CityRecord, destination: CityRecord) -> dict[str, Any]:
        return {
            "resource": self.settings.resource,
            "profile": self.settings.profile,
            "optimization": self.settings.optimization,
            "start": f"{origin.lon},{origin.lat}",
            "end": f"{destination.lon},{destination.lat}",
            "distanceUnit": self.settings.distance_unit,
            "timeUnit": self.settings.time_unit,
            "crs": self.settings.crs,
            "getSteps": self.settings.get_steps,
            "getBbox": self.settings.get_bbox,
        }

    def _write_raw_response(self, origin: str, destination: str, text: str) -> None:
        if self.raw_response_dir is None:
            return
        self.raw_response_dir.mkdir(parents=True, exist_ok=True)
        safe_name = f"{origin}_{destination}_{int(time.time() * 1000)}.json"
        (self.raw_response_dir / safe_name).write_text(text, encoding="utf-8")


def parse_ign_route_response(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"route_status": "parse_error", "api_error": "response is not a JSON object"}

    explicit_error = _find_first_key(payload, {"error", "message", "detail"})
    duration = _find_numeric_by_keys(
        payload,
        {"duration", "duration_sec", "totalDuration", "time", "time_sec"},
    )
    distance = _find_numeric_by_keys(payload, {"distance", "distance_m", "totalDistance", "length"})

    if duration is None and distance is None:
        if explicit_error is not None:
            return {"route_status": "no_route", "api_error": str(explicit_error)}
        return {"route_status": "no_route", "api_error": "no duration or distance found"}

    return {
        "route_status": "ok",
        "duration_sec": int(round(duration)) if duration is not None else None,
        "distance_m": int(round(distance)) if distance is not None else None,
    }


def _find_numeric_by_keys(value: Any, keys: set[str]) -> float | None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in keys and isinstance(child, int | float):
                return float(child)
            if key in keys and isinstance(child, str):
                try:
                    return float(child)
                except ValueError:
                    continue
        for child in value.values():
            found = _find_numeric_by_keys(child, keys)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_numeric_by_keys(child, keys)
            if found is not None:
                return found
    return None


def _find_first_key(value: Any, keys: set[str]) -> Any | None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in keys and child:
                return child
        for child in value.values():
            found = _find_first_key(child, keys)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_first_key(child, keys)
            if found is not None:
                return found
    return None
