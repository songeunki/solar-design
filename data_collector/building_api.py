import warnings
import requests
from dataclasses import dataclass, field
from data_collector.address_api import Location
from config import BUILDING_API_KEY, VWORLD_API_KEY, JUSO_API_KEY, KAKAO_REST_API_KEY

BUILDING_REGISTRY_URL = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"
VWORLD_ADDRESS_URL    = "https://api.vworld.kr/req/address"
JUSO_API_URL          = "https://business.juso.go.kr/addrlink/addrLinkApi.do"
KAKAO_ADDRESS_URL     = "https://dapi.kakao.com/v2/local/search/address.json"

_PURPOSE_TO_TYPE: dict[str, str] = {
    "단독주택": "주거", "공동주택": "주거", "다세대주택": "주거", "다가구주택": "주거",
    "제1종근린생활시설": "상업", "제2종근린생활시설": "상업",
    "판매시설": "상업", "업무시설": "상업", "숙박시설": "상업",
    "공장": "공업", "창고시설": "공업",
}


@dataclass
class BuildingInfo:
    address: str
    building_type: str      # 주거/상업/공업 등
    floors: int
    roof_area_m2: float
    roof_type: str          # 평지붕/경사지붕
    roof_slope_deg: float   # 경사각 (도)
    roof_azimuth_deg: float # 방위각 (0=북, 180=남)
    structure: str          # 철근콘크리트/철골 등
    extra: dict = field(default_factory=dict)


class BuildingAPIError(Exception):
    pass


class BuildingAPI:
    """VWorld 주소 → PNU 변환 후 건축HUB 건축물대장 표제부 조회"""

    def get_building_info(self, location: Location) -> BuildingInfo:
        try:
            pnu  = _get_pnu(location)
            item = _fetch_building_item(pnu)
            return _parse_item(location.address, item)
        except BuildingAPIError as e:
            warnings.warn(
                f"[BuildingAPI] {e} — 건축물대장 조회 실패, 기본값으로 대체합니다. "
                "실제 운영 시 data.go.kr에서 유효한 BUILDING_API_KEY를 발급받으세요.",
                stacklevel=2,
            )
            return _fallback_info(location.address)


# ── 내부 함수 ─────────────────────────────────────────────────────────────────

