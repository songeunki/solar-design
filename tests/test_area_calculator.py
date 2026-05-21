"""analyzer/area_calculator.py 단위 테스트."""
import math
import pytest

from analyzer.area_calculator import calculate_polygon_area

# 서울 기준 미터→위경도 변환 상수
_LAT0 = 37.5
_LNG0 = 127.0
_M_PER_LAT = 111_320
_M_PER_LNG = _M_PER_LAT * math.cos(math.radians(_LAT0))  # ≈ 88 386 m/°


def _square(side_m: float, lat0: float = _LAT0, lng0: float = _LNG0) -> list[dict]:
    """정사각형 polygon 생성 (SW → SE → NE → NW)."""
    dlat = side_m / _M_PER_LAT
    dlng = side_m / _M_PER_LNG
    return [
        {"lat": lat0,         "lng": lng0        },
        {"lat": lat0,         "lng": lng0 + dlng },
        {"lat": lat0 + dlat,  "lng": lng0 + dlng },
        {"lat": lat0 + dlat,  "lng": lng0        },
    ]


def _rect(ns_m: float, ew_m: float, lat0: float = _LAT0, lng0: float = _LNG0) -> list[dict]:
    """직사각형 polygon 생성."""
    dlat = ns_m / _M_PER_LAT
    dlng = ew_m / _M_PER_LNG
    return [
        {"lat": lat0,         "lng": lng0        },
        {"lat": lat0,         "lng": lng0 + dlng },
        {"lat": lat0 + dlat,  "lng": lng0 + dlng },
        {"lat": lat0 + dlat,  "lng": lng0        },
    ]


# ── 정상 케이스 ──────────────────────────────────────────────────────────────

class TestValidPolygons:
    def test_10m_square_area(self):
        """10×10m 정사각형 → 100㎡ ± 0.5%."""
        result = calculate_polygon_area(_square(10.0))
        assert result["valid"] is True
        assert result["method"] == "shoelace_utm"
        assert abs(result["area_m2"] - 100.0) / 100.0 < 0.005

    def test_10m_square_returns_float(self):
        result = calculate_polygon_area(_square(10.0))
        assert isinstance(result["area_m2"], float)

    def test_rectangle_30x50(self):
        """30×50m 직사각형 → 1 500㎡ ± 0.5%."""
        result = calculate_polygon_area(_rect(30.0, 50.0))
        assert result["valid"] is True
        assert abs(result["area_m2"] - 1_500.0) / 1_500.0 < 0.005

    def test_rectangle_100x200(self):
        """100×200m → 20 000㎡ ± 0.5%."""
        result = calculate_polygon_area(_rect(100.0, 200.0))
        assert result["valid"] is True
        assert abs(result["area_m2"] - 20_000.0) / 20_000.0 < 0.005

    def test_triangle(self):
        """삼각형 (좌표 3개) — 최소 유효 케이스."""
        dlat = 10 / _M_PER_LAT
        dlng = 10 / _M_PER_LNG
        tri = [
            {"lat": _LAT0,         "lng": _LNG0        },
            {"lat": _LAT0,         "lng": _LNG0 + dlng },
            {"lat": _LAT0 + dlat,  "lng": _LNG0        },
        ]
        result = calculate_polygon_area(tri)
        assert result["valid"] is True
        # 직각삼각형 넓이 = 100/2 = 50㎡ ± 0.5%
        assert abs(result["area_m2"] - 50.0) / 50.0 < 0.005


# ── 실패 케이스 ──────────────────────────────────────────────────────────────

class TestInvalidPolygons:
    def test_empty_list(self):
        result = calculate_polygon_area([])
        assert result["valid"] is False
        assert result["area_m2"] == 0
        assert "error" in result

    def test_one_point(self):
        result = calculate_polygon_area([{"lat": 37.5, "lng": 127.0}])
        assert result["valid"] is False
        assert "error" in result

    def test_two_points(self):
        result = calculate_polygon_area([
            {"lat": 37.5,  "lng": 127.0},
            {"lat": 37.51, "lng": 127.0},
        ])
        assert result["valid"] is False
        assert "error" in result

    def test_missing_key(self):
        """lat/lng 키 없는 경우 → valid False."""
        result = calculate_polygon_area([
            {"x": 0, "y": 0},
            {"x": 1, "y": 0},
            {"x": 1, "y": 1},
        ])
        assert result["valid"] is False

    def test_returns_method_always(self):
        """실패 시에도 method 필드 존재."""
        result = calculate_polygon_area([])
        assert result["method"] == "shoelace_utm"
