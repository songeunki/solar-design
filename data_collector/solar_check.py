"""기존 태양광 설치 현장 감지 — 공공데이터포털 API 또는 폴백."""
from __future__ import annotations
import os
import requests


def check_existing_solar(lat: float, lng: float, radius_m: float = 100) -> dict:
    """
    주어진 좌표 근처에 기존 태양광 설비가 있는지 확인.
    SOLAR_DATA_API_KEY 환경변수 없으면 빈 결과 반환.
    """
    result: dict = {
        "has_existing":  False,
        "nearby_count":  0,
        "message":       None,
        "installations": [],
    }

    api_key = os.environ.get("SOLAR_DATA_API_KEY", "")
    if not api_key:
        return result

    try:
        resp = requests.get(
            "https://apis.data.go.kr/B552895/unis/getSolarGenFacility",
            params={
                "serviceKey": api_key,
                "pageNo":     1,
                "numOfRows":  10,
                "latitude":   lat,
                "longitude":  lng,
                "radius":     radius_m,
            },
            timeout=10,
        )
        data  = resp.json()
        items = (
            data.get("response", {})
                .get("body", {})
                .get("items", {})
                .get("item", [])
        )
        if isinstance(items, dict):
            items = [items]

        if items:
            result["has_existing"]  = True
            result["nearby_count"]  = len(items)
            result["installations"] = items[:3]
            result["message"] = (
                f"반경 {int(radius_m)}m 내 기존 태양광 설비 {len(items)}개 감지"
            )
    except Exception:
        pass

    return result
