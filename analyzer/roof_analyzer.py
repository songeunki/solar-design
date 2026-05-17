import math
from dataclasses import dataclass, field
from data_collector.building_api import BuildingInfo
from config import DEFAULTS, get_admin_defaults

_PANEL_AREA = DEFAULTS["panel_width_m"] * DEFAULTS["panel_height_m"]  # 기본값 (import 시점)
_PANEL_H    = DEFAULTS["panel_height_m"]                               # 기본값 (import 시점)

# 서울 기준 위도 및 최적 경사각
_LATITUDE  = 37.5              # °N
_OPT_TILT  = _LATITUDE * 0.87  # 서울 권장 최적각 ≈ 32.6°
_TILT_FLAT = 30.0              # 평지붕 설치 고정 경사각

# 절기별 태양 적위 (°)
_DECLINATION: dict[str, float] = {
    "동지":   -23.45,
    "춘추분":   0.00,
    "하지":    23.45,
}

# 경사지붕: 지붕면 밀착 설치 → GCR 고정
_GCR_SLOPE   = 0.90

# 지붕 유효 면적 비율 (파라펫·장비·출입 동선 제외)
_USABLE_RATIO: dict[str, float] = {
    "평지붕":   0.65,
    "경사지붕": 0.75,
}


@dataclass
class RoofAnalysis:
    usable_area_m2: float
    max_panels: int
    tilt_deg: float
    azimuth_deg: float
    azimuth_factor: float        # 방위각 발전량 보정계수 (남향=1.0)
    shading_loss: float
    gcr: float                   # 실제 적용 GCR
    solar_elevations: dict       # 절기별 정오 태양 고도각 (°)
    notes: list[str]
    roof_type: str = "평지붕"


class RoofAnalyzer:
    """지붕 면적·형태 분석 및 패널 배치 계산 (태양 고도각·방위각 보정 포함)"""

    def analyze(self, building: BuildingInfo) -> RoofAnalysis:
        cfg       = get_admin_defaults()
        panel_h   = cfg["panel_height_m"]
        panel_area = cfg["panel_width_m"] * cfg["panel_height_m"]
        min_roof  = cfg["min_roof_area_m2"]

        roof_type = building.roof_type if building.roof_type in _USABLE_RATIO else "평지붕"
        notes: list[str] = []

        # ── 1. 태양 고도각 계산 ──────────────────────────────────────────────
        elevations = {k: _solar_elevation(_LATITUDE, d) for k, d in _DECLINATION.items()}
        elev_winter = elevations["동지"]  # 보수적 설계 기준

        # ── 2. 경사각 결정 ───────────────────────────────────────────────────
        if roof_type == "평지붕":
            tilt = _TILT_FLAT
        else:
            tilt = building.roof_slope_deg if building.roof_slope_deg > 0 else _OPT_TILT
            _add_tilt_notes(tilt, notes)

        # ── 3. GCR 계산 (평지붕: 동지 정오 무음영 기준, 경사지붕: 고정) ────
        if roof_type == "평지붕":
            gcr = _gcr_from_solar(tilt, elev_winter)
            notes.append(
                f"동지 태양 고도각 {elev_winter:.1f}° 기준 GCR {gcr:.2f} 적용 "
                f"(행간 이격거리 {_row_gap_m(tilt, elev_winter, panel_h):.2f} m)"
            )
        else:
            gcr = _GCR_SLOPE

        # ── 4. 유효 면적 및 패널 수 ─────────────────────────────────────────
        usable = building.roof_area_m2 * _USABLE_RATIO[roof_type]
        if building.roof_area_m2 == 0:
            notes.append("건축물대장 건축면적 정보 없음 — 현장 실측 필요")
        elif usable < min_roof:
            notes.append(
                f"유효 면적({usable:.1f}㎡)이 최소 기준"
                f"({min_roof}㎡) 미만 — 설치 부적합 가능성"
            )

        area_per_panel = panel_area / gcr
        max_panels = max(0, math.floor(usable / area_per_panel))
        if max_panels == 0:
            notes.append("패널 설치 가능 수량 0 — 지붕 면적 또는 형태 재확인 필요")

        # ── 5. 방위각 보정계수 ───────────────────────────────────────────────
        az_factor = _azimuth_factor(building.roof_azimuth_deg)
        if az_factor < 0.99:
            loss_pct = round((1 - az_factor) * 100, 1)
            notes.append(
                f"방위각 {building.roof_azimuth_deg:.0f}° — "
                f"남향 대비 발전량 {loss_pct}% 감소 예상"
            )

        # ── 6. 음영 손실 추정 ────────────────────────────────────────────────
        shading = _estimate_shading(building, roof_type, elev_winter)

        # ── 7. 구조·환경 경고 ────────────────────────────────────────────────
        if building.structure and "조적" in building.structure:
            notes.append("조적구조: 패널 하중 검토 필요 (경량 모듈 권장)")
        if roof_type == "평지붕" and building.floors >= 5:
            notes.append("고층 건물: 파라펫 음영 및 풍하중 상세 검토 필요")

        return RoofAnalysis(
            usable_area_m2=round(usable, 1),
            max_panels=max_panels,
            tilt_deg=tilt,
            azimuth_deg=building.roof_azimuth_deg,
            azimuth_factor=az_factor,
            shading_loss=shading,
            gcr=gcr,
            solar_elevations={k: round(v, 1) for k, v in elevations.items()},
            notes=notes,
            roof_type=roof_type,
        )


