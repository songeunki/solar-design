"""공공데이터포털 KPX SMP 단가 조회.

API: 한국전력거래소_계통한계가격 및 수요예측(하루전 발전계획용)
endpoint: https://apis.data.go.kr/B552115/SmpWithForecastDemand/getSmpWithForecastDemand

거래시간 표기: hour=N → (N-1)시~N시 구간.
따라서 실제 발전시간대 09:00~17:00 = hour in [10, 11, 12, 13, 14, 15, 16, 17].

예시 호출:
  curl "https://apis.data.go.kr/B552115/SmpWithForecastDemand/getSmpWithForecastDemand
        ?serviceKey=XXX&pageNo=1&numOfRows=50&dataType=json&date=20260521"

환경변수 KPX_API_KEY: 공공데이터포털(data.go.kr) 발급 인증키.
"""
from __future__ import annotations
import logging
import os
from datetime import date, timedelta

import requests

logger = logging.getLogger(__name__)

_URL = "https://apis.data.go.kr/B552115/SmpWithForecastDemand/getSmpWithForecastDemand"

# 실제 발전시간대 09:00~17:00 → API hour 표기 [10, 11, ..., 17]
# (API hour=N 은 N-1시~N시 구간을 의미)
GENERATION_HOURS: list[int] = list(range(10, 18))


def _to_items(raw_items: object) -> list[dict]:
    """공공데이터포털 공통 이슈: 결과 1개면 dict, 여러 개면 list로 반환."""
    if isinstance(raw_items, dict):
        return [raw_items]
    if isinstance(raw_items, list):
        return raw_items
    return []


def _fetch_date(api_key: str, query_date: str) -> dict | None:
    """단일 날짜 API 호출 → 성공 시 결과 dict, 실패·데이터 없음 시 None.

    Args:
        query_date: YYYYMMDD 형식 문자열
    """
    resp = requests.get(
        _URL,
        params={
            "serviceKey": api_key,
            "pageNo":     "1",
            "numOfRows":  "50",   # 24h × 2지역(육지/제주) = 48 + 여유
            "dataType":   "json",
            "date":       query_date,
        },
        timeout=8,
    )
    resp.raise_for_status()

    body = resp.json().get("response", {})
    header = body.get("header", {})
    if header.get("resultCode") != "00":
        logger.warning("KPX SMP API resultCode=%s msg=%s (date=%s)",
                       header.get("resultCode"), header.get("resultMsg"), query_date)
        return None

    raw_items = body.get("body", {}).get("items", {}).get("item")
    items = _to_items(raw_items)
    if not items:
        logger.debug("KPX SMP: items 비어있음 (date=%s)", query_date)
        return None

    prices: list[float] = []
    for item in items:
        if str(item.get("areaName", "")).strip() != "육지":
            continue
        try:
            hour = int(item["hour"])
        except (KeyError, ValueError, TypeError):
            continue
        if hour not in GENERATION_HOURS:
            continue
        try:
            prices.append(float(item["smp"]))
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("KPX SMP: smp 파싱 실패 item=%s err=%s", item, exc)
            continue

    if not prices:
        logger.debug("KPX SMP: 발전시간대 육지 데이터 없음 (date=%s)", query_date)
        return None

    avg = round(sum(prices) / len(prices), 1)
    d = query_date  # YYYYMMDD
    return {
        "price":        avg,
        "date":         f"{d[:4]}-{d[4:6]}-{d[6:]}",
        "sample_count": len(prices),
    }


def get_smp_price() -> dict:
    """육지 발전시간대(09:00~17:00) SMP 평균 단가 조회.

    날짜 재시도: 오늘 → 어제 → 그제
    (당일 데이터는 23시 이후 갱신되므로 통상 전일 데이터 사용)

    Returns:
        성공: {
            "price":        float,          # 원/kWh, 소수 첫째자리 반올림
            "date":         "YYYY-MM-DD",
            "source":       "KPX 실시간 (발전시간대 평균)",
            "sample_count": int,            # 평균에 사용된 시간대 수
            "hours_used":   "09:00-17:00",
        }
        실패: {
            "price":  float,                # admin_config revenue_per_kwh
            "date":   None,
            "source": "관리자 설정 기준",
        }
    """
    api_key = os.getenv("KPX_API_KEY", "")

    if not api_key:
        logger.warning("KPX_API_KEY 환경변수가 설정되지 않음. fallback 사용.")
    else:
        for days_ago in (0, 1, 2):
            query_date = (date.today() - timedelta(days=days_ago)).strftime("%Y%m%d")
            try:
                result = _fetch_date(api_key, query_date)
                if result:
                    return {
                        "price":        result["price"],
                        "date":         result["date"],
                        "source":       "KPX 실시간 (발전시간대 평균)",
                        "sample_count": result["sample_count"],
                        "hours_used":   "09:00-17:00",
                    }
            except requests.HTTPError as exc:
                logger.warning("KPX SMP HTTP 오류 (date=%s): %s", query_date, exc)
            except Exception as exc:
                logger.warning("KPX SMP 예외 (date=%s): %s", query_date, exc)

    from config import get_admin_finance
    fin = get_admin_finance()
    return {
        "price":  fin["revenue_per_kwh"],
        "date":   None,
        "source": "관리자 설정 기준",
    }


if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(message)s")

    key = os.getenv("KPX_API_KEY", "")
    if not key:
        print("[!] KPX_API_KEY 환경변수 없음 → fallback 반환 예정\n")

    result = get_smp_price()
    print(json.dumps(result, ensure_ascii=False, indent=2))
