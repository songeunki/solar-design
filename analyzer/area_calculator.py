"""V-World 건물 polygon 위경도 좌표 → 실측 면적 계산.

변환 방식: EPSG:4326 (위경도) → EPSG:32652 (UTM Zone 52N, 한국)
면적 산정: Shoelace formula (Gauss's area formula)
"""
from __future__ import annotations

try:
    from pyproj import Transformer
    _TRANSFORMER = Transformer.from_crs("EPSG:4326", "EPSG:32652", always_xy=True)
    _PYPROJ_OK = True
except ImportError:
    _TRANSFORMER = None
    _PYPROJ_OK = False

_METHOD = "shoelace_utm"


def _shoelace(xs: list[float], ys: list[float]) -> float:
    """Shoelace formula → 부호 없는 면적(㎡)."""
    n = len(xs)
    acc = 0.0
    for i in range(n):
        j = (i + 1) % n
        acc += xs[i] * ys[j]
        acc -= xs[j] * ys[i]
    return abs(acc) / 2.0


def calculate_polygon_area(coordinates: list) -> dict:
    """위경도 polygon 좌표로 실측 면적 계산.

    Args:
        coordinates: [{"lat": float, "lng": float}, ...] 형식

    Returns:
        성공: {"area_m2": float, "method": "shoelace_utm", "valid": True}
        실패: {"area_m2": 0,     "method": "shoelace_utm", "valid": False, "error": str}
    """
    def _fail(reason: str) -> dict:
        return {"area_m2": 0, "method": _METHOD, "valid": False, "error": reason}

    if not coordinates:
        return _fail("빈 좌표 배열")
    if len(coordinates) < 3:
        return _fail(f"좌표 {len(coordinates)}개 — 면적 계산에는 최소 3개 필요")
    if not _PYPROJ_OK:
        return _fail("pyproj 패키지 미설치 — pip install pyproj")

    try:
        xs, ys = [], []
        for p in coordinates:
            x, y = _TRANSFORMER.transform(float(p["lng"]), float(p["lat"]))
            xs.append(x)
            ys.append(y)
    except (KeyError, TypeError, ValueError) as exc:
        return _fail(f"좌표 변환 실패: {exc}")

    area = _shoelace(xs, ys)
    if area <= 0:
        return _fail("계산된 면적이 0 이하 (좌표 오류 가능성)")

    return {"area_m2": round(area, 2), "method": _METHOD, "valid": True}
