"""공공데이터포털 KPX SMP 단가 조회.

API: 한국전력거래소_계통한계가격 및 수요예측
endpoint: https://apis.data.go.kr/B552115/SmpWithForecastDemand/getSmpWithForecastDemand

# 예시 호출:
# curl "https://apis.data.go.kr/B552115/SmpWithForecastDemand/getSmpWithForecastDemand?
#   serviceKey=XXX&pageNo=1&numOfRows=50&dataType=json&date=20260521"

환경변수 KPX_API_KEY: 공공데이터포털(data.go.kr) 발급 인증키.
"""
from __future__ import annotations
import os
from datetime import date, timedelta

_URL = "https://apis.data.go.kr/B552115/SmpWithForecastDemand/getSmpWithForecastDemand"

# 태양광 발전 시간대 (09~17시) — 이 범위만 평균 산정
# 향후 정책 변경 시 이 상수만 수정
_GEN_HOURS: frozenset[int] = frozenset(range(9, 18))  # 9, 10, ..., 17


def _parse_hour(raw: object) -> int | None:
    """API 시간 필드 → 정수 시(0~23).

    지원 형식: 1~24, "01"~"24", "0100"~"2400"
    """
    if raw is None:
        return None
    s = str(raw).strip()
    try:
        h = int(s[:2]) if len(s) >= 4 else int(s)
        if h > 24:               # 잘못된 값(예: "900" → 900) 거부
            return None
        return h % 24            # 24 → 0 (자정)
    except (ValueError, TypeError):
        return None


def _fetch(api_key: str, query_date: str) -> dict | None:
    """API 호출 → 육지 발전시간대 SMP 평균 반환. 실패 또는 데이터 없으면 None.

    Args:
        query_date: YYYYMMDD 형식 날짜 문자열

    Returns:
        {"price": float, "date": "YYYY-MM-DD", "raw_count": int} or None
    """
    import requests

    resp = requests.get(
        _URL,
        params={
            "serviceKey": api_key,
            "pageNo":     1,
            "numOfRows":  50,   # 24시간 × 2지역(육지+제주) 충분히 커버
            "dataType":   "json",
            "date":       query_date,
        },
        timeout=8,
    )
    resp.raise_for_status()

    body = resp.json().get("response", {})
    if body.get("header", {}).get("resultCode") != "00":
        return None

    items = body.get("body", {}).get("items", {})
    if isinstance(items, dict):
        items = items.get("item", [])
    if not items:
        return None

    prices: list[float] = []
    for item in (items if isinstance(items, list) else [items]):
        if str(item.get("areaName", "")).strip() != "육지":
            continue
        hour = _parse_hour(item.get("time") or item.get("hour") or item.get("baseTime"))
        if hour not in _GEN_HOURS:
            continue
        raw_smp = item.get("smp")
        if raw_smp in (None, "", "-"):
            continue
        try:
            prices.append(float(raw_smp))
        except (ValueError, TypeError):
            pass

    if not prices:
        return None

    avg = round(sum(prices) / len(prices), 2)
    d   = query_date
    return {
        "price":     avg,
        "date":      f"{d[:4]}-{d[4:6]}-{d[6:]}",
        "raw_count": len(prices),
    }


def get_smp_price() -> dict:
    """SMP 단가 조회 (발전 시간대 09~17시 육지 평균).

    날짜 재시도: 오늘 → 어제 → 그제 순서
    (당일 데이터는 당일 24시 이후 공시되므로 전일 데이터가 일반적)

    Returns:
        성공: {"price": float, "date": "YYYY-MM-DD",
               "source": "KPX 실시간", "raw_count": int}
        실패: {"price": float, "date": None,
               "source": "관리자 설정 기준"}
    """
    api_key = os.environ.get("KPX_API_KEY", "")

    if api_key:
        for days_ago in (0, 1, 2):
            query_date = (date.today() - timedelta(days=days_ago)).strftime("%Y%m%d")
            try:
                result = _fetch(api_key, query_date)
                if result:
                    return {
                        "price":     result["price"],
                        "date":      result["date"],
                        "source":    "KPX 실시간",
                        "raw_count": result["raw_count"],
                    }
            except Exception:
                continue

    from config import get_admin_finance
    fin = get_admin_finance()
    return {"price": fin["revenue_per_kwh"], "date": None, "source": "관리자 설정 기준"}
