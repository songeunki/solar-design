from __future__ import annotations
import asyncio
import base64
import json
import os
import pathlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

import requests as _req
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from api.pipeline import run_pipeline

_GH_REPO = "songeunki/solar-design"
_GH_PATH = "data/analysis_log.json"
_GH_API  = f"https://api.github.com/repos/{_GH_REPO}/contents/{_GH_PATH}"


def _gh_headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }


def _get_client_ip(websocket: WebSocket) -> str:
    forwarded = websocket.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return websocket.client.host if websocket.client else "unknown"


def _append_log(address: str, result: dict, ip: str = "unknown") -> None:
    if not os.environ.get("GITHUB_TOKEN"):
        return

    entry = {
        "timestamp":   datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S"),
        "ip":          ip,
        "address":     address,
        "capacity_kw": result.get("system", {}).get("totalKw", 0),
        "annual_kwh":  result.get("system", {}).get("yearlyTotal", 0),
        "roi_years":   result.get("financial", {}).get("paybackYear", 0),
        "azimuth_deg": result.get("building", {}).get("azimuth", 180),
    }

    headers = _gh_headers()
    sha: str | None = None
    logs: list = []

    # 1. 현재 파일 조회
    try:
        r = _req.get(_GH_API, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            sha = data["sha"]
            logs = json.loads(base64.b64decode(data["content"]).decode("utf-8"))
    except Exception:
        pass

    # 2. 새 항목 추가 후 PUT
    logs.append(entry)
    new_content = base64.b64encode(
        json.dumps(logs, ensure_ascii=False, indent=2).encode("utf-8")
    ).decode("ascii")

    body: dict = {
        "message": f"log: {address} ({entry['timestamp']})",
        "content": new_content,
    }
    if sha:
        body["sha"] = sha

    try:
        _req.put(_GH_API, headers=headers, json=body, timeout=15)
    except Exception:
        pass

router = APIRouter(tags=["analyze"])


class AnalyzeRequest(BaseModel):
    address: str
    azimuth_override: float | None = None


# ── REST ─────────────────────────────────────────────────────────────────────

@router.get("/satellite-map")
async def satellite_map(lat: float, lng: float, level: int = 2):
    """Playwright로 위성지도 캡처 → PNG 반환. 3D 뷰어 지면 텍스처용."""
    from output.report_generator import _fetch_static_map_square
    loop = asyncio.get_running_loop()
    try:
        b64 = await loop.run_in_executor(None, _fetch_static_map_square, lat, lng, level)
        if b64:
            return Response(content=base64.b64decode(b64), media_type="image/png",
                            headers={"Cache-Control": "public, max-age=86400"})
    except Exception:
        pass
    raise HTTPException(status_code=404, detail="위성 이미지 캡처 실패")



@router.get("/api/ordinance")
async def get_ordinance(sido: str = "", sigungu: str = ""):
    """시/도 + 시/군/구 기반 지자체 조례 조회 + Gemini 요약."""
    from analyzer.ordinance_api import fetch_ordinances
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, fetch_ordinances, sido, sigungu)
    return result


@router.get("/api/regulation")
async def get_regulation(address: str, pnu: str = ""):
    """PNU + 주소로 용도지역·토지특성 규제 분석."""
    from data_collector.regulation_api import RegulationAPI
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: RegulationAPI().fetch(address, pnu=pnu or None),
    )
    return result.to_dict()


