"""AI 종합 평가 — Gemini API 스트리밍 연동."""
from __future__ import annotations
import asyncio
import json
import time
import threading
import requests as _req
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(tags=["ai"])

_GEMINI_STREAM_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:streamGenerateContent?alt=sse&key={key}"
)

# 429 방지: 호출 간 최소 간격
_call_lock    = threading.Lock()
_last_call_ts = 0.0
_MIN_INTERVAL = 0.5  # seconds

# 재시도 설정
_MAX_RETRIES   = 3
_RETRY_DELAYS  = [1, 2, 4]  # seconds (exponential backoff)


# ── 요청 모델 ─────────────────────────────────────────────────────────────────

class AiEvaluateRequest(BaseModel):
    address:      str  = ""
    building:     dict = {}
    system:       dict = {}
    financial:    dict = {}
    monthly_data: list = []


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def _fmt(v, divisor: float = 1, suffix: str = "", default: str = "-") -> str:
    """숫자를 안전하게 포맷. None / '-' → default."""
    if v is None or v == "-":
        return default
    try:
        val = float(v) / divisor
        return f"{val:,.0f}{suffix}"
    except (TypeError, ValueError):
        return str(v)


def _build_prompt(req: AiEvaluateRequest) -> str:
    b, s, f = req.building, req.system, req.financial

    return (
        f"태양광 투자 전문가로서 아래 설치 데이터를 바탕으로 5개 섹션을 한국어로 평가하세요.\n"
        f"섹션 제목은 ## 로 시작, 항목은 - bullet.\n\n"
        f"[건물] {req.address or '-'} | "
        f"{b.get('roofType','-')}/{b.get('roofShape','-')}지붕 "
        f"{b.get('floor','-')}층 {_fmt(b.get('archArea'), suffix='m²')}\n"
        f"[시스템] {s.get('totalKw','-')}kW·{s.get('panelCount','-')}매 "
        f"연{_fmt(s.get('yearlyTotal'), suffix='kWh')} "
        f"월평균{_fmt(s.get('monthlyAvg'), suffix='kWh')}\n"
        f"[재무] 설치비{_fmt(f.get('installCost'), divisor=10000, suffix='만원')} "
        f"연수익{_fmt(f.get('yearlyRevenue'), divisor=10000, suffix='만원')} "
        f"회수{f.get('paybackYear','-')}년 "
        f"20년순익{_fmt(f.get('netProfit20y'), divisor=10000, suffix='만원')}\n\n"
        "## 📊 입지 적합성 평가\n점수(100점)와 근거 2문장.\n\n"
        "## ✅ 강점\n3~4개 bullet.\n\n"
        "## ⚠️ 약점·리스크\n2~3개 bullet.\n\n"
        "## 💡 투자 권고\n추천/보통/비권고 판정 + 근거 2문장.\n\n"
        "## 📋 주의사항\n실무 주의사항 2~3개 bullet."
    )


# ── 단일 Gemini SSE 요청 ───────────────────────────────────────────────────────

def _iter_gemini_sse(prompt: str, api_key: str):
    """Gemini SSE 단일 요청 — 텍스트 청크 yield. 429는 HTTPError로 raise."""
    global _last_call_ts

    # 최소 호출 간격 보장 (debounce)
    with _call_lock:
        gap = _MIN_INTERVAL - (time.time() - _last_call_ts)
        if gap > 0:
            time.sleep(gap)
        _last_call_ts = time.time()

    url = _GEMINI_STREAM_URL.format(key=api_key)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": 1000,
            "temperature":     0.7,
        },
    }

    with _req.post(url, json=payload, stream=True, timeout=90) as resp:
        resp.raise_for_status()
        for raw_line in resp.iter_lines():
            if not raw_line:
                continue
            line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
            if not line.startswith("data: "):
                continue
            data_str = line[6:].strip()
            if not data_str or data_str == "[DONE]":
                continue
            try:
                chunk = json.loads(data_str)
                text = (
                    chunk.get("candidates", [{}])[0]
                         .get("content", {})
                         .get("parts", [{}])[0]
                         .get("text", "")
                )
                if text:
                    yield text
            except (json.JSONDecodeError, IndexError, KeyError):
                pass


# ── 엔드포인트 ────────────────────────────────────────────────────────────────

@router.post("/api/ai-evaluate")
async def ai_evaluate(req: AiEvaluateRequest):
    """Gemini 2.5 Flash로 태양광 입지 종합 평가 (SSE 스트리밍, 429 재시도 포함)."""
    from config import GEMINI_API_KEY
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail=(
                "GEMINI_API_KEY가 설정되지 않았습니다. "
                "Railway 환경변수에 GEMINI_API_KEY를 추가해주세요."
            ),
        )

    prompt  = _build_prompt(req)
    api_key = GEMINI_API_KEY

    # thread-safe queue: 튜플 (kind, payload) 또는 None(sentinel)
    queue: asyncio.Queue[tuple[str, str] | None] = asyncio.Queue()
    loop  = asyncio.get_event_loop()

    def _producer():
        """스레드 풀: Gemini 청크를 queue에 push. 429 시 최대 3회 재시도."""
        for attempt in range(_MAX_RETRIES):
            try:
                for text in _iter_gemini_sse(prompt, api_key):
                    loop.call_soon_threadsafe(queue.put_nowait, ("text", text))
                # 성공 — sentinel 전송 후 종료
                loop.call_soon_threadsafe(queue.put_nowait, None)
                return

            except _req.exceptions.HTTPError as exc:
                status = getattr(exc.response, "status_code", 0)

                if status == 429 and attempt < _MAX_RETRIES - 1:
                    delay = _RETRY_DELAYS[attempt]
                    # 프론트엔드에 재시도 상태 알림
                    retry_info = json.dumps(
                        {"attempt": attempt + 2, "total": _MAX_RETRIES, "delay": delay},
                        ensure_ascii=False,
                    )
                    loop.call_soon_threadsafe(queue.put_nowait, ("retrying", retry_info))
                    time.sleep(delay)
                    continue

                # 복구 불가 오류
                if status == 429:
                    msg = "요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요."
                else:
                    msg = f"Gemini API 오류 ({status})"
                loop.call_soon_threadsafe(queue.put_nowait, ("error", msg))
                loop.call_soon_threadsafe(queue.put_nowait, None)
                return

            except Exception as exc:
                loop.call_soon_threadsafe(queue.put_nowait, ("error", str(exc)))
                loop.call_soon_threadsafe(queue.put_nowait, None)
                return

        # 3회 모두 실패
        loop.call_soon_threadsafe(
            queue.put_nowait,
            ("error", "요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요."),
        )
        loop.call_soon_threadsafe(queue.put_nowait, None)

    asyncio.get_event_loop().run_in_executor(None, _producer)

    async def event_stream():
        while True:
            item = await queue.get()
            if item is None:
                yield "data: [DONE]\n\n"
                break
            kind, payload_text = item
            yield f"data: {json.dumps({kind: payload_text}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
