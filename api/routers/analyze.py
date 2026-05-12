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
    """단일 주소 분석 (동기 결과 반환)."""
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, run_pipeline, req.address)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


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
