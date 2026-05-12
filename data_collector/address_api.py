import requests
from dataclasses import dataclass
from config import VWORLD_API_KEY

VWORLD_GEOCODE_URL = "https://api.vworld.kr/req/address"


@dataclass
class Location:
    address: str
    lat: float
    lng: float
    sido: str       # 시/도
    sigungu: str    # 시/군/구


class AddressAPIError(Exception):
    pass


class AddressAPI:
    """VWorld 지오코더 API로 주소 → 위도/경도 변환 (도로명·지번 모두 지원)"""

    def get_coordinates(self, address: str) -> Location:
        # 도로명 우선, 결과 없으면 지번으로 재시도
        for addr_type in ("road", "parcel"):
            data = _vworld_request(address, addr_type)
            if data.get("response", {}).get("status") == "OK":
                point = data["response"]["result"]["point"]
                sido, sigungu = _parse_sido_sigungu(address)
                return Location(
                    address=address,
                    lat=float(point["y"]),
                    lng=float(point["x"]),
                    sido=sido,
                    sigungu=sigungu,
                )

        raise AddressAPIError(f"주소를 찾을 수 없습니다: '{address}'")


def _vworld_request(address: str, addr_type: str) -> dict:
    params = {
        "service": "address",
        "request": "getcoord",
        "version": "2.0",
        "crs": "epsg:4326",
        "address": address,
        "format": "json",
        "type": addr_type,
        "key": VWORLD_API_KEY,
    }
    try:
        resp = requests.get(VWORLD_GEOCODE_URL, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        raise AddressAPIError(f"VWorld API 호출 실패: {e}") from e


def _parse_sido_sigungu(address: str) -> tuple[str, str]:
    """주소 문자열에서 시/도, 시/군/구 추출"""
    parts = address.split()
    sido = parts[0] if len(parts) > 0 else ""
    sigungu = parts[1] if len(parts) > 1 else ""
    return sido, sigungu


if __name__ == "__main__":
    from dataclasses import asdict
    import json

    test_cases = [
        ("도로명", "서울특별시 강남구 테헤란로 521"),
        ("지번",   "서울특별시 강남구 삼성동 169"),
    ]
    api = AddressAPI()
    for label, addr in test_cases:
        print(f"\n[{label}] {addr}")
        try:
            loc = api.get_coordinates(addr)
            print(json.dumps(asdict(loc), ensure_ascii=False, indent=2))
        except AddressAPIError as e:
            print(f"  오류: {e}")
