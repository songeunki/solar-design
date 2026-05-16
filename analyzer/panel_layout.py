"""태양광 패널 배치 최적화 엔진."""
from __future__ import annotations
import math
from dataclasses import dataclass, field, asdict

# ── 640W 패널 규격 (m) ──────────────────────────────────────────────────────
PANEL_W = 1.134   # 폭  (동서 방향)
PANEL_H = 2.094   # 높이 (남북 방향, 세로 설치)

# ── 지구 계수 ───────────────────────────────────────────────────────────────
M_PER_DEG_LAT = 111_320


def _m_per_deg_lng(lat_deg: float) -> float:
    return M_PER_DEG_LAT * math.cos(math.radians(lat_deg))


# ── 데이터클래스 ────────────────────────────────────────────────────────────

@dataclass
class Panel:
    row: int
    col: int
    lat: float     # 남서 꼭짓점 위도
    lng: float     # 남서 꼭짓점 경도
    status: str    # 'active' | 'shade' | 'buffer'
    kwh_year: float = 0.0   # 연간 예상 발전량 (kWh)


@dataclass
class PanelLayoutResult:
    panels: list[Panel]
    roof_polygon: list[dict]    # [{lat, lng}] — 지붕 윤곽
    center_lat: float
    center_lng: float
    panel_w_deg_lng: float      # 패널 폭 (경도 단위)
    panel_h_deg_lat: float      # 패널 높이 (위도 단위)
    row_spacing_deg: float      # 행 간격 (위도 단위)
    col_spacing_deg: float      # 열 간격 (경도 단위)
    stats: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "panels": [
                {
                    "row": p.row, "col": p.col,
                    "lat": p.lat, "lng": p.lng,
                    "status": p.status,
                    "kwh_year": round(p.kwh_year, 1),
                }
                for p in self.panels
            ],
            "roof_polygon": self.roof_polygon,
            "center_lat": self.center_lat,
            "center_lng": self.center_lng,
            "panel_w_deg_lng": self.panel_w_deg_lng,
            "panel_h_deg_lat": self.panel_h_deg_lat,
            "row_spacing_deg": self.row_spacing_deg,
            "col_spacing_deg": self.col_spacing_deg,
            "stats": self.stats,
        }


# ── 배치 엔진 ────────────────────────────────────────────────────────────────

