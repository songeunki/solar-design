from __future__ import annotations
import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

from api.pipeline import run_compare_pipeline

router = APIRouter(tags=["compare"])


class CompareRequest(BaseModel):
    addresses: list[str]


# ── REST ─────────────────────────────────────────────────────────────────────

@router.post("/compare")
async def post_compare(req: CompareRequest):
    """복수 주소 비교 분석 (동기 결과 반환)."""
    if len(req.addresses) < 2:
        raise HTTPException(status_code=422, detail="주소는 최소 2개 이상이어야 합니다.")
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, run_compare_pipeline, req.addresses)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── WebSocket ─────────────────────────────────────────────────────────────────

@router.websocket("/ws/compare")
async def ws_compare(websocket: WebSocket):
    """복수 주소 비교 분석 — 진행상황 실시간 전송.

    클라이언트 → 서버: {"addresses": ["주소1", "주소2", ...]}
    서버 → 클라이언트:
      {"type": "progress", "step": 1, "total": 11, "message": "[1/2] 주소1 — 주소 조회"}
      {"type": "result",   "data": {"html_path": "...", "addresses": [...]}}
      {"type": "error",    "message": "..."}
    """
    await websocket.accept()

    try:
        data      = await websocket.receive_json()
        addresses = [a.strip() for a in data.get("addresses", []) if a.strip()]
        if len(addresses) < 2:
            await websocket.send_json({"type": "error", "message": "주소는 최소 2개 이상이어야 합니다."})
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
            result = run_compare_pipeline(addresses, on_progress)
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
