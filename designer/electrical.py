import math
from dataclasses import dataclass
from analyzer.roof_analyzer import RoofAnalysis
from data_collector.weather_api import SolarData
from config import get_admin_defaults

# 표준 인버터 용량 라인업 (kW)
_STANDARD_INVERTER_KW = [3, 5, 8, 10, 15, 20, 30, 50, 75, 100, 150, 200, 250]

# 400W 패널 기준 전기 특성 (일반 상업용 모듈)
_PANEL_VOC = 45.0   # V (개방 전압)
_PANEL_VMP = 37.0   # V (최대 동작 전압)
_MAX_DC_V  = 1000   # V (인버터 최대 직류 입력)
_MIN_MPPT_V = 200   # V (최소 MPPT 동작 전압)


@dataclass
class ElectricalDesign:
    panel_count: int
    total_capacity_kw: float
    annual_generation_kwh: float
    monthly_generation_kwh: list[float]   # 월별 예상 발전량 (12개월)
    inverter_capacity_kw: float
    string_config: str          # 예: "4직렬 × 3병렬"
    wiring_spec: dict


class ElectricalDesigner:
    """전기 설계: 용량 산정, 인버터 선정, 배선 설계"""

    def design(self, roof: RoofAnalysis, weather: SolarData) -> ElectricalDesign:
        cfg = get_admin_defaults()
        panel_count = roof.max_panels
        total_kw = round(panel_count * cfg["panel_watt"] / 1000, 2)

        # 연간 발전량: 경사면 일사량 보정 + 성능 계수(PR) + 방위각 보정 적용
        tilt_factor = 1.0 + 0.003 * roof.tilt_deg
        pr = (1 - cfg["system_loss"]) * (1 - roof.shading_loss) * roof.azimuth_factor

        # 월별 발전량: 월별 일사량(kWh/m²) × 시스템 용량 × 보정 계수
        monthly_gen = [
            round(total_kw * m * tilt_factor * pr, 1)
            for m in weather.monthly_irradiance
        ]
        annual_gen = round(sum(monthly_gen))

        # 인버터: DC/AC ratio 1.1 기준으로 목표 용량 산출 후 표준 용량 상향 선택
        inverter_kw = _select_inverter(total_kw / 1.1)

        series, parallel = _calc_string_config(panel_count)
        string_cfg = f"{series}직렬 × {parallel}병렬" if panel_count > 0 else "N/A"

        return ElectricalDesign(
            panel_count=panel_count,
            total_capacity_kw=total_kw,
            annual_generation_kwh=annual_gen,
            monthly_generation_kwh=monthly_gen,
            inverter_capacity_kw=inverter_kw,
            string_config=string_cfg,
            wiring_spec=_build_wiring_spec(total_kw, inverter_kw, parallel),
        )


def _select_inverter(target_kw: float) -> float:
    """목표 용량 이상의 가장 가까운 표준 인버터 용량 선택"""
    for kw in _STANDARD_INVERTER_KW:
        if kw >= target_kw:
            return float(kw)
    return float(_STANDARD_INVERTER_KW[-1])


def _calc_string_config(panel_count: int) -> tuple[int, int]:
    """VOC·MPPT 전압 범위를 지키며 잔여 패널을 최소화하는 직병렬 구성 산출"""
    if panel_count == 0:
        return 0, 0

    min_s = math.ceil(_MIN_MPPT_V / _PANEL_VMP)   # 최소 직렬 수 ≈ 6
    max_s = math.floor(_MAX_DC_V  / _PANEL_VOC)   # 최대 직렬 수 ≈ 22

    # 한 스트링으로 구성 가능한 경우
    if panel_count <= max_s:
        return panel_count, 1

    # 잔여 패널(불완전 스트링) 손실이 최소인 직렬 수 탐색
    best_s = min(max_s, 10)
    min_loss = panel_count % best_s
    for s in range(min_s, max_s + 1):
        loss = panel_count % s
        if loss < min_loss:
            min_loss = loss
            best_s = s

    return best_s, panel_count // best_s


def _build_wiring_spec(total_kw: float, inverter_kw: float, parallel: int) -> dict:
    """KEC(한국전기설비규정) 기준 주요 배선 사양"""
    return {
        "dc_cable_mm2": 6 if total_kw <= 30 else 10,
        "ac_cable_mm2": _ac_cable_mm2(inverter_kw),
        "combiner_box_required": parallel > 3,
        "string_fuse_A": 15,
        "grounding_scheme": "TN-S",
    }


def _ac_cable_mm2(inverter_kw: float) -> int:
    """인버터 용량별 AC 케이블 최소 단면적 (mm²)"""
    if inverter_kw <= 5:   return 4
    if inverter_kw <= 15:  return 6
    if inverter_kw <= 30:  return 10
    if inverter_kw <= 75:  return 25
    return 50
