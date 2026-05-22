"""data_collector/vworld_polygon.py 단위 테스트 (mock 기반, API 키 불필요)."""
from unittest.mock import patch, MagicMock
import pytest

from data_collector.vworld_polygon import (
    _centroid, _closest_feature, _to_coords, get_building_polygon,
)

# 서울 삼성동 기준 테스트 좌표
_LAT, _LNG = 37.5107, 127.0642


def _make_feature(coords: list, geom_type: str = "Polygon") -> dict:
    """GeoJSON Feature 딕셔너리 생성 헬퍼."""
    if geom_type == "Polygon":
        coordinates = [coords]
    else:
        coordinates = [[coords]]
    return {
        "type": "Feature",
        "geometry": {"type": geom_type, "coordinates": coordinates},
        "properties": {},
    }


_SAMPLE_RING = [
    [127.064, 37.510], [127.065, 37.510],
    [127.065, 37.511], [127.064, 37.511],
    [127.064, 37.510],
]


# ── _centroid ────────────────────────────────────────────────────────────────

class TestCentroid:
    def test_simple_polygon(self):
        f = _make_feature(_SAMPLE_RING)
        cx, cy = _centroid(f)
        assert abs(cx - 127.0645) < 0.001
        assert abs(cy - 37.5105) < 0.001

    def test_invalid_feature_returns_zero(self):
        cx, cy = _centroid({"geometry": {}})
        assert cx == 0.0 and cy == 0.0


# ── _closest_feature ─────────────────────────────────────────────────────────

class TestClosestFeature:
    def test_empty(self):
        assert _closest_feature([], _LAT, _LNG) is None

    def test_single(self):
        f = _make_feature(_SAMPLE_RING)
        assert _closest_feature([f], _LAT, _LNG) is f

    def test_selects_nearest(self):
        near = _make_feature([
            [127.064, 37.510], [127.065, 37.510],
            [127.065, 37.511], [127.064, 37.510],
        ])
        far = _make_feature([
            [127.100, 37.550], [127.110, 37.550],
            [127.110, 37.560], [127.100, 37.550],
        ])
        result = _closest_feature([near, far], _LAT, _LNG)
        assert result is near


# ── _to_coords ───────────────────────────────────────────────────────────────

class TestToCoords:
    def test_polygon(self):
        f = _make_feature(_SAMPLE_RING)
        coords = _to_coords(f)
        assert coords is not None
        assert len(coords) == len(_SAMPLE_RING)
        assert all(len(c) == 2 for c in coords)

    def test_multipolygon(self):
        f = _make_feature(_SAMPLE_RING, geom_type="MultiPolygon")
        coords = _to_coords(f)
        assert coords is not None
        assert len(coords) == len(_SAMPLE_RING)

    def test_too_few_coords(self):
        f = _make_feature([[127.0, 37.0], [127.1, 37.0]])
        assert _to_coords(f) is None

    def test_unknown_geom_type(self):
        f = {"type": "Feature", "geometry": {"type": "Point", "coordinates": [127.0, 37.0]}, "properties": {}}
        assert _to_coords(f) is None


# ── get_building_polygon ─────────────────────────────────────────────────────

class TestGetBuildingPolygon:
    def test_no_api_key_returns_all_none(self):
        result = get_building_polygon(_LAT, _LNG, api_key="")
        assert result == (None, None, None, None, None)

    def test_api_success_returns_coords(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "features": [_make_feature(_SAMPLE_RING)]
        }

        with patch("data_collector.vworld_polygon.requests.get", return_value=mock_resp):
            area, azimuth, ew_m, ns_m, coords = get_building_polygon(
                _LAT, _LNG, api_key="DUMMY_KEY"
            )

        assert coords is not None
        assert len(coords) >= 3
        assert azimuth is not None
        assert 0 <= azimuth <= 360

    def test_empty_features_falls_through_all_layers(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"features": []}

        with patch("data_collector.vworld_polygon.requests.get", return_value=mock_resp):
            result = get_building_polygon(_LAT, _LNG, api_key="DUMMY_KEY")

        assert result == (None, None, None, None, None)

    def test_http_error_returns_none(self):
        import requests as _req
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = _req.HTTPError("500")

        with patch("data_collector.vworld_polygon.requests.get", return_value=mock_resp):
            result = get_building_polygon(_LAT, _LNG, api_key="DUMMY_KEY")

        assert result == (None, None, None, None, None)

    def test_small_polygon_area_returns_none_area(self):
        """면적 < 5㎡인 폴리곤 → area None, coords는 반환."""
        tiny = [
            [127.0640, 37.5100], [127.0640001, 37.5100],
            [127.0640001, 37.5100001], [127.0640, 37.5100],
        ]
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"features": [_make_feature(tiny)]}

        with patch("data_collector.vworld_polygon.requests.get", return_value=mock_resp):
            area, azimuth, ew_m, ns_m, coords = get_building_polygon(
                _LAT, _LNG, api_key="DUMMY_KEY"
            )

        assert area is None      # 5㎡ 미만이므로 None
        assert coords is not None
