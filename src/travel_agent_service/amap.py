import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

import httpx

from .models import FoodRecommendation, Location, Place


AMAP_BASE_URL = "https://restapi.amap.com"


@dataclass
class AmapRoute:
    distance_m: int
    duration_min: int


class AmapClient:
    def __init__(self, key: Optional[str] = None, timeout_seconds: Optional[float] = None):
        self.key = key or os.getenv("AMAP_WEB_SERVICE_KEY") or os.getenv("AMAP_KEY")
        self.timeout_seconds = timeout_seconds or float(os.getenv("AMAP_TIMEOUT_SECONDS", "1.0"))

    @property
    def enabled(self) -> bool:
        return bool(self.key)

    def _get(self, path: str, params: dict) -> Optional[dict]:
        if not self.key:
            return None
        try:
            response = httpx.get(
                f"{AMAP_BASE_URL}{path}",
                params={"key": self.key, "output": "JSON", **params},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return None
        if payload.get("status") != "1":
            return None
        return payload

    def geocode(self, address: str, city: str) -> Optional[Place]:
        payload = self._get("/v3/geocode/geo", {"address": address, "city": city})
        if payload is None:
            return None

        geocodes = payload.get("geocodes") or []
        if not geocodes:
            return None
        raw_location = geocodes[0].get("location")
        if not raw_location or "," not in raw_location:
            return None
        lon, lat = raw_location.split(",", 1)
        return Place(
            name=address,
            location=Location(longitude=float(lon), latitude=float(lat)),
            default_stay_minutes=70,
            indoor_score=0.5,
            tags=["高德地理编码"],
        )

    def distance(self, origin: Location, destination: Location) -> Optional[Tuple[int, int]]:
        payload = self._get(
            "/v3/distance",
            {
                "origins": _format_location(origin),
                "destination": _format_location(destination),
                "type": 1,
            },
        )
        if payload is None:
            return None

        results = payload.get("results") or []
        if not results:
            return None
        distance_m = int(float(results[0].get("distance", 0)))
        duration_sec = int(float(results[0].get("duration", 0) or 0))
        duration_min = max(1, round(duration_sec / 60)) if duration_sec else 0
        return distance_m, duration_min

    def route(
        self,
        origin: Location,
        destination: Location,
        transport: str,
        city: str,
    ) -> Optional[AmapRoute]:
        if transport == "walk":
            return self.walking_route(origin, destination)
        if transport == "metro":
            return self.transit_route(origin, destination, city)
        if transport == "taxi":
            return self.driving_route(origin, destination)
        return None

    def walking_route(self, origin: Location, destination: Location) -> Optional[AmapRoute]:
        payload = self._get(
            "/v3/direction/walking",
            {"origin": _format_location(origin), "destination": _format_location(destination)},
        )
        return _parse_path_route(payload)

    def driving_route(self, origin: Location, destination: Location) -> Optional[AmapRoute]:
        payload = self._get(
            "/v3/direction/driving",
            {"origin": _format_location(origin), "destination": _format_location(destination)},
        )
        return _parse_path_route(payload)

    def transit_route(
        self,
        origin: Location,
        destination: Location,
        city: str,
    ) -> Optional[AmapRoute]:
        payload = self._get(
            "/v3/direction/transit/integrated",
            {
                "origin": _format_location(origin),
                "destination": _format_location(destination),
                "city": city,
                "strategy": "0",
            },
        )
        if not payload:
            return None
        transits = (payload.get("route") or {}).get("transits") or []
        if not transits:
            return None
        best = transits[0]
        return _build_route_result(best.get("distance"), best.get("duration"))

    def search_food_near(
        self,
        location: Location,
        near_stop: str,
        city: str,
        per_person_budget: float,
        radius_m: int = 1800,
    ) -> List[FoodRecommendation]:
        payload = self._get(
            "/v3/place/around",
            {
                "location": _format_location(location),
                "city": city,
                "radius": radius_m,
                "types": "050000",
                "keywords": "餐厅|小吃|本帮菜",
                "offset": 10,
                "page": 1,
                "extensions": "all",
            },
        )
        if not payload:
            return []
        recommendations = []
        for poi in payload.get("pois") or []:
            recommendation = _food_from_poi(poi, near_stop, per_person_budget)
            if recommendation:
                recommendations.append(recommendation)
        return recommendations


def _format_location(location: Location) -> str:
    return f"{location.longitude:.6f},{location.latitude:.6f}"


def _parse_path_route(payload: Optional[dict]) -> Optional[AmapRoute]:
    if not payload:
        return None
    paths = (payload.get("route") or {}).get("paths") or []
    if not paths:
        return None
    return _build_route_result(paths[0].get("distance"), paths[0].get("duration"))


def _build_route_result(distance, duration) -> Optional[AmapRoute]:
    try:
        distance_m = int(float(distance or 0))
        duration_sec = int(float(duration or 0))
    except (TypeError, ValueError):
        return None
    if distance_m <= 0 or duration_sec <= 0:
        return None
    return AmapRoute(distance_m=distance_m, duration_min=max(1, round(duration_sec / 60)))


def _food_from_poi(
    poi: dict,
    near_stop: str,
    per_person_budget: float,
) -> Optional[FoodRecommendation]:
    raw_location = poi.get("location")
    name = str(poi.get("name") or "").strip()
    if not name or not raw_location or "," not in raw_location:
        return None
    lon, lat = raw_location.split(",", 1)
    avg_price = _parse_price(((poi.get("biz_ext") or {}).get("cost")))
    if avg_price <= 0:
        avg_price = _fallback_food_price(per_person_budget)
    distance = poi.get("distance")
    distance_text = f"，距{near_stop}约{distance}米" if distance not in (None, "", []) else ""
    try:
        location = Location(longitude=float(lon), latitude=float(lat))
    except ValueError:
        return None
    return FoodRecommendation(
        name=name,
        near_stop=near_stop,
        avg_price_cny=avg_price,
        location=location,
        reason=f"高德周边餐饮POI{distance_text}，适合作为顺路用餐点。",
    )


def _parse_price(value) -> int:
    if value in (None, "", []):
        return 0
    try:
        return max(0, round(float(value)))
    except (TypeError, ValueError):
        return 0


def _fallback_food_price(per_person_budget: float) -> int:
    if per_person_budget < 120:
        return 45
    if per_person_budget < 220:
        return 80
    return 120
