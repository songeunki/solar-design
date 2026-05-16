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
    ) -> PanelLayoutResult:

        m_lng = _m_per_deg_lng(lat)

        # ── 1. 지붕 크기 추정 ─────────────────────────────────────────────
        side_m = math.sqrt(usable_area_m2)
        half_ns_m = side_m / 2
        half_ew_m = side_m / 2

        # ── 2. 파라펫 버퍼 (10%) ─────────────────────────────────────────
        buf_ratio = 0.10
        avail_ns_m = half_ns_m * (1 - buf_ratio)
        avail_ew_m = half_ew_m * (1 - buf_ratio)

        # ── 3. 행 이격거리 (동지 무음영) ──────────────────────────────────
        elev_rad = math.radians(max(sun_elevation_winter_deg, 5.0))
        tilt_rad = math.radians(tilt_deg)
        h_shadow = PANEL_H * math.sin(tilt_rad)            # 패널 투영 높이
        min_gap_m = h_shadow / math.tan(elev_rad)          # 동지 최소 이격
        row_spacing_m = PANEL_H * math.cos(tilt_rad) + min_gap_m

        # ── 4. 열 간격 ────────────────────────────────────────────────────
        col_spacing_m = PANEL_W + 0.05  # 측면 5cm 여유

        # ── 5. 행/열 수 ──────────────────────────────────────────────────
        row_count = max(1, int((avail_ns_m * 2) / row_spacing_m))
        col_count = max(1, int((avail_ew_m * 2) / col_spacing_m))

        # ── 6. 실제 배치 총 패널 수로 단위 발전량 계산 ────────────────────
        total = row_count * col_count
        kwh_per_panel = annual_generation_kwh / total if total > 0 else 0

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
                # 음영 구역: 최북단 행 (다른 패널 그림자를 받는 구역)
                if r == row_count - 1 and row_count > 2:
                    status = "shade"
                else:
                    status = "active"
                panels.append(Panel(
                    row=r, col=c, lat=p_lat, lng=p_lng,
                    status=status, kwh_year=kwh_per_panel,
                ))

        # ── 10. 지붕 윤곽 폴리곤 (기본: 사각형) ───────────────────────────
        if not roof_polygon:
            half_ns_deg = half_ns_m / M_PER_DEG_LAT
            half_ew_deg = half_ew_m / m_lng
            roof_polygon = [
                {"lat": lat - half_ns_deg, "lng": lng - half_ew_deg},
                {"lat": lat - half_ns_deg, "lng": lng + half_ew_deg},
                {"lat": lat + half_ns_deg, "lng": lng + half_ew_deg},
                {"lat": lat + half_ns_deg, "lng": lng - half_ew_deg},
            ]

        active_panels  = [p for p in panels if p.status == "active"]
        shaded_panels  = [p for p in panels if p.status == "shade"]

        stats = {
            "total_panels":   total,
            "active_panels":  len(active_panels),
            "shaded_panels":  len(shaded_panels),
            "row_count":      row_count,
            "col_count":      col_count,
            "row_spacing_m":  round(row_spacing_m, 2),
            "col_spacing_m":  round(col_spacing_m, 2),
            "tilt_deg":       tilt_deg,
            "azimuth_deg":    azimuth_deg,
            "panel_w_m":      PANEL_W,
            "panel_h_m":      PANEL_H,
            "min_gap_m":      round(min_gap_m, 2),
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
