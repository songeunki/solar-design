"""건축물대장 표제부 조회 — PNU 추출 → 건축HUB API → OSM 순으로 시도."""
import math
import os
import warnings
import requests
from dataclasses import dataclass, field
from data_collector.address_api import Location
from config import BUILDING_API_KEY, JUSO_API_KEY, KAKAO_REST_API_KEY

BUILDING_TITLE_URL  = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"
BUILDING_RECAP_URL  = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrRecapTitleInfo"
JUSO_API_URL        = "https://business.juso.go.kr/addrlink/addrLinkApi.do"
KAKAO_ADDRESS_URL     = "https://dapi.kakao.com/v2/local/search/address.json"
OVERPASS_URL          = "https://overpass-api.de/api/interpreter"
# Vercel 프록시: Render → Overpass 직접 연결 불가 시 사용 (icn1 리전)
_OSM_PROXY_URL = os.environ.get(
    "OSM_PROXY_URL",
    "https://solar-design-opal.vercel.app/api/osm-building",
)

_PURPOSE_TO_TYPE: dict[str, str] = {
    "단독주택": "주거", "공동주택": "주거", "다세대주택": "주거", "다가구주택": "주거",
    "제1종근린생활시설": "상업", "제2종근린생활시설": "상업",
    "판매시설": "상업", "업무시설": "상업", "숙박시설": "상업",
    "공장": "공업", "창고시설": "공업",
}


@dataclass
class BuildingInfo:
    address: str
    building_type: str
    floors: int
    roof_area_m2: float
    roof_type: str          # 평지붕/경사지붕
    roof_slope_deg: float
    roof_azimuth_deg: float
    structure: str
    extra: dict = field(default_factory=dict)


class BuildingAPIError(Exception):
    pass


class BuildingAPI:
    """PNU 추출(Juso→Kakao) → 건축물대장 API → OSM 면적 폴백 순으로 시도."""

    def get_building_info(self, location: Location, is_user_override: bool = False) -> BuildingInfo:
        # 1단계: PNU 확보 → 건축물대장 (archArea 힌트 추출 목적)
        _pnu:           str | None  = None
        _register_item: dict | None = None
        _arch_area_hint: float | None = None
        try:
            _pnu = _get_pnu(location.address)
        except BuildingAPIError as e:
            warnings.warn(f"[BuildingAPI] PNU 조회 실패: {e}", stacklevel=2)

        if _pnu:
            try:
                _register_item  = _fetch_building_item(_pnu)
                _arch_area_hint = float(_register_item.get("archArea") or 0) or None
            except BuildingAPIError as e:
                warnings.warn(f"[BuildingAPI] 건축물대장 실패: {e}", stacklevel=2)

        # 2단계: V-World WFS polygon (archArea 힌트로 대형 복합 필지 오선택 방지)
        from data_collector.vworld_polygon import get_building_polygon
        osm_area, osm_azimuth, osm_ew_m, osm_ns_m, osm_polygon = get_building_polygon(
            location.lat, location.lng,
            arch_area_m2=_arch_area_hint,
            user_location_override=is_user_override,
        )
        polygon_source = "vworld"

        # 3단계: OSM Overpass fallback (V-World 실패 시)
        if osm_polygon is None:
            osm_area, osm_azimuth, osm_ew_m, osm_ns_m, osm_polygon = _building_info_from_osm(
                location.lat, location.lng
            )
            polygon_source = "osm"

        if osm_azimuth is None:
            osm_azimuth = _DEFAULT_AZIMUTH

        warnings.warn(
            f"[BuildingAPI] polygon_source={polygon_source}  azimuth={osm_azimuth}° "
            f"EW={osm_ew_m}m NS={osm_ns_m}m polygon={len(osm_polygon) if osm_polygon else 0}pts ({location.address})",
            stacklevel=2,
        )

        def _apply_osm(info: BuildingInfo) -> BuildingInfo:
            info.roof_azimuth_deg               = osm_azimuth
            info.extra["osm_azimuth_deg"]        = osm_azimuth
            info.extra["polygon_source"]         = polygon_source
            if osm_ew_m:
                info.extra["building_ew_m"] = osm_ew_m
            if osm_ns_m:
                info.extra["building_ns_m"] = osm_ns_m
            if osm_polygon:
                info.extra["osm_polygon"] = [[c[0], c[1]] for c in osm_polygon]
            return info

        # 4단계: 건축물대장 결과 있으면 반환 (1단계에서 이미 취득)
        if _register_item:
            info = _apply_osm(_parse_item(location.address, _register_item))
            info.extra["pnu"] = _pnu
            return info

        # 5단계: OSM 면적 폴백
        if osm_area:
            warnings.warn(
                f"[BuildingAPI] OSM 면적 사용: {osm_area:.1f}㎡ ({location.address})",
                stacklevel=2,
            )
            info = _apply_osm(_fallback_info(location.address, roof_area=osm_area, area_source="OSM"))
            if _pnu:
                info.extra["pnu"] = _pnu
            return info

        info = _fallback_info(location.address)
        if _pnu:
            info.extra["pnu"] = _pnu
        return info


