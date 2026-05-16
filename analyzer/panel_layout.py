"""태양광 패널 배치 최적화 엔진."""
from __future__ import annotations
import math
from dataclasses import dataclass, field

# ── 640W 패널 규격 — 가로(landscape) 설치 기준 ──────────────────────────────
# 장변(2.094m)을 동서(EW) 방향으로 배치
PANEL_W = 2.094   # 동서(EW) 폭 — 장변
PANEL_H = 1.134   # 남북(NS) 높이 — 단변

M_PER_DEG_LAT = 111_320


def _meter_to_latlng(
    center_lat: float, center_lng: float,
    dx_east: float, dy_north: float,
) -> tuple[float, float]:
    """
    center 기준으로 동쪽 dx_east(m), 북쪽 dy_north(m) 이동한 위경도 반환.
    동쪽(+) = lng 증가, 북쪽(+) = lat 증가.
    """
    lat = center_lat + dy_north / M_PER_DEG_LAT
    lng = center_lng + dx_east / (M_PER_DEG_LAT * math.cos(math.radians(center_lat)))
    return lat, lng


# ── 데이터클래스 ────────────────────────────────────────────────────────────

@dataclass
class Panel:
    row: int
    col: int
    lat: float          # SW 꼭짓점 위도
    lng: float          # SW 꼭짓점 경도
    status: str         # 'active' | 'shade' | 'north' | 'buffer'
    kwh_year: float = 0.0
    corners: list[dict] = field(default_factory=list)  # [SW, SE, NE, NW] {lat, lng}


