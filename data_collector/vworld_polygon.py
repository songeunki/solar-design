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

def _outer_ring(feature: dict) -> list | None:
    """GeoJSON feature에서 외곽 링 좌표([[lng,lat],...]) 추출.
    MultiPolygon은 가장 긴 외곽 링 반환.
    """
    try:
        geom  = feature["geometry"]
        gtype = geom.get("type", "")
        raw   = geom["coordinates"]
        if gtype == "Polygon":
            return raw[0]
        if gtype == "MultiPolygon":
            # 좌표 수가 가장 많은 외곽 링 (가장 복잡한 polygon = 본체)
            return max((part[0] for part in raw if part), key=len)
    except Exception:
        pass
    return None


def _centroid(feature: dict) -> tuple[float, float]:
    ring = _outer_ring(feature)
    if not ring:
        return 0.0, 0.0
    try:
        lons = [c[0] for c in ring]
        lats = [c[1] for c in ring]
        return sum(lons) / len(lons), sum(lats) / len(lats)
    except Exception:
        return 0.0, 0.0


def _bbox_area(feature: dict) -> float:
    """외곽 링 bounding box 넓이 (상대 크기 비교용)."""
    ring = _outer_ring(feature)
    if not ring:
        return 0.0
    try:
        lons = [c[0] for c in ring]
        lats = [c[1] for c in ring]
        return (max(lons) - min(lons)) * (max(lats) - min(lats))
    except Exception:
        return 0.0


def _point_in_ring(lng: float, lat: float, ring: list) -> bool:
    """Ray-casting Point-in-Polygon. ring: [[lng, lat], ...]"""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and \
                (lng < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _contains_point(feature: dict, lat: float, lng: float) -> bool:
    """Feature의 어떤 polygon이라도 (lat, lng)를 내부에 포함하면 True."""
    try:
        geom  = feature["geometry"]
        gtype = geom.get("type", "")
        raw   = geom["coordinates"]
        if gtype == "Polygon":
            rings = [raw[0]]
        elif gtype == "MultiPolygon":
            rings = [part[0] for part in raw if part]
        else:
            return False
        return any(_point_in_ring(lng, lat, ring) for ring in rings)
    except Exception:
        return False


def _best_feature(features: list[dict], lat: float, lng: float) -> dict | None:
    """분석 대상 건물 polygon 선택.

    1차: Point-in-Polygon 통과 feature 중 가장 큰 것 (bounding box 기준)
    2차: PIP 통과 없으면 centroid 거리 기준 가장 가까운 것
    """
    if not features:
        return None

    pip = [f for f in features if _contains_point(f, lat, lng)]
    if pip:
        chosen = max(pip, key=_bbox_area)
        logger.debug(
            "V-World PIP 매칭: %d/%d개 → bbox_area=%.2e  centroid_dist=%.1fm",
            len(pip), len(features), _bbox_area(chosen),
            math.hypot(
                (_centroid(chosen)[0] - lng) * _M_PER_DEG,
                (_centroid(chosen)[1] - lat) * _M_PER_DEG,
            ),
        )
        return chosen

    # PIP 없음 → centroid 거리 fallback
    logger.debug("V-World PIP 매칭 없음 → centroid 거리 fallback")
    return min(
        features,
        key=lambda f: math.hypot(
            _centroid(f)[0] - lng,
            _centroid(f)[1] - lat,
        ),
    )


def _to_coords(feature: dict) -> list[tuple[float, float]] | None:
    """GeoJSON feature → [(lng, lat), ...] 외곽 링. 실패 시 None."""
    ring = _outer_ring(feature)
    if not ring or len(ring) < 3:
        return None
    return [(float(c[0]), float(c[1])) for c in ring]


def _metrics_from_coords(
    coords: list[tuple[float, float]],
) -> tuple[float | None, float, float, float]:
    """coords → (area_m2, azimuth_deg, ew_m, ns_m)."""
    from data_collector.building_api import _polygon_area_m2, _azimuth_from_polygon
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    lat0    = sum(lats) / len(lats)
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
        coords: [(lng, lat), ...]  — OSM fallback 형식과 동일
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

    # ── 1차: PIP 매칭 레이어 우선 (cbnd → building 순) ─────────────────────
    all_features: list[tuple[str, dict]] = []
    for key in ("cbnd", "building"):
        layer = data.get(key)
        if not layer:
            continue
        features = layer.get("features", [])
        all_features.extend((key, f) for f in features)

        # 이 레이어에서 PIP 통과 feature가 있으면 바로 사용
        pip = [f for f in features if _contains_point(f, lat, lng)]
        if pip:
            feature = max(pip, key=_bbox_area)
            coords  = _to_coords(feature)
            if coords and len(coords) >= 3:
                area, azimuth, ew_m, ns_m = _metrics_from_coords(coords)
                logger.info(
                    "V-World 프록시 PIP [%s]: %d pts  area=%.1f㎡  az=%.1f°",
                    key, len(coords), area or 0, azimuth,
                )
                return (round(area, 1) if area and area > 5 else None), azimuth, ew_m, ns_m, coords

    # ── 2차: 모든 레이어에 PIP 없음 → centroid 거리 fallback ────────────────
    if all_features:
        logger.debug("V-World PIP 매칭 없음 → centroid fallback (전체 %d개)", len(all_features))
        _, feature = min(
            all_features,
            key=lambda kf: math.hypot(
                _centroid(kf[1])[0] - lng,
                _centroid(kf[1])[1] - lat,
            ),
        )
        coords = _to_coords(feature)
        if coords and len(coords) >= 3:
            area, azimuth, ew_m, ns_m = _metrics_from_coords(coords)
            logger.info(
                "V-World 프록시 centroid fallback: %d pts  area=%.1f㎡",
                len(coords), area or 0,
            )
            return (round(area, 1) if area and area > 5 else None), azimuth, ew_m, ns_m, coords

    logger.debug("V-World 프록시: features 없음 lat=%.6f lng=%.6f", lat, lng)
    return None, None, None, None, None