# ── PNU 추출 ───────────────────────────────────────────────────────────────────

def _get_pnu(address: str) -> str:
    """Kakao REST API → Juso API 순으로 19자리 PNU 반환.

    Kakao를 우선 사용하는 이유:
    - Juso API의 bdMgtSn은 산여부(11번째 자리)가 부정확한 경우가 있음
      (예: 도심 일반지번인데 산여부=1 반환 → 건축물대장 조회 실패)
    - Kakao는 b_code + mountain_yn으로 명시적으로 구분하므로 더 정확
    NOTE: VWorld getcoord의 level4LC는 법정동코드(10자리)라 PNU(19자리) 불가, 제외.
    """
    # 1단계: Kakao REST API (b_code + 산여부 + 본번 + 부번 명시적 조합)
    try:
        return _pnu_via_kakao(address)
    except BuildingAPIError:
        pass

    # 2단계: Juso API (bdMgtSn 앞 19자리)
    return _pnu_via_juso(address)


def _pnu_via_juso(address: str) -> str:
    """도로명주소 Juso API → bdMgtSn 앞 19자리(PNU).

    bdMgtSn 구조: 법정동코드(10) + 산여부(1) + 본번(4) + 부번(4) + 동코드(3) + 호코드(3)
    """
    if not JUSO_API_KEY:
        raise BuildingAPIError("JUSO_API_KEY 미설정")

    try:
        resp = requests.get(
            JUSO_API_URL,
            params={
                "confmKey": JUSO_API_KEY, "currentPage": 1,
                "countPerPage": 1, "keyword": address, "resultType": "json",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        raise BuildingAPIError(f"Juso API 호출 실패: {e}") from e

    common = data.get("results", {}).get("common", {})
    if common.get("errorCode", "") != "0":
        raise BuildingAPIError(f"Juso API 오류: {common.get('errorMessage', '')}")

    juso_list = data.get("results", {}).get("juso", [])
    if not juso_list:
        raise BuildingAPIError(f"Juso API 결과 없음: '{address}'")

    bd_mgt_sn = juso_list[0].get("bdMgtSn", "")
    pnu = bd_mgt_sn[:19]
    if len(pnu) != 19:
        raise BuildingAPIError(f"Juso bdMgtSn PNU 추출 실패: '{address}'")
    return pnu


def _pnu_via_kakao(address: str) -> str:
    """Kakao REST API → b_code + 산여부 + 본번 + 부번 조합으로 19자리 PNU 생성."""
    if not KAKAO_REST_API_KEY:
        raise BuildingAPIError("KAKAO_REST_API_KEY 미설정")

    try:
        resp = requests.get(
            KAKAO_ADDRESS_URL,
            params={"query": address, "size": 1},
            headers={"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"},
            timeout=10,
        )
        resp.raise_for_status()
        docs = resp.json().get("documents", [])
    except requests.RequestException as e:
        raise BuildingAPIError(f"Kakao 주소 조회 실패: {e}") from e

    if not docs:
        raise BuildingAPIError(f"Kakao 결과 없음: '{address}'")

    addr = docs[0].get("address")
    if not addr:
        raise BuildingAPIError(f"Kakao 지번주소 정보 없음: '{address}'")

    b_code = addr.get("b_code", "")
    if len(b_code) < 10:
        raise BuildingAPIError(f"Kakao b_code 형식 오류: '{b_code}'")

    mountain = "1" if addr.get("mountain_yn", "N") == "Y" else "0"
    main_no  = (addr.get("main_address_no") or "0").zfill(4)
    sub_no   = (addr.get("sub_address_no")  or "0").zfill(4)

    pnu = b_code[:10] + mountain + main_no + sub_no
    if len(pnu) != 19:
        raise BuildingAPIError(f"Kakao PNU 구성 실패 (길이 {len(pnu)}): '{address}'")
    return pnu


# ── 건축물대장 API ─────────────────────────────────────────────────────────────

def _fetch_building_item(pnu: str) -> dict:
    """PNU → 건축HUB API 조회.

    시도 순서:
    1. 일반건축물대장 표제부 (getBrTitleInfo)
    2. 총괄표제부 (getBrRecapTitleInfo) — 집합건물·대형건물은 여기에만 있음

    platGbCd(산여부)는 전달하지 않음: 원래 작동 테스트에 없었고,
    명시하면 오히려 일부 건물이 필터링되어 결과 없음 발생.
    """
    if not BUILDING_API_KEY:
        raise BuildingAPIError("BUILDING_API_KEY 미설정")

    base = {
        "serviceKey": BUILDING_API_KEY,
        "sigunguCd":  pnu[0:5],
        "bjdongCd":   pnu[5:10],
        "bun":        pnu[11:15],
        "ji":         pnu[15:19],
        "_type":      "json",
        "numOfRows":  10,
    }

    # 1차: 일반건축물대장 표제부
    try:
        return _call_building_api(BUILDING_TITLE_URL, base)
    except BuildingAPIError as e1:
        title_err = str(e1)

    # 2차: 총괄표제부
    try:
        return _call_building_api(BUILDING_RECAP_URL, base)
    except BuildingAPIError as e2:
        raise BuildingAPIError(
            f"일반표제부: {title_err} | 총괄표제부: {e2}"
        ) from e2


def _call_building_api(url: str, params: dict) -> dict:
    try:
        resp = requests.get(url, params=params, timeout=12)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise BuildingAPIError(f"건축물대장 API 호출 실패 ({url.split('/')[-1]}): {e}") from e

    if not resp.content:
        raise BuildingAPIError("응답 비어 있음 — 인코딩 키 여부 확인")

    try:
        data = resp.json()
    except Exception:
        raise BuildingAPIError(f"JSON 파싱 실패: {resp.text[:300]}")

    items = (
        data.get("response", {})
            .get("body", {})
            .get("items", {})
            .get("item", [])
    )
    if not items:
        result_code = data.get("response", {}).get("header", {}).get("resultCode", "")
        result_msg  = data.get("response", {}).get("header", {}).get("resultMsg", "")
        raise BuildingAPIError(
            f"데이터 없음 (resultCode={result_code}, msg={result_msg})"
        )
    return items if isinstance(items, dict) else items[0]


def _parse_item(address: str, item: dict) -> BuildingInfo:
    purpose       = item.get("mainPurpsCdNm", "")
    building_type = _PURPOSE_TO_TYPE.get(purpose, "기타")
    floors        = int(item.get("grndFlrCnt") or 1)
    roof_area     = float(item.get("archArea") or 0.0)

    if roof_area == 0.0:
        tot_area = float(item.get("totArea") or 0.0)
        if tot_area > 0:
            roof_area = round(tot_area / max(floors, 1), 1)

    roof_cd      = (item.get("roofCdNm", "") or "").strip()
    structure_cd = (item.get("strctCdNm", "") or "").strip()
    arch_area    = float(item.get("archArea") or 0.0)

    _RESIDENTIAL = ("단독주택", "다가구주택", "연립주택")
    _is_residential = purpose in _RESIDENTIAL
    _is_low_rise    = floors <= 3

    # 지붕 형상 결정 — 판정 우선순위:
    #  1) 명확한 경사 지시자 (기와·슬레이트·아스팔트 등)
    #  2) 슬라브/콘크리트 → 고층·상업은 평지붕, 저층 주거는 경사지붕 가능
    #  3) "평" 포함 → 무조건 평지붕
    #  4) 식별 불가 → 용도·구조 보조
    if "기와" in roof_cd:
        roof_type, slope, roof_shape = "경사지붕", 30.0, "hip"

    elif any(k in roof_cd for k in ("경사", "슬레이트", "아스팔트", "금속", "징크")):
        roof_type, slope, roof_shape = "경사지붕", 30.0, "gable"

    elif any(k in roof_cd for k in ("슬라브", "콘크리트")):
        # 슬라브/콘크리트: 저층 주거는 대장 오기재 가능 → gable 허용
        if _is_residential and _is_low_rise:
            roof_type, slope, roof_shape = "경사지붕", 30.0, "gable"
        else:
            roof_type, slope, roof_shape = "평지붕", 0.0, "flat"

    elif "평" in roof_cd:
        roof_type, slope, roof_shape = "평지붕", 0.0, "flat"

    else:
        # roofCdNm 식별 불가 → 용도·구조 보조
        if _is_residential or any(k in structure_cd for k in ("목조", "조적")):
            roof_type, slope, roof_shape = "경사지붕", 30.0, "gable"
        else:
            roof_type, slope, roof_shape = "평지붕", 0.0, "flat"

    # 진단 로그 — Railway 서버 로그에서 실제 roofCdNm 확인 가능
    warnings.warn(
        f"[roofShape] roofCdNm='{roof_cd}' | purpose='{purpose}' | "
        f"structure='{structure_cd}' | floors={floors} → {roof_shape}",
        stacklevel=3,
    )

    return BuildingInfo(
        address=address,
        building_type=building_type,
        floors=floors,
        roof_area_m2=roof_area,
        roof_type=roof_type,
        roof_slope_deg=slope,
        roof_azimuth_deg=180.0,
        structure=item.get("strctCdNm", ""),
        extra={
            "purpose":             purpose,
            "total_floor_area_m2": float(item.get("totArea") or 0.0),
            "underground_floors":  int(item.get("ugrndFlrCnt") or 0),
            "roof_code":           roof_cd,
            "roof_shape":          roof_shape,
            "arch_area_m2":        arch_area,
        },
    )


# ── OSM Overpass 면적·방위각·치수 추정 ────────────────────────────────────────

_DEFAULT_AZIMUTH = 135.0   # OSM 데이터 완전 없을 때 기본값 (실측 기반)

_CARDINAL_TO_DEG: dict[str, float] = {
    "N": 0.0, "NNE": 22.5, "NE": 45.0, "ENE": 67.5,
    "E": 90.0, "ESE": 112.5, "SE": 135.0, "SSE": 157.5,
    "S": 180.0, "SSW": 202.5, "SW": 225.0, "WSW": 247.5,
    "W": 270.0, "WNW": 292.5, "NW": 315.0, "NNW": 337.5,
}


def _parse_osm_direction(value: str) -> float | None:
    """OSM building:direction / direction 태그 → 방위각(°). 파싱 실패 시 None."""
    v = value.strip()
    if v.upper() in _CARDINAL_TO_DEG:
        return _CARDINAL_TO_DEG[v.upper()]
    _LONG: dict[str, float] = {
        "north": 0.0, "northeast": 45.0, "east": 90.0, "southeast": 135.0,
        "south": 180.0, "southwest": 225.0, "west": 270.0, "northwest": 315.0,
    }
    if v.lower() in _LONG:
        return _LONG[v.lower()]
    try:
        deg = float(v)
        return deg if 0.0 <= deg <= 360.0 else None
    except ValueError:
        return None


def _azimuth_from_road(lat: float, lng: float, radius_m: int = 30) -> float | None:
    """인근 도로 방향에서 건물 방위각 추정. 실패 시 None.

    도로 bearing에 +90°/-90° 법선 중 남향(180°)에 가까운 쪽 반환.
    """
    query = (
        f"[out:json][timeout:10];"
        f"way[\"highway\"](around:{radius_m},{lat},{lng});"
        f"out geom;"
    )
    try:
        resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=12)
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
    except Exception:
        return None

    if not elements:
        return None

    el     = elements[0]
    coords = [(p["lon"], p["lat"]) for p in el.get("geometry", [])]
    if len(coords) < 2:
        return None

    lat0    = (coords[0][1] + coords[-1][1]) / 2
    cos_lat = math.cos(math.radians(lat0))
    dx = (coords[-1][0] - coords[0][0]) * 111_320 * cos_lat
    dy = (coords[-1][1] - coords[0][1]) * 111_320
    if math.hypot(dx, dy) < 0.1:
        return None

    road_bearing = math.degrees(math.atan2(dx, dy)) % 360
    # 법선 두 후보 중 남향에 더 가까운 방향 선택
    best, best_diff = road_bearing, 360.0
    for offset in (90, -90):
        candidate = (road_bearing + offset) % 360
        diff = abs(candidate - 180)
        if diff > 180:
            diff = 360 - diff
        if diff < best_diff:
            best_diff, best = diff, candidate
    return round(best, 1)


def _building_info_from_osm(
    lat: float, lng: float, radius_m: int = 50
) -> tuple[float | None, float, float | None, float | None]:
    """OSM Overpass API로 건물 면적(㎡), 방위각(°), EW치수(m), NS치수(m) 반환.

    방위각 우선순위:
      1) building:direction 태그 (가장 정확)
      2) 폴리곤 엣지 법선 계산 (_azimuth_from_polygon)
      3) 인근 도로 방향 (_azimuth_from_road)
      4) 기본값 _DEFAULT_AZIMUTH
    반환: (area_m2|None, azimuth_deg, ew_m|None, ns_m|None)
    """
    # ── 건물 폴리곤 조회: Vercel proxy 우선, 실패 시 직접 호출 ──────────────
    elements: list = []
    try:
        resp = requests.get(
            _OSM_PROXY_URL,
            params={"lat": lat, "lng": lng, "radius": radius_m},
            timeout=35,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("success"):
            elements = data.get("elements", [])
    except Exception:
        pass

    if not elements:
        # Vercel proxy 실패 → Overpass 직접 시도 (로컬 환경 등)
        query = (
            f"[out:json][timeout:25];"
            f"way[\"building\"](around:{radius_m},{lat},{lng});"
            f"out body geom;"
        )
        try:
            resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=30)
            resp.raise_for_status()
            elements = resp.json().get("elements", [])
        except Exception:
            elements = []

    if elements:
        el     = max(elements, key=lambda e: len(e.get("geometry", [])))
        coords = [(p["lon"], p["lat"]) for p in el.get("geometry", [])]

        if len(coords) >= 3:
            # ── 면적 ─────────────────────────────────────────────────
            area = _polygon_area_m2(coords)

            # ── 바운딩박스 EW/NS 치수 (세계 좌표 기준) ──────────────
            lons  = [c[0] for c in coords]
            lats_ = [c[1] for c in coords]
            lat0  = sum(lats_) / len(lats_)
            cos_l = math.cos(math.radians(lat0))
            ew_m  = round((max(lons) - min(lons)) * 111_320 * cos_l, 1)
            ns_m  = round((max(lats_) - min(lats_)) * 111_320, 1)

            # ── 방위각: direction 태그 → 폴리곤 법선 ─────────────────
            tags    = el.get("tags", {})
            dir_tag = tags.get("building:direction") or tags.get("direction")
            if dir_tag:
                az = _parse_osm_direction(dir_tag)
                azimuth = az if az is not None else _azimuth_from_polygon(coords)
            else:
                azimuth = _azimuth_from_polygon(coords)

            return (round(area, 1) if area > 5 else None), azimuth, ew_m, ns_m, coords

    # ── 건물 폴리곤 없음 → 도로 방향 → 기본값 ────────────────────────
    azimuth = _azimuth_from_road(lat, lng) or _DEFAULT_AZIMUTH
    return None, azimuth, None, None, None


def _building_area_from_osm(lat: float, lng: float, radius_m: int = 50) -> float | None:
    """하위 호환용 — 면적만 반환."""
    area, _, _, _, _ = _building_info_from_osm(lat, lng, radius_m)
    return area


def _azimuth_from_polygon(coords: list[tuple[float, float]]) -> float:
    """건물 폴리곤 엣지에서 태양광 방위각(°) 계산.

    남쪽(180°)에 가장 가까운 면의 법선 방향 반환.
    엣지 길이 가중치 적용: 긴 벽면이 방위각 결정에 더 큰 영향.
    coords: [(lon, lat), ...] — OSM geometry 형식 (닫힌 폴리곤)
    """
    if len(coords) < 3:
        return 180.0
    lat0    = sum(c[1] for c in coords) / len(coords)
    cos_lat = math.cos(math.radians(lat0))
    best_az    = 180.0
    best_score = -1.0
    n = len(coords)
    for i in range(n - 1):
        lon1, lat1 = coords[i]
        lon2, lat2 = coords[(i + 1) % n]
        dx = (lon2 - lon1) * 111_320 * cos_lat   # 동서 성분 (m)
        dy = (lat2 - lat1) * 111_320              # 남북 성분 (m)
        length = math.hypot(dx, dy)
        if length < 0.5:
            continue
        # 엣지 방위각 (북=0°, 동=90°, 남=180°, 서=270°)
        edge_bearing = math.degrees(math.atan2(dx, dy)) % 360
        # 좌우 법선 각도 두 후보 — 폴리곤 winding 방향 무관하게 둘 다 검사
        for offset in (90, -90):
            normal_az = (edge_bearing + offset) % 360
            diff = abs(normal_az - 180)
            if diff > 180:
                diff = 360 - diff
            # 남향에 가깝고(diff↓) 엣지가 길수록(length↑) 높은 점수
            score = length / (1.0 + diff)
            if score > best_score:
                best_score = score
                best_az    = normal_az
    return round(best_az, 1)


def _polygon_area_m2(coords: list[tuple[float, float]]) -> float:
    """위경도 다각형 → 면적(㎡) 변환 (소면적 근사, 쇼레이스 공식).

    위도 1도 ≈ 111,320m, 경도 1도 ≈ 111,320 * cos(lat) m.
    """
    if len(coords) < 3:
        return 0.0
    lat0 = sum(c[1] for c in coords) / len(coords)
    mx   = 111_320 * math.cos(math.radians(lat0))
    my   = 111_320

    area = 0.0
    n    = len(coords)
    for i in range(n):
        x1, y1 = coords[i][0] * mx,       coords[i][1] * my
        x2, y2 = coords[(i + 1) % n][0] * mx, coords[(i + 1) % n][1] * my
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


# ── 폴백 ──────────────────────────────────────────────────────────────────────

def _fallback_info(
    address: str,
    roof_area: float = 100.0,
    area_source: str = "기본값",
) -> BuildingInfo:
    return BuildingInfo(
        address=address,
        building_type="기타",
        floors=1,
        roof_area_m2=roof_area,
        roof_type="평지붕",
        roof_slope_deg=0.0,
        roof_azimuth_deg=180.0,
        structure="철근콘크리트구조",
        extra={"fallback": True, "area_source": area_source, "roof_shape": "flat", "arch_area_m2": roof_area},
    )


# ── 단독 실행 (로컬 테스트용) ──────────────────────────────────────────────────

if __name__ == "__main__":
    import json as _json
    from dataclasses import asdict
    from data_collector.address_api import AddressAPI

    test_addr = "서울특별시 강남구 삼성동 169"
    print(f"[테스트 주소] {test_addr}\n")

    try:
        pnu = _get_pnu(test_addr)
        print(f"PNU: {pnu}")
        item = _fetch_building_item(pnu)
        print("건축물대장 원본:", _json.dumps(item, ensure_ascii=False, indent=2))
    except BuildingAPIError as e:
        print(f"건축물대장 실패: {e}")

    loc = AddressAPI().get_coordinates(test_addr)
    area = _building_area_from_osm(loc.lat, loc.lng)
    print(f"\nOSM 면적: {area} ㎡")
