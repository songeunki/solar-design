"""태양광 패널 배치 최적화 엔진."""
from __future__ import annotations
import math
from dataclasses import dataclass, field

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
    lat: float          # SW 꼭짓점 위도 (하위 호환)
    lng: float          # SW 꼭짓점 경도 (하위 호환)
    status: str         # 'active' | 'shade' | 'north' | 'buffer'
    kwh_year: float = 0.0
    corners: list[dict] = field(default_factory=list)  # [SW, SE, NE, NW] {lat, lng}


@dataclass
class PanelLayoutResult:
    panels: list[Panel]
    roof_polygon: list[dict]    # [{lat, lng}] — 지붕 윤곽
    center_lat: float
    center_lng: float
    panel_w_deg_lng: float
    panel_h_deg_lat: float
    row_spacing_deg: float
    col_spacing_deg: float
    stats: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "panels": [
                {
                    "row": p.row, "col": p.col,
                    "lat": p.lat, "lng": p.lng,
                    "status": p.status,
                    "kwh_year": round(p.kwh_year, 1),
                    "corners": p.corners,   # 회전 적용된 4개 꼭짓점
                }
                for p in self.panels
            ],
            "roof_polygon": self.roof_polygon,
            "center_lat":       self.center_lat,
            "center_lng":       self.center_lng,
            "panel_w_deg_lng":  self.panel_w_deg_lng,
            "panel_h_deg_lat":  self.panel_h_deg_lat,
            "row_spacing_deg":  self.row_spacing_deg,
            "col_spacing_deg":  self.col_spacing_deg,
            "stats":            self.stats,
        }


# ── 배치 엔진 ────────────────────────────────────────────────────────────────

