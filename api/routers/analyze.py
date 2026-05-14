from __future__ import annotations
import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

from api.pipeline import run_pipeline

router = APIRouter(tags=["analyze"])


class AnalyzeRequest(BaseModel):
    address: str


# ── REST ─────────────────────────────────────────────────────────────────────

@router.post("/analyze")
async def post_analyze(req: AnalyzeRequest):
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, run_pipeline, req.address)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── 디버그: Railway 환경에서 API 실패 원인 진단 ───────────────────────────────

@router.get("/debug/building")
async def debug_building(address: str = "서울특별시 강남구 삼성동 169"):
    """각 단계별 성공/실패와 오류 메시지를 반환. Railway 환경 진단용."""
    from config import BUILDING_API_KEY, KAKAO_REST_API_KEY, JUSO_API_KEY, VWORLD_API_KEY
    from data_collector.building_api import (
        _pnu_via_juso, _pnu_via_kakao, _fetch_building_item,
        _building_area_from_osm, BuildingAPIError,
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

    # Step 4: 건축물대장 API (PNU 확보된 경우)
    if pnu:
        try:
            item = _fetch_building_item(pnu)
            result["steps"]["building_api"] = {
                "status":   "ok",
                "archArea": item.get("archArea"),
                "totArea":  item.get("totArea"),
                "grndFlrCnt": item.get("grndFlrCnt"),
                "mainPurpsCdNm": item.get("mainPurpsCdNm"),
                "roofCdNm": item.get("roofCdNm"),
                "strctCdNm": item.get("strctCdNm"),
            }
        except BuildingAPIError as e:
            result["steps"]["building_api"] = {"status": "error", "error": str(e)}
    else:
        result["steps"]["building_api"] = {"status": "skip", "reason": "PNU 확보 실패"}

    # Step 5: OSM Overpass
    if loc:
        try:
            area = _building_area_from_osm(loc.lat, loc.lng)
            result["steps"]["osm"] = {
                "status": "ok" if area else "no_data",
                "area_m2": area,
            }
        except Exception as e:
            result["steps"]["osm"] = {"status": "error", "error": str(e)}
    else:
        result["steps"]["osm"] = {"status": "skip", "reason": "좌표 조회 실패"}

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
    except WebSocketDisconnect:
        return

    loop:  asyncio.AbstractEventLoop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict]       = asyncio.Queue()

    def on_progress(step: int, total: int, message: str) -> None:
        asyncio.run_coroutine_threadsafe(
            queue.put({"type": "progress", "step": step, "total": total, "message": message}),
            loop,
        )

    def run() -> None:
        try:
            result = run_pipeline(address, on_progress)
            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "result", "data": result}),
                loop,
            )
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
