import pytest
import math

from data_collector.building_api import BuildingInfo
from analyzer.roof_analyzer import (
    RoofAnalyzer,
    _solar_elevation, _gcr_from_solar, _azimuth_factor, _row_gap_m,
)


def _building(
    roof_type="평지붕", roof_area=1000.0, floors=3,
    slope=0.0, azimuth=180.0, structure="철근콘크리트구조",
) -> BuildingInfo:
    return BuildingInfo(
        address="테스트주소", building_type="상업",
        floors=floors, roof_area_m2=roof_area,
        roof_type=roof_type, roof_slope_deg=slope,
        roof_azimuth_deg=azimuth, structure=structure,
    )


# ── 태양 고도각 ───────────────────────────────────────────────────────────────

class TestSolarElevation:
    def test_seoul_winter(self):
        # 서울(37.5°N) 동지(δ=-23.45°) → 29.05°
        assert _solar_elevation(37.5, -23.45) == pytest.approx(29.05)

    def test_seoul_equinox(self):
        assert _solar_elevation(37.5, 0.0) == pytest.approx(52.5)

    def test_seoul_summer(self):
        assert _solar_elevation(37.5, 23.45) == pytest.approx(75.95)

    def test_equator(self):
        # 적도 동지 → 90 - 23.45 = 66.55°
        assert _solar_elevation(0.0, -23.45) == pytest.approx(66.55)


# ── GCR 계산 ─────────────────────────────────────────────────────────────────

class TestGcrFromSolar:
    def test_seoul_winter_30deg(self):
        # 서울 동지(29.05°), 경사각 30°
        gcr = _gcr_from_solar(30.0, 29.05)
        assert 0.45 < gcr < 0.55  # 약 0.49

    def test_higher_elevation_higher_gcr(self):
        # 태양 고도각 높을수록 GCR 커짐 (더 촘촘히 배치 가능)
        gcr_low  = _gcr_from_solar(30.0, 20.0)
        gcr_high = _gcr_from_solar(30.0, 50.0)
        assert gcr_high > gcr_low

    def test_steeper_tilt_lower_gcr(self):
        # 경사각 클수록 그림자 길어져 GCR 작아짐
        gcr_flat  = _gcr_from_solar(10.0, 29.05)
        gcr_steep = _gcr_from_solar(45.0, 29.05)
        assert gcr_flat > gcr_steep


# ── 방위각 보정계수 ───────────────────────────────────────────────────────────

class TestAzimuthFactor:
    def test_south(self):
        assert _azimuth_factor(180.0) == pytest.approx(1.0, abs=1e-9)

    def test_east(self):
        assert _azimuth_factor(90.0) == pytest.approx(0.85, abs=1e-3)

    def test_west(self):
        assert _azimuth_factor(270.0) == pytest.approx(0.85, abs=1e-3)

    def test_north(self):
        assert _azimuth_factor(0.0) == pytest.approx(0.70, abs=1e-3)
        assert _azimuth_factor(360.0) == pytest.approx(0.70, abs=1e-3)

    def test_southeast(self):
        # 남동(135°)은 남향과 동향 사이 → 0.85 < factor < 1.0
        f = _azimuth_factor(135.0)
        assert 0.85 < f < 1.0


# ── 행간 이격거리 ─────────────────────────────────────────────────────────────

class TestRowGap:
    def test_positive(self):
        assert _row_gap_m(30.0, 29.05) > 0

    def test_steeper_tilt_larger_gap(self):
        assert _row_gap_m(40.0, 29.05) > _row_gap_m(20.0, 29.05)


# ── RoofAnalyzer 통합 ─────────────────────────────────────────────────────────

class TestRoofAnalyzer:
    def test_flat_roof_basic(self):
        roof = RoofAnalyzer().analyze(_building(roof_area=1000.0, floors=3))

        assert roof.roof_type == "평지붕"
        assert roof.tilt_deg == 30.0
        assert roof.usable_area_m2 == pytest.approx(650.0)
        assert roof.gcr == pytest.approx(0.49, abs=0.05)
        assert roof.max_panels > 0
        assert roof.azimuth_factor == pytest.approx(1.0)
        assert roof.shading_loss > 0

    def test_sloped_roof_uses_actual_slope(self):
        roof = RoofAnalyzer().analyze(_building(roof_type="경사지붕", slope=25.0))

        assert roof.tilt_deg == 25.0
        assert roof.gcr == pytest.approx(0.90)

    def test_sloped_roof_zero_slope_uses_optimal(self):
        # slope=0이면 최적각(32.6°) 사용
        roof = RoofAnalyzer().analyze(_building(roof_type="경사지붕", slope=0.0))

        assert roof.tilt_deg == pytest.approx(32.6, abs=0.5)

    def test_zero_area_adds_note(self):
        roof = RoofAnalyzer().analyze(_building(roof_area=0.0))

        assert any("건축면적" in n for n in roof.notes)

    def test_non_south_azimuth_adds_note(self):
        roof = RoofAnalyzer().analyze(_building(azimuth=90.0))

        assert roof.azimuth_factor == pytest.approx(0.85, abs=1e-3)
        assert any("방위각" in n for n in roof.notes)

    def test_masonry_structure_adds_note(self):
        roof = RoofAnalyzer().analyze(_building(structure="조적구조"))

        assert any("조적" in n for n in roof.notes)

    def test_high_rise_adds_note(self):
        roof = RoofAnalyzer().analyze(_building(floors=10))

        assert any("고층" in n for n in roof.notes)

    def test_solar_elevations_keys(self):
        roof = RoofAnalyzer().analyze(_building())

        assert set(roof.solar_elevations.keys()) == {"동지", "춘추분", "하지"}
        assert roof.solar_elevations["동지"] < roof.solar_elevations["하지"]

    def test_panel_count_proportional_to_area(self):
        small = RoofAnalyzer().analyze(_building(roof_area=200.0))
        large = RoofAnalyzer().analyze(_building(roof_area=1000.0))

        assert large.max_panels > small.max_panels
