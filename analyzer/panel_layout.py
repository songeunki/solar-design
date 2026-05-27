"""태양광 패널 배치 최적화 엔진."""
from __future__ import annotations
import math
from dataclasses import dataclass, field

# ── 640W 패널 규격 — 가로(landscape) 설치 기준 ──────────────────────────────
# 장변(2.094m)을 동서(EW) 방향으로 배치
PANEL_W = 2.094   # 동서(EW) 폭 — 장변
PANEL_H = 1.134   # 남북(NS) 높이 — 단변

M_PER_DEG_LAT = 111_320


def calculate_optimal_azimuth(polygon_coords: list[dict]) -> float:
    """
    건물 폴리곤의 가장 긴 변을 기준으로 남향(180°)에 가장 가까운 면의 방위각 반환.
    polygon_coords: [{"lat": ..., "lng": ...}, ...]
    """
    if not polygon_coords or len(polygon_coords) < 2:
        return 180.0

    n = len(polygon_coords)
    best_len = -1.0
    best_azimuth = 180.0

    def _angle_diff(a: float, b: float) -> float:
        d = abs(a - b) % 360
        return min(d, 360 - d)

    for i in range(n):
        p1 = polygon_coords[i]
        p2 = polygon_coords[(i + 1) % n]
        mid_lat = (p1["lat"] + p2["lat"]) / 2
        dy = (p2["lat"] - p1["lat"]) * M_PER_DEG_LAT
        dx = (p2["lng"] - p1["lng"]) * M_PER_DEG_LAT * math.cos(math.radians(mid_lat))
        length = math.hypot(dx, dy)
        if length < 0.1:
            continue

        # 엣지 방위각 (북=0, 동=90, 남=180) 기준 수직 두 방향 중 남향에 가까운 쪽 선택
        edge_bearing = math.degrees(math.atan2(dx, dy)) % 360
        face1 = (edge_bearing + 90) % 360
        face2 = (edge_bearing - 90 + 360) % 360
        face = face1 if _angle_diff(face1, 180) <= _angle_diff(face2, 180) else face2

        if length > best_len:
            best_len = length
            best_azimuth = face

    return round(best_azimuth, 1)


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


