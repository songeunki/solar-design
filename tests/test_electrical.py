import pytest

from analyzer.roof_analyzer import RoofAnalysis
from data_collector.weather_api import SolarData
from designer.electrical import (
    ElectricalDesigner,
    _select_inverter, _calc_string_config, _build_wiring_spec,
)


def _roof(
    panels=100, tilt=30.0, azimuth=180.0, az_factor=1.0,
    shading=0.05, usable=650.0, gcr=0.49, roof_type="평지붕",
) -> RoofAnalysis:
    return RoofAnalysis(
        usable_area_m2=usable, max_panels=panels,
        tilt_deg=tilt, azimuth_deg=azimuth,
        azimuth_factor=az_factor, shading_loss=shading,
        gcr=gcr, solar_elevations={"동지": 29.1, "춘추분": 52.5, "하지": 76.0},
        notes=[], roof_type=roof_type,
    )


def _weather(peak=3.5) -> SolarData:
    return SolarData(
        annual_irradiance_kwh_m2=1277.5,
        peak_sun_hours=peak,
        monthly_irradiance=[100.0, 117.6, 169.5, 193.4, 224.5, 204.0,
                             161.7, 171.8, 158.0, 144.4, 98.0, 89.6],
        avg_temp_c=12.5,
    )


# ── _select_inverter ──────────────────────────────────────────────────────────

class TestSelectInverter:
    @pytest.mark.parametrize("target, expected", [
        (2.5,  3.0),
        (3.0,  3.0),
        (4.0,  5.0),
        (9.0, 10.0),
        (44.0, 50.0),
        (300.0, 250.0),  # 최대 라인업 초과 → 250 반환
    ])
    def test_standard_lineups(self, target, expected):
        assert _select_inverter(target) == expected


# ── _calc_string_config ───────────────────────────────────────────────────────

class TestCalcStringConfig:
    def test_zero_panels(self):
        assert _calc_string_config(0) == (0, 0)

    def test_single_string(self):
        # 패널 수가 최대 직렬(22) 이하 → 1 병렬
        s, p = _calc_string_config(10)
        assert p == 1
        assert s == 10

    def test_multiple_strings(self):
        s, p = _calc_string_config(100)
        assert s > 0 and p > 1
        assert s * p <= 100  # 잔여 패널 허용

    def test_voltage_constraint(self):
        # 직렬 수 × VOC(45V) ≤ MAX_DC_V(1000V) → 직렬 최대 22
        s, _ = _calc_string_config(200)
        assert s <= 22

    def test_min_mppt_constraint(self):
        # 직렬 수 × VMP(37V) ≥ MIN_MPPT_V(200V) → 직렬 최소 6
        s, p = _calc_string_config(50)
        if p > 1:
            assert s >= 6


# ── _build_wiring_spec ────────────────────────────────────────────────────────

class TestBuildWiringSpec:
    def test_small_system_cable(self):
        spec = _build_wiring_spec(10.0, 10.0, 2)
        assert spec["dc_cable_mm2"] == 6

    def test_large_system_cable(self):
        spec = _build_wiring_spec(50.0, 50.0, 5)
        assert spec["dc_cable_mm2"] == 10

    def test_combiner_box_above_3_parallel(self):
        assert _build_wiring_spec(30.0, 30.0, 4)["combiner_box_required"] is True
        assert _build_wiring_spec(30.0, 30.0, 3)["combiner_box_required"] is False


# ── ElectricalDesigner 통합 ───────────────────────────────────────────────────

class TestElectricalDesigner:
    def test_capacity_proportional_to_panels(self):
        w = _weather()
        d50  = ElectricalDesigner().design(_roof(panels=50), w)
        d100 = ElectricalDesigner().design(_roof(panels=100), w)

        assert d100.total_capacity_kw == pytest.approx(d50.total_capacity_kw * 2)

    def test_annual_equals_sum_of_monthly(self):
        result = ElectricalDesigner().design(_roof(panels=100), _weather())

        assert result.annual_generation_kwh == pytest.approx(
            sum(result.monthly_generation_kwh), abs=1
        )

    def test_monthly_length(self):
        result = ElectricalDesigner().design(_roof(), _weather())

        assert len(result.monthly_generation_kwh) == 12

    def test_azimuth_factor_reduces_generation(self):
        w = _weather()
        south = ElectricalDesigner().design(_roof(az_factor=1.0, panels=100), w)
        east  = ElectricalDesigner().design(_roof(az_factor=0.85, panels=100), w)

        assert south.annual_generation_kwh > east.annual_generation_kwh

    def test_azimuth_factor_ratio(self):
        w = _weather()
        south = ElectricalDesigner().design(_roof(az_factor=1.0, panels=100), w)
        north = ElectricalDesigner().design(_roof(az_factor=0.70, panels=100), w)

        ratio = north.annual_generation_kwh / south.annual_generation_kwh
        assert ratio == pytest.approx(0.70, abs=0.02)

    def test_string_config_format(self):
        result = ElectricalDesigner().design(_roof(panels=100), _weather())

        assert "직렬" in result.string_config
        assert "병렬" in result.string_config

    def test_zero_panels(self):
        result = ElectricalDesigner().design(_roof(panels=0), _weather())

        assert result.panel_count == 0
        assert result.total_capacity_kw == 0.0
        assert result.annual_generation_kwh == 0
        assert result.string_config == "N/A"
