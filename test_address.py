# -*- coding: utf-8 -*-
"""
실제 주소 → 건축물대장 전체 흐름 테스트
VWorld에서 찾을 수 있는 주소로 테스트
"""
import sys, requests, json, warnings
sys.path.insert(0, ".")
from config import VWORLD_API_KEY, BUILDING_API_KEY

BASE_ADDR    = "https://api.vworld.kr/req/address"
BASE_BLDG    = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"

# VWorld에서 찾을 수 있는 실제 테스트 주소
TEST_ADDRESSES = [
    ("parcel", "서울특별시 강남구 개포동 100"),
    ("parcel", "서울특별시 서초구 서초동 1700"),
    ("parcel", "서울특별시 마포구 합정동 100"),
    ("road",   "서울특별시 서초구 서초대로 398"),
]

def vworld_to_pnu(addr_type: str, address: str) -> str | None:
    r = requests.get(BASE_ADDR, params={
        "service": "address", "request": "getcoord",
        "address": address, "format": "json",
        "type": addr_type, "key": VWORLD_API_KEY,
    }, timeout=10)
    data = r.json()
    if data.get("response", {}).get("status") != "OK":
        return None
    pnu = (
        data.get("response", {})
            .get("refined", {})
            .get("structure", {})
            .get("level4LC", "")
    )
    return pnu if len(pnu) == 19 else None


def fetch_building(pnu: str) -> dict | None:
    params = {
        "serviceKey": BUILDING_API_KEY,
        "sigunguCd": pnu[0:5],
        "bjdongCd":  pnu[5:10],
        "bun":       pnu[11:15],
        "ji":        pnu[15:19],
        "_type":     "json",
    }
    r = requests.get(BASE_BLDG, params=params, timeout=10)
    data = r.json()
    items = (
        data.get("response", {})
            .get("body", {})
            .get("items", {})
            .get("item", [])
    )
    if not items:
        return None
    return items if isinstance(items, dict) else items[0]


for addr_type, address in TEST_ADDRESSES:
    print(f"\n{'='*60}")
    print(f"주소: {address}  [{addr_type}]")

    pnu = vworld_to_pnu(addr_type, address)
    if not pnu:
        print("  VWorld: 주소 조회 실패")
        continue
    print(f"  VWorld PNU: {pnu}")

    item = fetch_building(pnu)
    if not item:
        print("  건축물대장: 데이터 없음")
        continue

    print(f"  건물명:    {item.get('bldNm', '(없음)')}")
    print(f"  용도:      {item.get('mainPurpsCdNm', '')}")
    print(f"  구조:      {item.get('strctCdNm', '')}")
    print(f"  지상층:    {item.get('grndFlrCnt', '')}층")
    print(f"  건축면적:  {item.get('archArea', '')} m²")
    print(f"  지붕형태:  {item.get('roofCdNm', '')}")