@router.post("/analyze")
async def post_analyze(req: AnalyzeRequest):
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(
            None, run_pipeline, req.address, None, req.azimuth_override
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── 디버그: Railway 환경에서 API 실패 원인 진단 ───────────────────────────────

@router.get("/debug/building")
async def debug_building(address: str = "서울특별시 강남구 삼성동 169"):
    """각 단계별 성공/실패와 오류 메시지를 반환. Railway 환경 진단용."""
    from config import BUILDING_API_KEY, KAKAO_REST_API_KEY, JUSO_API_KEY, VWORLD_API_KEY
    from data_collector.building_api import (
        _pnu_via_juso, _pnu_via_kakao, _fetch_building_item,
        _building_info_from_osm, BuildingAPIError,
    )
    from data_collector.address_api import AddressAPI, AddressAPIError

    result: dict = {
        "address": address,
        "env": {
            "BUILDING_API_KEY":   "✓ set" if BUILDING_API_KEY   else "✗ NOT SET",
            "KAKAO_REST_API_KEY": "✓ set" if KAKAO_REST_API_KEY else "✗ NOT SET",
            "JUSO_API_KEY":       "✓ set" if JUSO_API_KEY       else "✗ NOT SET",
            "VWORLD_API_KEY":     "✓ set" if VWORLD_API_KEY     else "✗ NOT SET",
        },
        "steps": {},
    }

    # Step 1: 좌표 조회
    loc = None
    try:
        loc = AddressAPI().get_coordinates(address)
        result["steps"]["address_api"] = {
            "status": "ok",
            "lat": loc.lat, "lng": loc.lng,
        }
    except AddressAPIError as e:
        result["steps"]["address_api"] = {"status": "error", "error": str(e)}

    # Step 2: Juso PNU
    pnu = None
    try:
        pnu = _pnu_via_juso(address)
        result["steps"]["juso_pnu"] = {"status": "ok", "pnu": pnu}
    except BuildingAPIError as e:
        result["steps"]["juso_pnu"] = {"status": "error", "error": str(e)}

    # Step 3: Kakao PNU (Juso 실패 시에도 독립 테스트)
    kakao_pnu = None
    try:
        kakao_pnu = _pnu_via_kakao(address)
        result["steps"]["kakao_pnu"] = {"status": "ok", "pnu": kakao_pnu}
        if pnu is None:
            pnu = kakao_pnu
    except BuildingAPIError as e:
        result["steps"]["kakao_pnu"] = {"status": "error", "error": str(e)}

    # Step 4: 건축물대장 API — 일반표제부 / 총괄표제부 각각 테스트
    best_pnu = kakao_pnu or pnu
    if best_pnu:
        from data_collector.building_api import (
            _call_building_api, BUILDING_TITLE_URL, BUILDING_RECAP_URL,
        )
        base_params = {
            "serviceKey": BUILDING_API_KEY,
            "sigunguCd":  best_pnu[0:5],
            "bjdongCd":   best_pnu[5:10],
            "bun":        best_pnu[11:15],
            "ji":         best_pnu[15:19],
            "_type":      "json",
            "numOfRows":  10,
        }

        for api_name, url in [
            ("일반표제부(getBrTitleInfo)",   BUILDING_TITLE_URL),
            ("총괄표제부(getBrRecapTitleInfo)", BUILDING_RECAP_URL),
        ]:
            try:
                item = _call_building_api(url, base_params)
                result["steps"][api_name] = {
                    "status": "ok",
                    "archArea":       item.get("archArea"),
                    "totArea":        item.get("totArea"),
                    "grndFlrCnt":     item.get("grndFlrCnt"),
                    "mainPurpsCdNm":  item.get("mainPurpsCdNm"),
                    "roofCdNm":       item.get("roofCdNm"),
                    "strctCdNm":      item.get("strctCdNm"),
                }
            except BuildingAPIError as e:
                result["steps"][api_name] = {"status": "error", "error": str(e)}
    else:
        result["steps"]["building_api"] = {"status": "skip", "reason": "PNU 확보 실패"}

    # Step 5: V-World WFS polygon 조회
    if loc:
        try:
            from data_collector.vworld_polygon import get_building_polygon
            vw_area, vw_az, vw_ew, vw_ns, vw_poly = get_building_polygon(loc.lat, loc.lng)
            result["steps"]["vworld_wfs"] = {
                "status":        "ok" if vw_poly else "no_data",
                "area_m2":       vw_area,
                "azimuth_deg":   vw_az,
                "building_ew_m": vw_ew,
                "building_ns_m": vw_ns,
                "polygon_pts":   len(vw_poly) if vw_poly else 0,
            }
        except Exception as e:
            result["steps"]["vworld_wfs"] = {"status": "error", "error": str(e)}

        # Step 6: OSM Overpass fallback
        try:
            area, azimuth, ew_m, ns_m, _poly = _building_info_from_osm(loc.lat, loc.lng)
            result["steps"]["osm"] = {
                "status":        "ok" if area else "no_data",
                "area_m2":       area,
                "azimuth_deg":   azimuth,
                "building_ew_m": ew_m,
                "building_ns_m": ns_m,
                "polygon_pts":   len(_poly) if _poly else 0,
            }
        except Exception as e:
            result["steps"]["osm"] = {"status": "error", "error": str(e)}
    else:
        result["steps"]["vworld_wfs"] = {"status": "skip", "reason": "좌표 조회 실패"}
        result["steps"]["osm"]        = {"status": "skip", "reason": "좌표 조회 실패"}

    return result


# ── WebSocket ─────────────────────────────────────────────────────────────────

@router.websocket("/ws/analyze")
async def ws_analyze(websocket: WebSocket):
    """단일 주소 분석 — 진행상황 실시간 전송.

    클라이언트 → 서버: {"address": "서울특별시 ..."}
    서버 → 클라이언트:
      {"type": "progress", "step": 1, "total": 5, "message": "주소 조회"}
      {"type": "result",   "data": {...}}
      {"type": "error",    "message": "..."}
    """
    await websocket.accept()

    try:
        data    = await websocket.receive_json()
        address = data.get("address", "").strip()
        if not address:
            await websocket.send_json({"type": "error", "message": "address 필드가 비어 있습니다."})
            await websocket.close()
            return
        # 사용자 방위각 override (0~360 범위 검증)
        azimuth_override: float | None = None
        raw_az = data.get("azimuth_override")
        if raw_az is not None:
            try:
                v = float(raw_az)
                if 0 <= v <= 360:
                    azimuth_override = v
            except (TypeError, ValueError):
                pass
    except WebSocketDisconnect:
        return

    client_ip = _get_client_ip(websocket)
    loop:  asyncio.AbstractEventLoop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict]       = asyncio.Queue()

    def on_progress(step: int, total: int, message: str) -> None:
        asyncio.run_coroutine_threadsafe(
            queue.put({"type": "progress", "step": step, "total": total, "message": message}),
            loop,
        )

    def run() -> None:
        try:
            result = run_pipeline(address, on_progress, azimuth_override=azimuth_override)
            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "result", "data": result}),
                loop,
            )
            try:
                _append_log(address, result, ip=client_ip)
            except Exception:
                pass
        except Exception as exc:
            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "error", "message": str(exc)}),
                loop,
            )

    loop.run_in_executor(ThreadPoolExecutor(max_workers=1), run)

    try:
        while True:
            msg = await queue.get()
            await websocket.send_json(msg)
            if msg["type"] in ("result", "error"):
                break
    except WebSocketDisconnect:
        pass
    finally:
        await websocket.close()
