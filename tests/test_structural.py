import pytest

from analyzer.roof_analyzer import RoofAnalysis
from designer.electrical import ElectricalDesign
from designer.structural import (
    StructuralDesigner,
    _calc_weight, _calc_wind_load, _calc_snow_load, _anchor_spec,
)


def _roof(panels=50, tilt=30.0, usable=650.0, roof_type="평지붕") -> RoofAnalysis:
    return RoofAnalysis(
        usable_area_m2=usable, max_panels=panels,
        tilt_deg=tilt, azimuth_deg=180.0, azimuth_factor=1.0,
        shading_loss=0.05, gcr=0.49,
        solar_elevations={"동지": 29.1, "춘추분": 52.5, "하지": 76.0},
        notes=[], roof_type=roof_type,
    )


def _electrical(panels=50, capacity=20.0) -> ElectricalDesign:
    return ElectricalDesign(
        panel_count=panels, total_capacity_kw=capacity,
        annual_generation_kwh=20000,
        monthly_generation_kwh=[1000.0] * 12,
        inverter_capacity_kw=20.0,
        string_config="10직렬 × 5병렬",
        wiring_spec={"dc_cable_mm2": 6, "ac_cable_mm2": 6,
                     "combiner_box_required": False, "string_fuse_A": 15,
                     "grounding_scheme": "TN-S"},
    )


# ── 하중 계산 ─────────────────────────────────────────────────────────────────

class TestCalcWeight:
    def test_flat_heavier_than_slope(self):
        # 평지붕: 발라스트 추가로 경사지붕보다 무거움
        w_flat  = _calc_weight(10, is_flat=True)
        w_slope = _calc_weight(10, is_flat=False)
        assert w_flat > w_slope

    def test_proportional_to_panel_count(self):
        assert _calc_weight(20, True) == pytest.approx(_calc_weight(10, True) * 2)

    def test_zero_panels(self):
        assert _calc_weight(0, True) == 0.0
        assert _calc_weight(0, False) == 0.0


class TestCalcWindLoad:
    def test_positive(self):
        assert _calc_wind_load(10, 30.0) > 0

    def test_steeper_tilt_larger_load(self):
        assert _calc_wind_load(10, 45.0) > _calc_wind_load(10, 15.0)

    def test_more_panels_larger_load(self):
        assert _calc_wind_load(20, 30.0) == pytest.approx(_calc_wind_load(10, 30.0) * 2)


class TestCalcSnowLoad:
    def test_positive_below_30deg(self):
        assert _calc_snow_load(10, 20.0) > 0

    def test_steep_slope_reduces_snow(self):
        # 30° 초과 시 미끄러짐 저감으로 적설하중 감소
        s30 = _calc_snow_load(10, 30.0)
        s60 = _calc_snow_load(10, 60.0)
        assert s30 > s60

    def test_zero_panels(self):
        assert _calc_snow_load(0, 30.0) == 0.0


class TestAnchorSpec:
    def test_flat_roof_chemical_anchor(self):
        spec = _anchor_spec(10, is_flat=True, wind_load_kn=50.0)
        assert "화학" in spec["type"]
        assert spec["total_count"] == 20  # 패널당 2개

    def test_slope_roof_hook_bolt(self):
        spec = _anchor_spec(10, is_flat=False, wind_load_kn=50.0)
        assert "후크" in spec["type"]
        assert spec["total_count"] == 30  # 패널당 3개

    def test_design_pull_calculated(self):
        spec = _anchor_spec(10, is_flat=True, wind_load_kn=100.0)
        # 총 앙카 20개 → 인발력 = 100 / 20 = 5.0 kN
        assert spec["design_pull_kn"] == pytest.approx(5.0)


# ── StructuralDesigner 통합 ───────────────────────────────────────────────────

class TestStructuralDesigner:
    def test_flat_roof_ballast_mounting(self):
        result = StructuralDesigner().design(_roof(roof_type="평지붕"), _electrical())
        assert "발라스트" in result.mounting_type

    def test_slope_roof_rail_mounting(self):
        result = StructuralDesigner().design(_roof(roof_type="경사지붕"), _electrical())
        assert "레일" in result.mounting_type

    def test_weight_positive(self):
        result = StructuralDesigner().design(_roof(panels=50), _electrical(panels=50))
        assert result.total_weight_kg > 0

    def test_zero_panels_note(self):
        result = StructuralDesigner().design(_roof(panels=0), _electrical(panels=0))
        assert any("설치 패널 없음" in n for n in result.structural_notes)

    def test_flat_roof_drainage_note(self):
        result = StructuralDesigner().design(_roof(roof_type="평지붕"), _electrical())
        assert any("배수" in n for n in result.structural_notes)

    def test_low_slope_note(self):
        result = StructuralDesigner().design(
            _roof(roof_type="경사지붕", tilt=10.0), _electrical()
        )
        assert any("경사각" in n for n in result.structural_notes)

    def test_high_density_note(self):
        # 작은 면적에 많은 패널 → 단위 하중 초과 경고
        result = StructuralDesigner().design(
            _roof(panels=200, usable=10.0), _electrical(panels=200)
        )
        assert any("구조체 내력" in n for n in result.structural_notes)

    def test_loads_positive(self):
        result = StructuralDesigner().design(_roof(panels=50), _electrical(panels=50))
        assert result.wind_load_kn > 0
        assert result.snow_load_kn > 0
