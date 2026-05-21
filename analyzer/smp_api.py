"""공공데이터포털 KPX SMP 단가 조회 (공식 API 2단계 fallback).

1차: 한국전력거래소_계통한계가격 및 수요예측(하루전 발전계획용)
     endpoint: getElSmpFrcst
2차: 한국전력거래소_계통한계가격(SMP) 실시간 조회
     endpoint: getElSmpInvtList
3차: admin_config revenue_per_kwh (기본 150원)

환경변수 KPX_API_KEY: 공공데이터포털(data.go.kr) 발급 인증키.
"""
from __future__ import annotations
import os
from datetime import date, timedelta

_BASE = "https://apis.data.go.kr/B551182"

# 1차: 계통한계가격 및 수요예측 (하루전 발전계획용)
_PRIMARY_URL  = f"{_BASE}/kpxElfnSmpFrcst/getElSmpFrcst"
# 2차: 계통한계가격 실시간 조회
_FALLBACK_URL = f"{_BASE}/kpxElfnSmpInvtList/getElSmpInvtList"


def _extract_item(items) -> tuple[float, str] | None:
    """items(list or dict)에서 (price, YYYY-MM-DD) 추출. 실패 시 None."""
    item = items[0] if isinstance(items, list) else items
    price = 0.0
    for key in ("smp", "avgSmp", "cpSmp"):
        raw = item.get(key)
        if raw not in (None, "", "-"):
            try:
                price = float(raw)
                break
            except (ValueError, TypeError):
                pass
    if price <= 0:
        return None

    raw_date = str(item.get("tradeDate") or item.get("baseDatetime") or "")
    if len(raw_date) >= 8:
        d = raw_date[:8]
        trade_date = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    else:
        trade_date = date.today().isoformat()
    return price, trade_date


def _call(url: str, api_key: str, base_date: str) -> tuple[float, str] | None:
    """API 호출 → (price, date) 반환. 실패 시 None."""
    import requests
    params = {
        "serviceKey": api_key,
        "pageNo":     1,
        "numOfRows":  1,
        "dataType":   "json",
        "recvKwh":    "A",           # 육지 (제주: B)
        "baseDatetime": base_date,   # YYYYMMDD
    }
    resp = requests.get(url, params=params, timeout=6)
    resp.raise_for_status()
    body  = resp.json().get("response", {}).get("body", {})
    items = body.get("items", {})
    if isinstance(items, dict):
        items = items.get("item", [])
    if not items:
        return None
    return _extract_item(items)


def get_smp_price() -> dict:
    """SMP 단가 조회.

    Returns:
        성공: {"price": float, "date": "YYYY-MM-DD", "source": "KPX 실시간"}
        실패: {"price": float, "date": None,          "source": "관리자 설정 기준"}
    """
    api_key = os.environ.get("KPX_API_KEY", "")

    if api_key:
        # 오늘 데이터 없으면 전일로 재시도 (당일 SMP는 늦게 공시될 수 있음)
        for days_ago in (0, 1):
            base_date = (date.today() - timedelta(days=days_ago)).strftime("%Y%m%d")
            for url in (_PRIMARY_URL, _FALLBACK_URL):
                try:
                    result = _call(url, api_key, base_date)
                    if result:
                        price, trade_date = result
                        return {"price": price, "date": trade_date, "source": "KPX 실시간"}
                except Exception:
                    continue

    from config import get_admin_finance
    fin = get_admin_finance()
    return {"price": fin["revenue_per_kwh"], "date": None, "source": "관리자 설정 기준"}
