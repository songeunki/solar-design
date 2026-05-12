from dataclasses import dataclass
from analyzer.roof_analyzer import RoofAnalysis
from designer.electrical import ElectricalDesign

# 설계 기준값 (KBC 2022)
_PANEL_WEIGHT_KG  = 22.0   # 400W 패널 단위 중량
_RACKING_FLAT_KG  = 10.0   # 평지붕 경사 마운트 중량/패널
_BALLAST_KG       = 20.0   # 발라스트 블록 중량/패널 (평지붕)
_RACKING_SLOPE_KG =  4.0   # 경사지붕 레일 마운트 중량/패널

_DESIGN_WIND_MS  = 35.0    # m/s  (KBC 기본 설계 풍속)
_GROUND_SNOW_KNM2 = 0.5    # kN/m² (서울 기준 지상 적설하중 Sg)
_PANEL_AREA_M2   = 1.134 * 2.094   # m²

_LOAD_WARN_KG_M2 = 25.0    # kg/m² 초과 시 구조 검토 권고


@dataclass
class StructuralDesign:
    mounting_type: str          # 고정식/추적식/BIPV
    total_weight_kg: float
    anchor_spec: dict           # 앙카 규격 및 간격
    wind_load_kn: float         # 설계 풍하중 (전체 패널 합산)
    snow_load_kn: float         # 설계 적설하중 (전체 패널 합산)
    structural_notes: list[str]


class StructuralDesigner:
    """구조 설계: 하중 계산, 마운팅 시스템 선정 (KBC 2022 기준)"""

    def design(self, roof: RoofAnalysis, electrical: ElectricalDesign) -> StructuralDesign:
        is_flat = (roof.roof_type == "평지붕")
        n = electrical.panel_count
        notes: list[str] = []

        total_weight = _calc_weight(n, is_flat)
        wind_load    = _calc_wind_load(n, roof.tilt_deg)
        snow_load    = _calc_snow_load(n, roof.tilt_deg)

        if n == 0:
            notes.append("설치 패널 없음 — 구조 설계 불필요")

        if roof.usable_area_m2 > 0 and n > 0:
            density = total_weight / roof.usable_area_m2
            if density > _LOAD_WARN_KG_M2:
                notes.append(
                    f"지붕 단위 하중 {density:.1f} kg/m² — 구조체 내력 검토 필요"
                )

        if is_flat:
            notes.append("평지붕: 적설 시 패널 하부 배수로 확보 필요")
        elif roof.tilt_deg < 15:
            notes.append(
                f"경사각 {roof.tilt_deg:.0f}° 미만 — 적설 하중 증가 및 자연 세척 효과 감소"
            )

        return StructuralDesign(
            mounting_type=_mounting_type(is_flat),
            total_weight_kg=round(total_weight, 1),
            anchor_spec=_anchor_spec(n, is_flat, wind_load),
            wind_load_kn=round(wind_load, 2),
            snow_load_kn=round(snow_load, 2),
            structural_notes=notes,
        )


# ── 하위 계산 함수 ────────────────────────────────────────────────────────────

def _mounting_type(is_flat: bool) -> str:
    if is_flat:
        return "고정식 — 알루미늄 경사 가변 마운트 (발라스트 + 앙카)"
    return "고정식 — 지붕 밀착형 알루미늄 레일 마운트"


def _calc_weight(n: int, is_flat: bool) -> float:
    panel = n * _PANEL_WEIGHT_KG
    racking = n * (_RACKING_FLAT_KG + _BALLAST_KG if is_flat else _RACKING_SLOPE_KG)
    return panel + racking


def _calc_wind_load(n: int, tilt_deg: float) -> float:
    """KBC 2022 풍하중: 설계 풍속 35 m/s, 경사각별 풍력 계수 적용"""
    q0 = 0.5 * 1.225 * _DESIGN_WIND_MS ** 2 / 1000  # kN/m²  (≈ 0.75)
    cp = 0.5 + 0.02 * tilt_deg   # 풍력 계수: 경사 클수록 증가
    return q0 * cp * n * _PANEL_AREA_M2


def _calc_snow_load(n: int, tilt_deg: float) -> float:
    """KBC 2022 적설하중: Sg = 0.5 kN/m², 30° 초과 시 미끄러짐 저감"""
    cb    = 0.8   # 기본 적설하중 계수
    slide = max(0.0, 1.0 - max(0.0, tilt_deg - 30.0) / 30.0)
    return _GROUND_SNOW_KNM2 * cb * n * _PANEL_AREA_M2 * slide


def _anchor_spec(n: int, is_flat: bool, wind_load_kn: float) -> dict:
    """앙카 규격·수량 산정 (패널당 인발력 = 총 풍하중 / 전체 앙카 수)"""
    if is_flat:
        cpp = 2   # 패널당 앙카 수
        total = n * cpp
        return {
            "type": "M12 화학 앙카 (케미컬 앙카)",
            "embedment_depth_mm": 80,
            "spacing_m": 3.0,
            "count_per_panel": cpp,
            "total_count": total,
            "design_pull_kn": round(wind_load_kn / max(total, 1), 2),
        }
    else:
        cpp = 3   # 패널당 후크 볼트 수
        total = n * cpp
        return {
            "type": "M10 지붕 후크 볼트 (스테인리스)",
            "rail_spacing_m": 1.2,
            "count_per_panel": cpp,
            "total_count": total,
            "design_pull_kn": round(wind_load_kn / max(total, 1), 2),
        }