@dataclass
class PanelLayoutResult:
    panels: list[Panel]
    roof_polygon: list[dict]
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
                    "corners": p.corners,
                }
                for p in self.panels
            ],
            "roof_polygon":     self.roof_polygon,
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
    건물 중심 좌표 기반 패널 격자 배치.

    좌표 생성 순서:
      1. 미터 공간(x=동쪽+, y=북쪽+)에서 건물 격자 계산
      2. azimuth 회전 적용  rot_rad = azimuth_deg - 180°
         dx_rot = dx*cos - dy*sin
         dy_rot = dx*sin + dy*cos
      3. _meter_to_latlng()로 위경도 변환

    건물 장축: 동서(EW), 단축: 남북(NS)
    패널: 가로(landscape) — PANEL_W(EW장변)=2.094m, PANEL_H(NS단변)=1.134m
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

        m_lng = M_PER_DEG_LAT * math.cos(math.radians(lat))

        # ── 1. 건물 footprint ─────────────────────────────────────────────
        footprint     = arch_area_m2 if (arch_area_m2 and arch_area_m2 > 0) else usable_area_m2
        _ASPECT       = 1.5
        building_ew_m = math.sqrt(footprint * _ASPECT)   # 동서 장변
        building_ns_m = math.sqrt(footprint / _ASPECT)   # 남북 단변

        # ── 2. 외곽 경계 여유 (1 m) ──────────────────────────────────────
        MARGIN   = 1.0
        avail_ew = max(0.0, building_ew_m - 2 * MARGIN)
        avail_ns = max(0.0, building_ns_m - 2 * MARGIN)

        # ── 3. 행 이격거리 (남북, 동지 무음영) ───────────────────────────
        elev_rad      = math.radians(max(sun_elevation_winter_deg, 5.0))
        tilt_rad      = math.radians(tilt_deg)
        h_shadow      = PANEL_H * math.sin(tilt_rad)
        min_gap_m     = h_shadow / math.tan(elev_rad)
        row_spacing_m = PANEL_H * math.cos(tilt_rad) + min_gap_m

        # ── 4. 열 간격 (동서, 장변 방향) ─────────────────────────────────
        col_spacing_m = PANEL_W + 0.05

        # ── 5. 행/열 수 ──────────────────────────────────────────────────
        row_count = max(1, int(avail_ns / row_spacing_m))   # NS → 행(적음)
        col_count = max(1, int(avail_ew / col_spacing_m))   # EW → 열(많음)

        # ── [DEBUG] ───────────────────────────────────────────────────────
        print(
            f"[PanelLayout] footprint={footprint:.0f}㎡ "
            f"EW={building_ew_m:.2f}m(장변) NS={building_ns_m:.2f}m(단변) | "
            f"avail EW={avail_ew:.2f}m NS={avail_ns:.2f}m | "
            f"grid={row_count}행(NS)×{col_count}열(EW) | "
            f"row_sp={row_spacing_m:.3f}m col_sp={col_spacing_m:.3f}m | "
            f"PANEL_W(EW)={PANEL_W}m PANEL_H(NS)={PANEL_H}m | "
            f"azimuth={azimuth_deg}°",
            flush=True,
        )

        # ── 6. 단위 발전량 ────────────────────────────────────────────────
        total         = row_count * col_count
        base          = target_panel_count if (target_panel_count and target_panel_count > 0) else total
        kwh_per_panel = annual_generation_kwh / base if base > 0 else 0

        # ── 7. 위경도 단위 (하위 호환 — 2D 뷰어용) ───────────────────────
        panel_h_deg     = PANEL_H / M_PER_DEG_LAT
        panel_w_deg     = PANEL_W / m_lng
        row_spacing_deg = row_spacing_m / M_PER_DEG_LAT
        col_spacing_deg = col_spacing_m / m_lng

        # ── 8. 방위각 회전 설정 ───────────────────────────────────────────
        # rot_rad = azimuth_deg - 180  (정남향=0°, SE=-45°, SW=+45°)
        rot_rad = math.radians(azimuth_deg - 180.0)
        cos_r   = math.cos(rot_rad)
        sin_r   = math.sin(rot_rad)

        def _rot(dx: float, dy: float) -> tuple[float, float]:
            """2D 회전: (dx_east, dy_north) → (dx_rot, dy_rot)"""
            return (
                dx * cos_r - dy * sin_r,
                dx * sin_r + dy * cos_r,
            )

        # ── 9. 패널 목록 생성 ─────────────────────────────────────────────
        # 박공지붕: r >= ceil(row_count/2) → 북사면
        r_split = (row_count + 1) // 2 if roof_shape == "gable" else None

        # 건물 SW 꼭짓점 오프셋 (미터, 회전 전)
        bldg_sw_ew = -building_ew_m / 2 + MARGIN   # 서쪽 시작
        bldg_sw_ns = -building_ns_m / 2 + MARGIN   # 남쪽 시작

        panels: list[Panel] = []
        for r in range(row_count):
            for c in range(col_count):
                flat_idx = r * col_count + c

                # 패널 SW 오프셋 (건물 중심 기준, 회전 전)
                sw_ew = bldg_sw_ew + c * col_spacing_m   # 동쪽으로
                sw_ns = bldg_sw_ns + r * row_spacing_m   # 북쪽으로

                # SW 꼭짓점 위경도
                dx_r, dy_r = _rot(sw_ew, sw_ns)
                p_lat, p_lng = _meter_to_latlng(lat, lng, dx_r, dy_r)

                # 4개 꼭짓점 SW→SE→NE→NW (회전 적용)
                corners: list[dict] = []
                for dx_off, dy_off in [
                    (0,       0      ),  # SW
                    (PANEL_W, 0      ),  # SE (+EW)
                    (PANEL_W, PANEL_H),  # NE (+EW, +NS)
                    (0,       PANEL_H),  # NW (+NS)
                ]:
                    dx_r2, dy_r2 = _rot(sw_ew + dx_off, sw_ns + dy_off)
                    c_lat, c_lng = _meter_to_latlng(lat, lng, dx_r2, dy_r2)
                    corners.append({"lat": c_lat, "lng": c_lng})

                # 상태 결정
                if r_split is not None and r >= r_split:
                    status  = "north"
                    kwh_val = kwh_per_panel * 0.5
                elif target_panel_count and flat_idx >= target_panel_count:
                    status  = "buffer"
                    kwh_val = 0.0
                elif r == row_count - 1 and row_count > 2 and r_split is None:
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

        # ── [DEBUG] 방향 검증 ─────────────────────────────────────────────
        visible = [p for p in panels if p.status != "buffer"]
        if visible:
            p0, pN = visible[0], visible[-1]
            dlat_m = abs(pN.lat - p0.lat) * M_PER_DEG_LAT
            dlng_m = abs(pN.lng - p0.lng) * m_lng
            grid_orient = "동서(가로)✓" if dlng_m >= dlat_m else "남북(세로)⚠️"
            print(
                f"[PanelLayout] 배열범위 δEW={dlng_m:.1f}m δNS={dlat_m:.1f}m → {grid_orient}",
                flush=True,
            )
            if p0.corners:
                sw, se, nw = p0.corners[0], p0.corners[1], p0.corners[3]
                p_ew = abs(se["lng"] - sw["lng"]) * m_lng
                p_ns = abs(nw["lat"] - sw["lat"]) * M_PER_DEG_LAT
                print(
                    f"[PanelLayout] 단일패널 EW={p_ew:.3f}m NS={p_ns:.3f}m "
                    f"→ {'가로(landscape)✓' if p_ew > p_ns else '세로(portrait)⚠️'}",
                    flush=True,
                )

        # ── 10. 지붕 윤곽 폴리곤 (회전 포함) ─────────────────────────────
        if not roof_polygon:
            hw = building_ew_m / 2
            hn = building_ns_m / 2
            roof_polygon = []
            for bx, by in [(-hw, -hn), (hw, -hn), (hw, hn), (-hw, hn)]:
                dx_r, dy_r = _rot(bx, by)
                r_lat, r_lng = _meter_to_latlng(lat, lng, dx_r, dy_r)
                roof_polygon.append({"lat": r_lat, "lng": r_lng})

        # ── 11. 통계 ──────────────────────────────────────────────────────
        active_panels   = [p for p in panels if p.status == "active"]
        shaded_panels   = [p for p in panels if p.status == "shade"]
        north_panels    = [p for p in panels if p.status == "north"]
        displayed_total = len(active_panels) + len(shaded_panels) + len(north_panels)

        # Kakao Maps level=1, size=512px 기준 캡처 반경 ≈ 75m
        CAPTURE_RADIUS_M = 75

        stats = {
            "total_panels":     displayed_total,
            "active_panels":    len(active_panels),
            "shaded_panels":    len(shaded_panels),
            "north_panels":     len(north_panels),
            "row_count":        row_count,
            "col_count":        col_count,
            "row_spacing_m":    round(row_spacing_m, 2),
            "col_spacing_m":    round(col_spacing_m, 2),
            "tilt_deg":         tilt_deg,
            "azimuth_deg":      azimuth_deg,
            "panel_w_m":        PANEL_W,
            "panel_h_m":        PANEL_H,
            "min_gap_m":        round(min_gap_m, 2),
            "roof_shape":       roof_shape,
            "building_ew_m":    round(building_ew_m, 1),
            "building_ns_m":    round(building_ns_m, 1),
            "capture_radius_m": CAPTURE_RADIUS_M,
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
