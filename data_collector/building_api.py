"""건축물대장 표제부 조회 — PNU 추출 → 건축HUB API → OSM 순으로 시도."""
import math
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

    def get_building_info(self, location: Location) -> BuildingInfo:
        # 1단계: 건축물대장 API (Juso→Kakao로 PNU 확보)
        try:
            pnu  = _get_pnu(location.address)
            item = _fetch_building_item(pnu)
            return _parse_item(location.address, item)
        except BuildingAPIError as e:
            warnings.warn(f"[BuildingAPI] 건축물대장 실패: {e}", stacklevel=2)

        # 2단계: OSM Overpass로 건물 면적만 추정
        area = _building_area_from_osm(location.lat, location.lng)
        if area:
            warnings.warn(
                f"[BuildingAPI] OSM 면적 사용: {area:.1f}㎡ ({location.address})",
                stacklevel=2,
            )
            return _fallback_info(location.address, roof_area=area, area_source="OSM")

        return _fallback_info(location.address)


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

    roof_cd = item.get("roofCdNm", "")
    arch_area = float(item.get("archArea") or 0.0)

    # roofCdNm 값으로 지붕 형상 결정
    # 콘크리트 계열 → 평지붕, 슬레이트 → 박공, 기와 → 팔작, 나머지 경사 → 박공, 기타 → 평지붕
    if "콘크리트" in roof_cd:
        roof_type, slope, roof_shape = "평지붕", 0.0, "flat"
    elif "슬레이트" in roof_cd:
        roof_type, slope, roof_shape = "경사지붕", 30.0, "gable"
    elif "기와" in roof_cd:
        roof_type, slope, roof_shape = "경사지붕", 30.0, "hip"
    elif any(k in roof_cd for k in ("경사", "아스팔트", "금속", "징크")):
        roof_type, slope, roof_shape = "경사지붕", 30.0, "gable"
    else:
        roof_type, slope, roof_shape = "평지붕", 0.0, "flat"

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


# ── OSM Overpass 면적 추정 ─────────────────────────────────────────────────────

def _building_area_from_osm(lat: float, lng: float, radius_m: int = 50) -> float | None:
    """OSM Overpass API로 좌표 주변 건물 폴리곤 면적(㎡) 추출.

    무료, API키 불필요, 해외 서버(Railway)에서도 접근 가능.
    """
    query = (
        f"[out:json][timeout:12];"
        f"way[\"building\"](around:{radius_m},{lat},{lng});"
        f"out geom;"
    )
    try:
        resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=15)
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
    except Exception:
        return None

    if not elements:
        return None

    # 노드 수가 가장 많은 요소(가장 상세한 건물 폴리곤) 선택
    el = max(elements, key=lambda e: len(e.get("geometry", [])))
    coords = [(p["lon"], p["lat"]) for p in el.get("geometry", [])]
    if len(coords) < 3:
        return None

    area = _polygon_area_m2(coords)
    return round(area, 1) if area > 5 else None  # 5㎡ 미만은 노이즈


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