# ── 태양 기하 계산 ─────────────────────────────────────────────────────────────

def _solar_elevation(lat_deg: float, dec_deg: float) -> float:
    """정오 태양 고도각 (°) = 90 - 위도 + 적위"""
    return 90.0 - lat_deg + dec_deg


def _gcr_from_solar(tilt_deg: float, elev_winter_deg: float) -> float:
    """동지 정오 무음영 조건의 최대 GCR.

    패널 수평 투영길이 / 행 간격(수평 투영 + 동지 음영 거리)
    GCR = cos(β) / (cos(β) + sin(β) / tan(α))
    """
    b = math.radians(tilt_deg)
    a = math.radians(elev_winter_deg)
    cos_b = math.cos(b)
    sin_b = math.sin(b)
    gcr = cos_b / (cos_b + sin_b / math.tan(a))
    return round(gcr, 3)


def _row_gap_m(tilt_deg: float, elev_winter_deg: float, panel_h: float = _PANEL_H) -> float:
    """동지 기준 행간 최소 이격거리 (m)"""
    shadow_h = panel_h * math.sin(math.radians(tilt_deg))
    return round(shadow_h / math.tan(math.radians(elev_winter_deg)), 2)


# ── 방위각 보정 ────────────────────────────────────────────────────────────────

def _azimuth_factor(azimuth_deg: float) -> float:
    """방위각별 발전량 보정계수.

    코사인 연속 보정식: factor = 0.85 + 0.15 × cos(azimuth - 180°)
    - 남향(180°): 1.00
    - 동/서향(90°/270°): 0.85  (-15%)
    - 북향(0°/360°): 0.70  (-30%)
    """
    return round(0.85 + 0.15 * math.cos(math.radians(azimuth_deg - 180.0)), 3)


# ── 경사지붕 경사각 노트 ───────────────────────────────────────────────────────

def _add_tilt_notes(tilt_deg: float, notes: list[str]) -> None:
    """경사지붕 경사각 적정성 평가 및 발전량 보정 안내"""
    if tilt_deg < 15:
        notes.append(
            f"경사각 {tilt_deg:.0f}° — 적설 하중 증가 및 자연 세척 효과 감소"
        )
    elif tilt_deg > 45:
        notes.append(
            f"경사각 {tilt_deg:.0f}° — 시공 난이도 높음, 풍하중 상세 검토 필요"
        )
    else:
        diff = abs(tilt_deg - _OPT_TILT)
        if diff > 8:
            # 최적각 대비 코사인 근사로 발전량 손실 추정
            loss_pct = round((1 - math.cos(math.radians(diff)) ** 0.3) * 100, 1)
            notes.append(
                f"경사각 {tilt_deg:.0f}° — 서울 최적각 {_OPT_TILT:.0f}° 대비 "
                f"약 {loss_pct}% 발전량 손실 예상"
            )


# ── 음영 손실 추정 ─────────────────────────────────────────────────────────────

def _estimate_shading(
    building: BuildingInfo, roof_type: str, elev_winter: float
) -> float:
    """동지 태양 고도각 기반 음영 손실 추정.

    평지붕: 아침/오후 행간 잔존 음영 + 파라펫 음영
    경사지붕: 기본 오염·반사 손실만 적용
    """
    if roof_type == "경사지붕":
        return 0.03

    # 행간 잔존 음영: GCR이 동지 정오 무음영 기준이므로
    # 일출·일몰 근방 저고도 시간대의 행간 음영 비율을 위도로 근사
    # elev_winter이 낮을수록(고위도) 아침·오후 음영 시간 길어짐
    row_shading = max(0.02, 0.10 - elev_winter * 0.002)

    # 파라펫 음영: 3층 이상부터 층당 1%, 최대 5% 추가
    parapet = 0.01 * min(max(0, building.floors - 2), 5) if building.floors >= 3 else 0.0

    return round(row_shading + parapet, 3)
