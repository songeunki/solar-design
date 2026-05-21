"""공공데이터포털 KPX SMP 실시간 단가 조회."""
from __future__ import annotations
import os
from datetime import date


def get_smp_price() -> tuple[float, str, str]:
    """당일 SMP 단가(원/kWh), 날짜(YYYY-MM-DD), 소스('smp' or 'admin') 반환.

    KPX_API_KEY 환경변수가 없거나 API 호출 실패 시 admin_config의 revenue_per_kwh로 fallback.
    """
    api_key = os.environ.get("KPX_API_KEY", "")
    if api_key:
        try:
            import requests
            resp = requests.get(
                "https://apis.data.go.kr/B551182/kpxElfnSmpInvtList/getElSmpInvtList",
                params={
                    "serviceKey": api_key,
                    "pageNo":     1,
                    "numOfRows":  1,
                    "dataType":   "json",
                    "recvKwh":    "A",
                },
                timeout=5,
            )
            resp.raise_for_status()
            body = resp.json()
            items = (
                body.get("response", {})
                    .get("body", {})
                    .get("items", {})
                    .get("item", [])
            )
            if items:
                item = items[0] if isinstance(items, list) else items
                price = float(item.get("smp", 0))
                trade_date = str(item.get("tradeDate", ""))
                if price > 0:
                    if len(trade_date) == 8:
                        trade_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"
                    elif not trade_date:
                        trade_date = date.today().isoformat()
                    return price, trade_date, "smp"
        except Exception:
            pass

    from config import get_admin_finance
    fin = get_admin_finance()
    return fin["revenue_per_kwh"], date.today().isoformat(), "admin"