class PanelLayoutEngine:
    """
    건물 중심 좌표·지붕 면적 기반 패널 격자 배치 계산.

    - 남북 방향으로 패널 높이(세로) 배치
    - 동지 태양 고도각으로 최소 행 이격거리 계산
    - 파라펫·장비 구역 (10% 둘레 버퍼) 제외
    - 최북단 1행은 다른 패널 음영을 받는 'shade' 구역으로 표시
    """

    def compute(
        self,
        lat: float,
        lng: float,
        usable_area_m2: float,
        tilt_deg: float,
        sun_elevation_winter_deg: float,
        annual_generation_kwh: float,
        roof_polygon: list[dict] | None = None,
        azimuth_deg: float = 180.0,
        arch_area_m2: float | None = None,
        roof_shape: str = "flat",
        target_panel_count: int | None = None,
    ) -> PanelLayoutResult:

        m_lng = _m_per_deg_lng(lat)

        # ── 1. 지붕 크기 추정 (건축면적 우선, 없으면 가용면적) ───────────
        footprint = arch_area_m2 if (arch_area_m2 and arch_area_m2 > 0) else usable_area_m2
        # 일반 건물 장변(동서):단변(남북) ≈ 1.5:1
        _ASPECT       = 1.5
        building_ew_m = math.sqrt(footprint * _ASPECT)   # 동서 장변
        building_ns_m = math.sqrt(footprint / _ASPECT)   # 남북 단변

        # ── 2. 외곽 경계 여유 (1 m) ──────────────────────────────────────
        MARGIN = 1.0
        total_ns_m = max(0.0, building_ns_m - 2 * MARGIN)
        total_ew_m = max(0.0, building_ew_m - 2 * MARGIN)

        # ── 3. 행 이격거리 (남북 방향, 동지 무음영) ──────────────────────
        #   = 패널높이×cos(tilt) + 패널높이×sin(tilt)/tan(최저고도)
        elev_rad = math.radians(max(sun_elevation_winter_deg, 5.0))
        tilt_rad = math.radians(tilt_deg)
        h_shadow = PANEL_H * math.sin(tilt_rad)
        min_gap_m = h_shadow / math.tan(elev_rad)
        row_spacing_m = PANEL_H * math.cos(tilt_rad) + min_gap_m

        # ── 4. 열 간격 (동서 방향, 최소 2% 이격) ─────────────────────────
        col_spacing_m = PANEL_W * 1.02

        # ── 5. 행/열 수 ──────────────────────────────────────────────────
        row_count = max(1, int(total_ns_m / row_spacing_m))
        col_count = max(1, int(total_ew_m / col_spacing_m))

        # ── 6. 단위 발전량 (target 기준으로 정규화) ──────────────────────
        total = row_count * col_count
        base  = target_panel_count if (target_panel_count and target_panel_count > 0) else total
        kwh_per_panel = annual_generation_kwh / base if base > 0 else 0

        # ── 7. 위경도 단위 변환 ───────────────────────────────────────────
        panel_h_deg = PANEL_H / M_PER_DEG_LAT
        panel_w_deg = PANEL_W / m_lng
        row_spacing_deg = row_spacing_m / M_PER_DEG_LAT
        col_spacing_deg = col_spacing_m / m_lng

        # ── 8. 격자 원점 (남서 코너) ──────────────────────────────────────
        origin_lat = lat - (row_count * row_spacing_deg / 2)
        origin_lng = lng - (col_count * col_spacing_deg / 2)

        # ── 9. 패널 목록 생성 ─────────────────────────────────────────────
        panels: list[Panel] = []
        for r in range(row_count):
            for c in range(col_count):
                p_lat = origin_lat + r * row_spacing_deg
                p_lng = origin_lng + c * col_spacing_deg
                flat_idx = r * col_count + c

                # target을 초과하는 패널은 buffer (표시만, 발전량 0)
                if target_panel_count and flat_idx >= target_panel_count:
                    status = "buffer"
                elif r == row_count - 1 and row_count > 2:
                    status = "shade"
                else:
                    status = "active"

                panels.append(Panel(
                    row=r, col=c, lat=p_lat, lng=p_lng,
                    status=status,
                    kwh_year=kwh_per_panel if status != "buffer" else 0.0,
                ))

        # ── 10. 지붕 윤곽 폴리곤 (기본: 장변×단변 직사각형) ─────────────
        if not roof_polygon:
            half_ns_deg = (building_ns_m / 2) / M_PER_DEG_LAT
            half_ew_deg = (building_ew_m / 2) / m_lng
            roof_polygon = [
                {"lat": lat - half_ns_deg, "lng": lng - half_ew_deg},
                {"lat": lat - half_ns_deg, "lng": lng + half_ew_deg},
                {"lat": lat + half_ns_deg, "lng": lng + half_ew_deg},
                {"lat": lat + half_ns_deg, "lng": lng - half_ew_deg},
            ]

        active_panels = [p for p in panels if p.status == "active"]
        shaded_panels = [p for p in panels if p.status == "shade"]

        stats = {
            "total_panels":    total,
            "active_panels":   len(active_panels),
            "shaded_panels":   len(shaded_panels),
            "row_count":       row_count,
            "col_count":       col_count,
            "row_spacing_m":   round(row_spacing_m, 2),
            "col_spacing_m":   round(col_spacing_m, 2),
            "tilt_deg":        tilt_deg,
            "azimuth_deg":     azimuth_deg,
            "panel_w_m":       PANEL_W,
            "panel_h_m":       PANEL_H,
            "min_gap_m":       round(min_gap_m, 2),
            "roof_shape":      roof_shape,
            "building_ew_m":   round(building_ew_m, 1),
            "building_ns_m":   round(building_ns_m, 1),
        }

        return PanelLayoutResult(
            panels=panels,
            roof_polygon=roof_polygon,
            center_lat=lat,
            center_lng=lng,
            panel_w_deg_lng=panel_w_deg,
            panel_h_deg_lat=panel_h_deg,
            row_spacing_deg=row_spacing_deg,
            col_spacing_deg=col_spacing_deg,
            stats=stats,
        )
