"""V-World WFS API로 건물 footprint polygon 조회.

엔드포인트: https://api.vworld.kr/req/wfs
레이어 시도 순서:
  1) lp_pa_cbnd_bubun  — 건물 부분경계 (더 정밀)
  2) lt_c_bldginfo     — 건물 정보

환경변수 VWORLD_API_KEY: 주소 좌표 조회와 동일한 키 사용.
"""
from __future__ import annotations
import logging
import math

import requests

logger = logging.getLogger(__name__)

_WFS_URL   = "https://api.vworld.kr/req/wfs"
_BBOX_DEG  = 0.0005          # ≈ 55m — 단일 건물 조회에 충분
_M_PER_DEG = 111_320

_LAYERS = [
    "lp_pa_cbnd_bubun",  # 건물 부분경계 (GIS 기반)
    "lt_c_bldginfo",     # 건물 정보 (속성 + 형상)
]


# ── 내부 헬퍼 ────────────────────────────────────────────────────────────────

def _centroid(feature: dict) -> tuple[float, float]:
    """Feature 외곽 링의 무게중심 (lon, lat) 반환."""
    try:
        raw  = feature["geometry"]["coordinates"]
        ring = raw[0] if isinstance(raw[0][0], (list, tuple)) else raw
        lons = [c[0] for c in ring]
        lats = [c[1] for c in ring]
        return sum(lons) / len(lons), sum(lats) / len(lats)
    except Exception:
        return 0.0, 0.0


def _closest_feature(features: list[dict], lat: float, lng: float) -> dict | None:
    """조회 좌표에 무게중심이 가장 가까운 feature 반환."""
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
    """GeoJSON feature → [(lon, lat), ...] 외곽 링 좌표. 실패 시 None."""
    try:
        geom = feature["geometry"]
        gtype = geom.get("type", "")
        raw   = geom["coordinates"]

        if gtype == "Polygon":
            ring = raw[0]
        elif gtype == "MultiPolygon":
            # 좌표 수가 가장 많은 외곽 링 선택
            ring = max((part[0] for part in raw if part), key=len)
        else:
            return None

        if len(ring) < 3:
            return None
        return [(float(c[0]), float(c[1])) for c in ring]
    except Exception:
        return None


# ── 공개 API ─────────────────────────────────────────────────────────────────

def get_building_polygon(
    lat: float,
    lng: float,
    api_key: str = "",
) -> tuple[float | None, float | None, float | None, float | None, list | None]:
    """V-World WFS로 건물 footprint polygon 조회.

    Args:
        lat, lng: 건물 내부 위경도
        api_key: VWORLD_API_KEY. 빈 문자열이면 config에서 자동 로드.

    Returns:
        (area_m2|None, azimuth_deg|None, ew_m|None, ns_m|None, coords|None)
        coords: [(lon, lat), ...] — OSM _building_info_from_osm 반환 형식 호환
        모두 None이면 조회 실패 (caller가 OSM fallback 처리)
    """
    if not api_key:
        from config import VWORLD_API_KEY
        api_key = VWORLD_API_KEY

    if not api_key:
        logger.debug("VWORLD_API_KEY 미설정 — V-World WFS 건너뜀")
        return None, None, None, None, None

    bbox = (
        f"{lng - _BBOX_DEG},{lat - _BBOX_DEG},"
        f"{lng + _BBOX_DEG},{lat + _BBOX_DEG}"
    )

    for typename in _LAYERS:
        try:
            resp = requests.get(
                _WFS_URL,
                params={
                    "KEY":          api_key,
                    "SERVICE":      "WFS",
                    "REQUEST":      "GetFeature",
                    "TYPENAME":     typename,
                    "BBOX":         bbox,
                    "SRSNAME":      "EPSG:4326",
                    "OUTPUTFORMAT": "application/json",
                    "MAXFEATURES":  10,
                },
                timeout=10,
            )
            resp.raise_for_status()

            data = resp.json()
            features = data.get("features", [])
            if not features:
                logger.debug("V-World WFS %s: features 없음", typename)
                continue

            feature = _closest_feature(features, lat, lng)
            if feature is None:
                continue

            coords = _to_coords(feature)
            if not coords or len(coords) < 3:
                logger.debug("V-World WFS %s: coords %s개 부족", typename, len(coords or []))
                continue

            # 면적 + 바운딩박스 + 방위각 계산
            from data_collector.building_api import _polygon_area_m2, _azimuth_from_polygon
            area  = _polygon_area_m2(coords)
            lons_ = [c[0] for c in coords]
            lats_ = [c[1] for c in coords]
            lat0  = sum(lats_) / len(lats_)
            ew_m  = round((max(lons_) - min(lons_)) * _M_PER_DEG * math.cos(math.radians(lat0)), 1)
            ns_m  = round((max(lats_) - min(lats_)) * _M_PER_DEG, 1)
            azimuth = _azimuth_from_polygon(coords)

            logger.info(
                "V-World WFS %s: %d pts  area=%.1f㎡  az=%.1f°  EW=%.1fm  NS=%.1fm",
                typename, len(coords), area or 0, azimuth, ew_m, ns_m,
            )
            return (round(area, 1) if area and area > 5 else None), azimuth, ew_m, ns_m, coords

        except Exception as exc:
            logger.warning("V-World WFS 오류 (layer=%s): %s", typename, exc)
            continue

    logger.debug("V-World WFS: 모든 레이어 실패 lat=%.6f lng=%.6f", lat, lng)
    return None, None, None, None, None