def _center_in_polygon(lat: float, lng: float, polygon: list[dict]) -> bool:
    """Ray-casting PIP. polygon: [{"lat": ..., "lng": ...}, ...]
    회전 bbox 팽창으로 실제 지붕 밖에 생성된 패널 위치를 제거하는 데 사용.
    """
    n = len(polygon)
    if n < 3:
        return True
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]["lng"], polygon[i]["lat"]
        xj, yj = polygon[j]["lng"], polygon[j]["lat"]
        if ((yi > lat) != (yj > lat)) and \
                (lng < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


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
        osm_building_ew_m: float | None = None,
        osm_building_ns_m: float | None = None,
    ) -> PanelLayoutResult:

        m_lng = M_PER_DEG_LAT * math.cos(math.radians(lat))

        # ── 0. grid 기준점: polygon 중심 우선, 없으면 geocoded 주소 사용 ───
        # geocoded address(lat/lng)와 V-World polygon 중심이 최대 수십 m 벗어날
        # 수 있으므로, polygon이 있으면 centroid를 grid 원점으로 정렬한다.
        if roof_polygon and len(roof_polygon) >= 3:
            grid_lat = sum(p["lat"] for p in roof_polygon) / len(roof_polygon)
            grid_lng = sum(p["lng"] for p in roof_polygon) / len(roof_polygon)
        else:
            grid_lat = lat
            grid_lng = lng

        # ── 1. 건물 footprint ─────────────────────────────────────────────
        footprint = arch_area_m2 if (arch_area_m2 and arch_area_m2 > 0) else usable_area_m2
        if osm_building_ew_m and osm_building_ew_m > 0 \
                and osm_building_ns_m and osm_building_ns_m > 0:
            # OSM 폴리곤 실측 치수 사용 (세계좌표 바운딩박스)
            building_ew_m = osm_building_ew_m
            building_ns_m = osm_building_ns_m
        else:
            # OSM 없음 — 종횡비 추정 (NS 장변 1.5:1 기본)
            _ASPECT       = 1.5
            building_ns_m = math.sqrt(footprint * _ASPECT)
            building_ew_m = math.sqrt(footprint / _ASPECT)

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
        row_count = max(1, int(avail_ns / row_spacing_m))   # NS 장변 → 행(많음)
        col_count = max(1, int(avail_ew / col_spacing_m))   # EW 단변 → 열(적음)

        # ── 6. 격자 총 수 (kwh_per_panel은 polygon 수용량 확인 후 계산) ─────
        total = row_count * col_count

        # ── 7. 위경도 단위 (하위 호환 — 2D 뷰어용) ───────────────────────
        panel_h_deg     = PANEL_H / M_PER_DEG_LAT
        panel_w_deg     = PANEL_W / m_lng
        row_spacing_deg = row_spacing_m / M_PER_DEG_LAT
        col_spacing_deg = col_spacing_m / m_lng

        # ── 8. 방위각 회전 설정 ───────────────────────────────────────────
        # 기본값(180°) + 폴리곤 있으면 가장 긴 변 기준 남향 면으로 자동 계산
        if roof_polygon:
            poly_azimuth = calculate_optimal_azimuth(roof_polygon)
            print(f"[AZIMUTH_DEBUG] polygon_calc: {len(roof_polygon)}pts → {poly_azimuth}°")
            azimuth_deg = poly_azimuth
        else:
            print(f"[AZIMUTH_DEBUG] polygon_calc skipped: azimuth_deg={azimuth_deg}  roof_polygon=None")
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

        # ── 9. 패널 목록 생성 (2-pass) ───────────────────────────────────
        # 박공지붕: r >= ceil(row_count/2) → 북사면
        r_split = (row_count + 1) // 2 if roof_shape == "gable" else None

        # 건물 SW 꼭짓점 오프셋 (미터, 회전 전)
        bldg_sw_ew = -building_ew_m / 2 + MARGIN   # 서쪽 시작
        bldg_sw_ns = -building_ns_m / 2 + MARGIN   # 남쪽 시작

        # ── 1차 패스: 격자 위치 계산 + PIP 필터링 ────────────────────────
        # polygon bbox 기준 격자 생성 → 각 패널 중심이 지붕 polygon 내부인지
        # 검증 후 실제 수용 가능 매수(polygon_capacity)를 산출한다.
        _candidates: list[tuple] = []
        for r in range(row_count):
            for c in range(col_count):
                sw_ew = bldg_sw_ew + c * col_spacing_m
                sw_ns = bldg_sw_ns + r * row_spacing_m

                dx_r, dy_r = _rot(sw_ew, sw_ns)
                p_lat, p_lng = _meter_to_latlng(grid_lat, grid_lng, dx_r, dy_r)

                corners_: list[dict] = []
                for dx_off, dy_off in [
                    (0,       0      ),  # SW
                    (PANEL_W, 0      ),  # SE (+EW)
                    (PANEL_W, PANEL_H),  # NE (+EW, +NS)
                    (0,       PANEL_H),  # NW (+NS)
                ]:
                    dx_r2, dy_r2 = _rot(sw_ew + dx_off, sw_ns + dy_off)
                    c_lat, c_lng = _meter_to_latlng(grid_lat, grid_lng, dx_r2, dy_r2)
                    corners_.append({"lat": c_lat, "lng": c_lng})

                center_lat = (corners_[0]["lat"] + corners_[2]["lat"]) / 2
                center_lng = (corners_[0]["lng"] + corners_[2]["lng"]) / 2
                in_poly = (not roof_polygon) or _center_in_polygon(
                    center_lat, center_lng, roof_polygon
                )
                _candidates.append((r, c, p_lat, p_lng, corners_, in_poly))

        # polygon 내부 실제 수용 가능 매수 → target_panel_count 대체
        polygon_capacity = sum(1 for *_, ip in _candidates if ip)
        eff_base = polygon_capacity if polygon_capacity > 0 else total
        kwh_per_panel = annual_generation_kwh / eff_base if eff_base > 0 else 0

        # ── 2차 패스: 상태 배정 ─────────────────────────────────────────
        panels: list[Panel] = []
        inside_idx = 0
        for r, c, p_lat, p_lng, corners, in_poly in _candidates:
            if not in_poly:
                status, kwh_val = "buffer", 0.0
            else:
                if r_split is not None and r >= r_split:
                    status, kwh_val = "north", kwh_per_panel * 0.5
                elif r == row_count - 1 and row_count > 2 and r_split is None:
                    status, kwh_val = "shade", kwh_per_panel
                else:
                    status, kwh_val = "active", kwh_per_panel
                inside_idx += 1
            panels.append(Panel(
                row=r, col=c,
                lat=p_lat, lng=p_lng,
                status=status, kwh_year=kwh_val,
                corners=corners,
            ))

        # ── 10. 지붕 윤곽 폴리곤 (회전 포함) ─────────────────────────────
        # 전달받은 폴리곤이 4개 이상의 유니크 좌표를 갖는지 검증
        if roof_polygon:
            _tol = 1e-7
            _unique = [roof_polygon[0]]
            for _p in roof_polygon[1:]:
                if not any(
                    abs(_p["lat"] - _u["lat"]) < _tol
                    and abs(_p["lng"] - _u["lng"]) < _tol
                    for _u in _unique
                ):
                    _unique.append(_p)
            if len(_unique) < 4:
                import warnings
                warnings.warn(
                    f"[PanelLayout] roof_polygon 유니크 점 {len(_unique)}개 < 4 → 직사각형 폴백",
                    stacklevel=2,
                )
                roof_polygon = None   # 폴백 트리거

        if not roof_polygon:
            hw = building_ew_m / 2
            hn = building_ns_m / 2
            roof_polygon = []
            for bx, by in [(-hw, -hn), (hw, -hn), (hw, hn), (-hw, hn)]:
                dx_r, dy_r = _rot(bx, by)
                r_lat, r_lng = _meter_to_latlng(grid_lat, grid_lng, dx_r, dy_r)
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
            "polygon_capacity": polygon_capacity,
        }

        return PanelLayoutResult(
            panels=panels,
            roof_polygon=roof_polygon,
            center_lat=grid_lat,
            center_lng=grid_lng,
            panel_w_deg_lng=panel_w_deg,
            panel_h_deg_lat=panel_h_deg,
            row_spacing_deg=row_spacing_deg,
            col_spacing_deg=col_spacing_deg,
            stats=stats,
        )