class PanelLayoutEngine:
    """
    건물 중심 좌표·지붕 면적 기반 패널 격자 배치 계산.

    패널 좌표 생성 순서:
      1. 미터 좌표계(건물 중심 기준, x=동서, y=남북)에서 격자 계산
      2. azimuth_deg 기반 회전을 미터 공간에서 적용
      3. 위경도로 변환 → SW 꼭짓점(lat/lng) + 4개 꼭짓점(corners) 저장
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

        # ── 1. 지붕 크기 추정 ─────────────────────────────────────────────
        # 남향 건물: 동서(EW)가 장변(가로), 남북(NS)이 단변(세로)
        footprint = arch_area_m2 if (arch_area_m2 and arch_area_m2 > 0) else usable_area_m2
        _ASPECT       = 1.5
        building_ew_m = math.sqrt(footprint * _ASPECT)   # 동서 장변
        building_ns_m = math.sqrt(footprint / _ASPECT)   # 남북 단변

        # ── 2. 외곽 경계 여유 (1 m) ──────────────────────────────────────
        MARGIN = 1.0
        total_ns_m = max(0.0, building_ns_m - 2 * MARGIN)
        total_ew_m = max(0.0, building_ew_m - 2 * MARGIN)

        # ── 3. 행 이격거리 (남북 방향, 동지 무음영) ──────────────────────
        elev_rad      = math.radians(max(sun_elevation_winter_deg, 5.0))
        tilt_rad      = math.radians(tilt_deg)
        h_shadow      = PANEL_H * math.sin(tilt_rad)
        min_gap_m     = h_shadow / math.tan(elev_rad)
        row_spacing_m = PANEL_H * math.cos(tilt_rad) + min_gap_m

        # ── 4. 열 간격 (동서 방향, 최소 2% 이격) ─────────────────────────
        col_spacing_m = PANEL_W * 1.02

        # ── 5. 행/열 수 ──────────────────────────────────────────────────
        row_count = max(1, int(total_ns_m / row_spacing_m))
        col_count = max(1, int(total_ew_m / col_spacing_m))

        # ── [DEBUG] 건물/격자 치수 확인 ──────────────────────────────────
        print(
            f"[PanelLayout] footprint={footprint:.0f}㎡ | "
            f"building EW={building_ew_m:.2f}m NS={building_ns_m:.2f}m | "
            f"avail EW={total_ew_m:.2f}m NS={total_ns_m:.2f}m | "
            f"grid={row_count}행(NS)×{col_count}열(EW) | "
            f"row_spacing={row_spacing_m:.3f}m col_spacing={col_spacing_m:.3f}m",
            flush=True,
        )
        print(
            f"[PanelLayout] azimuth={azimuth_deg}° "
            f"rot_rad={rot_rad:.5f} cos={cos_r:.5f} sin={sin_r:.5f} | "
            f"center=({lat:.6f},{lng:.6f}) | "
            f"PANEL_W(EW)={PANEL_W}m PANEL_H(NS)={PANEL_H}m",
            flush=True,
        )
        print(
            f"[PanelLayout] 기대: col(열)→EW(lng+), row(행)→NS(lat+) | "
            f"_to_latlon(x=EW,y=NS)→(lat+y/111320, lng+x/m_lng)",
            flush=True,
        )

        # ── 6. 단위 발전량 ────────────────────────────────────────────────
        total         = row_count * col_count
        base          = target_panel_count if (target_panel_count and target_panel_count > 0) else total
        kwh_per_panel = annual_generation_kwh / base if base > 0 else 0

        # ── 7. 위경도 단위 변환 (하위 호환용) ────────────────────────────
        panel_h_deg     = PANEL_H / M_PER_DEG_LAT
        panel_w_deg     = PANEL_W / m_lng
        row_spacing_deg = row_spacing_m / M_PER_DEG_LAT
        col_spacing_deg = col_spacing_m / m_lng

        # ── 8. azimuth 회전 함수 (미터 공간 → 위경도) ────────────────────
        # azimuth=180° → 회전 0° (변화 없음)
        # azimuth=135° → CCW 45° 회전
        rot_rad = math.radians(-(azimuth_deg - 180.0))
        cos_r   = math.cos(rot_rad)
        sin_r   = math.sin(rot_rad)

        def _to_latlon(x_m: float, y_m: float) -> tuple[float, float]:
            """로컬 미터 오프셋 (x=동서+, y=남북+) → 회전 → 위경도"""
            xr = x_m * cos_r - y_m * sin_r
            yr = x_m * sin_r + y_m * cos_r
            return lat + yr / M_PER_DEG_LAT, lng + xr / m_lng

        # ── 9. 패널 목록 생성 ─────────────────────────────────────────────
        # 박공지붕: r >= ceil(row_count/2) → 북사면
        r_split = (row_count + 1) // 2 if roof_shape == "gable" else None

        panels: list[Panel] = []
        for r in range(row_count):
            for c in range(col_count):
                flat_idx = r * col_count + c

                # ── SW 꼭짓점 로컬 미터 오프셋 (격자 중심 = 건물 중심)
                cx_sw = (c - col_count / 2.0) * col_spacing_m
                cy_sw = (r - row_count / 2.0) * row_spacing_m

                # ── 회전 적용 → 위경도
                p_lat, p_lng = _to_latlon(cx_sw, cy_sw)

                # ── 4개 꼭짓점 (SW→SE→NE→NW)
                corners = []
                for dx_off, dy_off in [
                    (0,       0      ),   # SW
                    (PANEL_W, 0      ),   # SE
                    (PANEL_W, PANEL_H),   # NE
                    (0,       PANEL_H),   # NW
                ]:
                    c_lat, c_lng = _to_latlon(cx_sw + dx_off, cy_sw + dy_off)
                    corners.append({"lat": c_lat, "lng": c_lng})

                # ── 상태 결정
                if r_split is not None and r >= r_split:
                    status  = "north"
                    kwh_val = kwh_per_panel * 0.5
                elif target_panel_count and flat_idx >= target_panel_count:
                    status  = "buffer"
                    kwh_val = 0.0
                elif r == row_count - 1 and row_count > 2:
                    status  = "shade"
                    kwh_val = kwh_per_panel
                else:
                    status  = "active"
                    kwh_val = kwh_per_panel

                panels.append(Panel(
                    row=r, col=c,
                    lat=p_lat, lng=p_lng,
                    status=status, kwh_year=kwh_val,
                    corners=corners,
                ))

        # ── [DEBUG] 첫/마지막 패널 좌표 및 방향 검증 ────────────────────
        if panels:
            p0 = next((p for p in panels if p.status != "buffer"), panels[0])
            pN = next((p for p in reversed(panels) if p.status != "buffer"), panels[-1])
            dlat_m = abs(pN.lat - p0.lat) * M_PER_DEG_LAT
            dlng_m = abs(pN.lng - p0.lng) * m_lng
            orient = "동서(가로) ✓" if dlng_m >= dlat_m else "남북(세로) ⚠️ 방향 이상!"
            print(
                f"[PanelLayout] 첫패널=({p0.lat:.6f},{p0.lng:.6f}) "
                f"마지막=({pN.lat:.6f},{pN.lng:.6f})",
                flush=True,
            )
            print(
                f"[PanelLayout] δlat={dlat_m:.2f}m(NS) δlng={dlng_m:.2f}m(EW) → {orient}",
                flush=True,
            )
            # 단일 패널 크기 검증 (corners 이용)
            if p0.corners and len(p0.corners) == 4:
                sw, se, nw = p0.corners[0], p0.corners[1], p0.corners[3]
                p_ew = abs(se["lng"] - sw["lng"]) * m_lng
                p_ns = abs(nw["lat"] - sw["lat"]) * M_PER_DEG_LAT
                p_orient = "가로(landscape)" if p_ew > p_ns else "세로(portrait)"
                print(
                    f"[PanelLayout] 단일패널 EW={p_ew:.3f}m NS={p_ns:.3f}m → {p_orient}",
                    flush=True,
                )
                print(
                    f"[PanelLayout]   SW=({sw['lat']:.7f},{sw['lng']:.7f}) "
                    f"SE=({se['lat']:.7f},{se['lng']:.7f}) "
                    f"NW=({nw['lat']:.7f},{nw['lng']:.7f})",
                    flush=True,
                )

        # ── 10. 지붕 윤곽 폴리곤 (회전 포함) ─────────────────────────────
        if not roof_polygon:
            hw = building_ew_m / 2
            hn = building_ns_m / 2
            roof_polygon = []
            for x_off, y_off in [(-hw, -hn), (hw, -hn), (hw, hn), (-hw, hn)]:
                r_lat, r_lng = _to_latlon(x_off, y_off)
                roof_polygon.append({"lat": r_lat, "lng": r_lng})

        # ── 11. 통계 ──────────────────────────────────────────────────────
        active_panels   = [p for p in panels if p.status == "active"]
        shaded_panels   = [p for p in panels if p.status == "shade"]
        north_panels    = [p for p in panels if p.status == "north"]
        displayed_total = len(active_panels) + len(shaded_panels) + len(north_panels)

        # Kakao Maps level=2, 512px 기준 위성 캡처 반경 (m)
        # Three.js 바닥 PlaneGeometry 크기 = capture_radius_m * 2
        KAKAO_LEVEL2_RADIUS_M = 120

        stats = {
            "total_panels":       displayed_total,
            "active_panels":      len(active_panels),
            "shaded_panels":      len(shaded_panels),
            "north_panels":       len(north_panels),
            "row_count":          row_count,
            "col_count":          col_count,
            "row_spacing_m":      round(row_spacing_m, 2),
            "col_spacing_m":      round(col_spacing_m, 2),
            "tilt_deg":           tilt_deg,
            "azimuth_deg":        azimuth_deg,
            "panel_w_m":          PANEL_W,
            "panel_h_m":          PANEL_H,
            "min_gap_m":          round(min_gap_m, 2),
            "roof_shape":         roof_shape,
            "building_ew_m":      round(building_ew_m, 1),
            "building_ns_m":      round(building_ns_m, 1),
            "capture_radius_m":   KAKAO_LEVEL2_RADIUS_M,
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
