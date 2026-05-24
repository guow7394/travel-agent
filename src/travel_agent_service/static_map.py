import math
import os
from typing import Iterable, List, Optional
from urllib.parse import quote, urlencode

from .models import Location, RouteStop


def haversine_meters(a: Location, b: Location) -> int:
    radius_m = 6_371_000
    lat1 = math.radians(a.latitude)
    lat2 = math.radians(b.latitude)
    dlat = math.radians(b.latitude - a.latitude)
    dlon = math.radians(b.longitude - a.longitude)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return int(2 * radius_m * math.asin(math.sqrt(h)))


def expanded_route_distance_meters(a: Location, b: Location) -> int:
    return int(haversine_meters(a, b) * 1.25)


def build_static_map_url(
    route: List[RouteStop],
    start_location: Location,
    end_location: Location,
    amap_key: Optional[str],
    public_base_url: Optional[str] = None,
) -> str:
    points = [start_location] + [stop.location for stop in route] + [end_location]
    labels = ["起"] + [str(index + 1) for index in range(len(route))] + ["终"]
    if amap_key:
        center = _center(points)
        marker_parts = [
            f"mid,,{labels[index]}:{point.longitude:.6f},{point.latitude:.6f}"
            for index, point in enumerate(points[:10])
        ]
        path_points = ";".join(f"{point.longitude:.6f},{point.latitude:.6f}" for point in points)
        params = {
            "location": f"{center.longitude:.6f},{center.latitude:.6f}",
            "zoom": "12",
            "size": "1024*620",
            "scale": "2",
            "markers": "|".join(marker_parts),
            "paths": f"5,0x2F80ED,0.9,,0:{path_points}",
            "key": amap_key,
        }
        return f"https://restapi.amap.com/v3/staticmap?{urlencode(params)}"

    base_url = (public_base_url or os.getenv("PUBLIC_BASE_URL") or "http://localhost:8000").rstrip("/")
    point_param = "|".join(f"{point.longitude:.6f},{point.latitude:.6f}" for point in points)
    label_param = "|".join(labels)
    query = urlencode({"points": point_param, "labels": label_param})
    return f"{base_url}/mock/static-map.svg?{query}"


def render_mock_static_map_svg(points_raw: str, labels_raw: str) -> str:
    points = _parse_points(points_raw)
    labels = labels_raw.split("|") if labels_raw else [str(i + 1) for i in range(len(points))]
    width = 1024
    height = 620
    padding = 70
    projected = _project(points, width, height, padding)
    polyline = " ".join(f"{x},{y}" for x, y in projected)
    markers = []
    for index, (x, y) in enumerate(projected):
        label = labels[index] if index < len(labels) else str(index + 1)
        markers.append(
            f'<circle cx="{x}" cy="{y}" r="17" fill="#2563eb" stroke="#fff" stroke-width="4" />'
            f'<text x="{x}" y="{y + 5}" text-anchor="middle" font-size="15" '
            f'font-family="Arial" fill="#fff" font-weight="700">{_escape(label)}</text>'
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="620" viewBox="0 0 1024 620">'
        '<rect width="1024" height="620" fill="#f6f1e8" />'
        '<path d="M0 510 C220 455 285 558 480 510 S760 425 1024 470" '
        'fill="none" stroke="#c8d7c5" stroke-width="34" opacity="0.65" />'
        '<path d="M-20 180 C160 145 270 205 420 170 S715 84 1044 135" '
        'fill="none" stroke="#cbd5e1" stroke-width="24" opacity="0.75" />'
        '<rect x="54" y="44" width="916" height="532" rx="24" fill="none" '
        'stroke="#334155" stroke-width="2" opacity="0.18" />'
        f'<polyline points="{polyline}" fill="none" stroke="#ef4444" stroke-width="7" '
        'stroke-linecap="round" stroke-linejoin="round" />'
        f'{"".join(markers)}'
        '<text x="64" y="88" font-size="30" font-family="Arial" fill="#0f172a" '
        'font-weight="700">Travel Agent Mock Static Map</text>'
        '<text x="64" y="120" font-size="18" font-family="Arial" fill="#475569">'
        'AMap key is not configured; this deterministic SVG keeps the demo runnable.</text>'
        "</svg>"
    )


def encode_svg_data_url(svg: str) -> str:
    return "data:image/svg+xml;utf8," + quote(svg)


def _center(points: Iterable[Location]) -> Location:
    points = list(points)
    return Location(
        longitude=sum(point.longitude for point in points) / len(points),
        latitude=sum(point.latitude for point in points) / len(points),
    )


def _parse_points(raw: str) -> List[Location]:
    points = []
    for chunk in raw.split("|"):
        if not chunk or "," not in chunk:
            continue
        lon, lat = chunk.split(",", 1)
        points.append(Location(longitude=float(lon), latitude=float(lat)))
    if not points:
        points.append(Location(longitude=121.473701, latitude=31.230416))
    return points


def _project(points: List[Location], width: int, height: int, padding: int):
    min_lon = min(point.longitude for point in points)
    max_lon = max(point.longitude for point in points)
    min_lat = min(point.latitude for point in points)
    max_lat = max(point.latitude for point in points)
    lon_span = max(max_lon - min_lon, 0.001)
    lat_span = max(max_lat - min_lat, 0.001)
    projected = []
    for point in points:
        x = padding + (point.longitude - min_lon) / lon_span * (width - padding * 2)
        y = height - padding - (point.latitude - min_lat) / lat_span * (height - padding * 2)
        projected.append((round(x, 1), round(y, 1)))
    return projected


def _escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