def _get_pnu(location: Location) -> str:
    """VWorld → Juso → Kakao REST API 순으로 PNU 추출."""
    # 1단계: VWorld (도로명 → 지번)
    vworld_network_err = False
    for addr_type in ("road", "parcel"):
        params = {
            "service": "address", "request": "getcoord", "version": "2.0",
            "crs": "epsg:4326", "address": location.address,
            "format": "json", "type": addr_type, "key": VWORLD_API_KEY,
        }
        try:
            resp = requests.get(VWORLD_ADDRESS_URL, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException:
            vworld_network_err = True
            break  # 네트워크·HTTP 오류 → 재시도 없이 폴백

        if data.get("response", {}).get("status") != "OK":
            continue

        pnu = (
            data.get("response", {})
                .get("refined", {})
                .get("structure", {})
                .get("level4LC", "")
        )
        if len(pnu) == 19:
            return pnu

    # 2단계: Juso API
    try:
        return _pnu_via_juso(location.address)
    except BuildingAPIError:
        pass

    # 3단계: Kakao REST API
    return _pnu_via_kakao(location.address)


def _pnu_via_juso(address: str) -> str:
    """Juso API로 도로명 주소를 조회해 bdMgtSn 앞 19자리(PNU)를 반환한다.
    bdMgtSn 구조: 법정동코드(10) + 산여부(1) + 본번(4) + 부번(4) + 동코드(3) + 호코드(3)
    """
    if not JUSO_API_KEY:
        raise BuildingAPIError(
            "도로명 주소에서 PNU를 추출하려면 JUSO_API_KEY가 필요합니다. "
            "www.juso.go.kr 에서 키를 발급받아 config.py에 입력하세요."
        )

    params = {
        "confmKey":     JUSO_API_KEY,
        "currentPage":  1,
        "countPerPage": 1,
        "keyword":      address,
        "resultType":   "json",
    }
    try:
        resp = requests.get(JUSO_API_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        raise BuildingAPIError(f"Juso API 호출 실패: {e}") from e

    common = data.get("results", {}).get("common", {})
    if common.get("errorCode", "") != "0":
        raise BuildingAPIError(f"Juso API 오류: {common.get('errorMessage', '')}")

    juso_list = data.get("results", {}).get("juso", [])
    if not juso_list:
        raise BuildingAPIError(f"Juso API에서 주소를 찾을 수 없습니다: '{address}'")

    bd_mgt_sn = juso_list[0].get("bdMgtSn", "")
    pnu = bd_mgt_sn[:19]
    if len(pnu) != 19:
        raise BuildingAPIError(f"Juso API bdMgtSn에서 PNU를 추출할 수 없습니다: '{address}'")
    return pnu


def _pnu_via_kakao(address: str) -> str:
    """Kakao REST API 주소 검색으로 PNU를 구성한다.

    PNU = b_code(10) + 산여부(1) + 본번(4) + 부번(4)
    Kakao address 객체에서 b_code, mountain_yn, main/sub_address_no를 읽어 조합.
    """
    if not KAKAO_REST_API_KEY:
        raise BuildingAPIError("KAKAO_REST_API_KEY가 설정되지 않아 Kakao PNU 조회를 건너뜁니다.")
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
        raise BuildingAPIError(f"Kakao 주소 검색 결과 없음: '{address}'")

    addr = docs[0].get("address")  # 지번주소 정보
    if not addr:
        raise BuildingAPIError(f"Kakao 응답에 지번주소 정보 없음: '{address}'")

    b_code = addr.get("b_code", "")
    if len(b_code) < 10:
        raise BuildingAPIError(f"Kakao b_code 형식 오류: '{b_code}'")

    mountain  = "1" if addr.get("mountain_yn", "N") == "Y" else "0"
    main_no   = (addr.get("main_address_no") or "0").zfill(4)
    sub_no    = (addr.get("sub_address_no")  or "0").zfill(4)

    pnu = b_code[:10] + mountain + main_no + sub_no
    if len(pnu) != 19:
        raise BuildingAPIError(f"Kakao PNU 구성 실패 (길이 {len(pnu)}): '{address}'")
    return pnu


def _fetch_building_item(pnu: str) -> dict:
    """PNU → 건축HUB getBrTitleInfo 조회"""
    params = {
        "serviceKey": BUILDING_API_KEY,
        "sigunguCd":  pnu[0:5],
        "bjdongCd":   pnu[5:10],
        "bun":        pnu[11:15],
        "ji":         pnu[15:19],
        "_type":      "json",
    }
    return _call_building_api(params)


def _call_building_api(params: dict) -> dict:
    """건축물대장 API 호출 공통 로직"""
    try:
        resp = requests.get(BUILDING_REGISTRY_URL, params=params, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise BuildingAPIError(f"건축물대장 API 호출 실패: {e}") from e

    if not resp.content:
        raise BuildingAPIError(
            "건축물대장 API 응답이 비어 있습니다. "
            "data.go.kr에서 발급한 유효한 인코딩 키인지 확인하세요."
        )

    try:
        data = resp.json()
    except Exception as e:
        raise BuildingAPIError(f"건축물대장 API 응답 파싱 실패: {resp.text[:200]}") from e

    items = (
        data.get("response", {})
            .get("body", {})
            .get("items", {})
            .get("item", [])
    )
    if not items:
        raise BuildingAPIError("건축물대장에서 건물 정보를 찾을 수 없습니다.")
    return items if isinstance(items, dict) else items[0]


def _parse_item(address: str, item: dict) -> BuildingInfo:
    purpose       = item.get("mainPurpsCdNm", "")
    building_type = _PURPOSE_TO_TYPE.get(purpose, "기타")
    floors        = int(item.get("grndFlrCnt") or 1)
    roof_area     = float(item.get("archArea") or 0.0)
    # archArea가 0일 때 totArea / floors로 추정 (연면적 ÷ 층수 = 층당 면적 ≈ 지붕면적)
    if roof_area == 0.0:
        tot_area = float(item.get("totArea") or 0.0)
        if tot_area > 0:
            roof_area = round(tot_area / max(floors, 1), 1)
    roof_cd       = item.get("roofCdNm", "")

    if "경사" in roof_cd:
        roof_type, slope = "경사지붕", 30.0
    else:
        roof_type, slope = "평지붕", 0.0

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
        },
    )


def _fallback_info(address: str) -> BuildingInfo:
    """건축물대장 API 미응답 시 기본값 (테스트·시연용)"""
    return BuildingInfo(
        address=address,
        building_type="기타",
        floors=1,
        roof_area_m2=100.0,
        roof_type="평지붕",
        roof_slope_deg=0.0,
        roof_azimuth_deg=180.0,
        structure="철근콘크리트구조",
        extra={"fallback": True},
    )


if __name__ == "__main__":
    import json as _json
    from dataclasses import asdict

    params = {
        "serviceKey": BUILDING_API_KEY,
        "sigunguCd":  "11680",
        "bjdongCd":   "10500",
        "bun":        "0169",
        "ji":         "0000",
        "_type":      "json",
    }
    print("요청 URL:", BUILDING_REGISTRY_URL)
    print("파라미터:", params)

    try:
        item = _call_building_api(params)
        print("\n[원본 응답]")
        print(_json.dumps(item, ensure_ascii=False, indent=2))

        address = item.get("platPlc", "주소 미상")
        info = _parse_item(address, item)
        print("\n[BuildingInfo 변환 결과]")
        print(_json.dumps(asdict(info), ensure_ascii=False, indent=2))
    except BuildingAPIError as e:
        print(f"\n[오류] {e}")
