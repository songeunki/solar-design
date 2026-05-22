"""V-World WFS polygon 조회 — Vercel 프록시 경유.

Vercel icn1의 /api/vworld-polygon 프록시가 V-World WFS를 호출하고
GeoJSON을 반환한다. Render 서버는 직접 V-World를 호출하지 않는다.

프록시 URL: VWORLD_PROXY_URL 환경변수 (기본값 하드코딩)
"""
from __future__ import annotations
import logging
import math
import os

import requests

logger = logging.getLogger(__name__)

_PROXY_URL = os.environ.get(
    "VWORLD_PROXY_URL",
    "https://solar-design-opal.vercel.app/api/vworld-polygon",
)
_M_PER_DEG = 111_320


# ── 내부 헬퍼 ────────────────────────────────────────────────────────────────

def _centroid(feature: dict) -> tuple[float, float]:
    try:
        raw  = feature["geometry"]["coordinates"]
        ring = raw[0] if isinstance(raw[0][0], (list, tuple)) else raw
        lons = [c[0] for c in ring]
        lats = [c[1] for c in ring]
        return sum(lons) / len(lons), sum(lats) / len(lats)
    except Exception:
        return 0.0, 0.0


def _closest_feature(features: list[dict], lat: float, lng: float) -> dict | None:
    if not features:
        return None
    return min(
        features,
        key=lambda f: math.hypot(
            _centroid(f)[0] - lng,
            _centroid(f)[1] - lat,
        ),
    )


def _to_coords(feature: dict) -> list[tuple[float, float]] | None:
    try:
        geom  = feature["geometry"]
        gtype = geom.get("type", "")
        raw   = geom["coordinates"]

        if gtype == "Polygon":
            ring = raw[0]
        elif gtype == "MultiPolygon":
            ring = max((part[0] for part in raw if part), key=len)
        else:
            return None

        if len(ring) < 3:
            return None
        return [(float(c[0]), float(c[1])) for c in ring]
    except Exception:
        return None


def _metrics_from_coords(
    coords: list[tuple[float, float]],
) -> tuple[float | None, float, float, float]:
    """coords → (area_m2, azimuth_deg, ew_m, ns_m)."""
    from data_collector.building_api import _polygon_area_m2, _azimuth_from_polygon
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    lat0 = sum(lats) / len(lats)
    area    = _polygon_area_m2(coords)
    ew_m    = round((max(lons) - min(lons)) * _M_PER_DEG * math.cos(math.radians(lat0)), 1)
    ns_m    = round((max(lats) - min(lats)) * _M_PER_DEG, 1)
    azimuth = _azimuth_from_polygon(coords)
    return area, azimuth, ew_m, ns_m


# ── 공개 API ─────────────────────────────────────────────────────────────────

def get_building_polygon(
    lat: float,
    lng: float,
    api_key: str = "",          # 프록시 방식에서는 미사용 (하위 호환 유지)
) -> tuple[float | None, float | None, float | None, float | None, list | None]:
    """Vercel 프록시 경유로 건물 footprint polygon 조회.

    Returns:
        (area_m2|None, azimuth_deg|None, ew_m|None, ns_m|None, coords|None)
        coords: [(lon, lat), ...]  — OSM fallback 형식과 동일
        모두 None이면 조회 실패 → caller가 OSM fallback 처리
    """
    try:
        resp = requests.get(
            _PROXY_URL,
            params={"lat": lat, "lng": lng, "layer": "both"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("V-World 프록시 호출 실패: %s", exc)
        return None, None, None, None, None

    if not data.get("success"):
        logger.debug("V-World 프록시 실패 응답: %s", data.get("error"))
        return None, None, None, None, None

    # cbnd 우선, 없으면 building 레이어
    for key in ("cbnd", "building"):
        layer = data.get(key)
        if not layer:
            continue
        features = layer.get("features", [])
        feature  = _closest_feature(features, lat, lng)
        if feature is None:
            continue
        coords = _to_coords(feature)
        if not coords or len(coords) < 3:
            continue

        area, azimuth, ew_m, ns_m = _metrics_from_coords(coords)
        logger.info(
            "V-World 프록시 [%s]: %d pts  area=%.1f㎡  az=%.1f°  EW=%.1fm  NS=%.1fm",
            key, len(coords), area or 0, azimuth, ew_m, ns_m,
        )
        return (round(area, 1) if area and area > 5 else None), azimuth, ew_m, ns_m, coords

    logger.debug("V-World 프록시: features 없음 lat=%.6f lng=%.6f", lat, lng)
    return None, None, None, None, None
