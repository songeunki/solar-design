"""AI 종합 평가 — Gemini API 스트리밍 연동."""
from __future__ import annotations
import asyncio
import json
import requests as _req
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(tags=["ai"])

_GEMINI_STREAM_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:streamGenerateContent?alt=sse&key={key}"
)

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
    b  = req.building
    s  = req.system
    f  = req.financial
    md = req.monthly_data

    monthly_str = ""
    if md:
        items = [
            f"{d.get('month', f'{i+1}월')} {_fmt(d.get('kwh'), suffix='kWh')}"
            for i, d in enumerate(md)
        ]
        monthly_str = "  월별 발전량: " + " / ".join(items)

    return f"""당신은 대한민국 태양광 발전 투자 전문가입니다.
아래 분석 데이터를 바탕으로 해당 건물의 태양광 설치 타당성을 종합 평가하세요.

## 분석 대상

- **주소:** {req.address or '-'}
- **건물 용도/지붕:** {b.get('roofType', '-')} / {b.get('roofShape', '-')}형 지붕
- **층수 / 건축면적:** {b.get('floor', '-')}층 / {_fmt(b.get('archArea'), suffix=' m²')}

## 태양광 시스템

- 설치 용량: **{s.get('totalKw', '-')} kW** ({s.get('panelCount', '-')}매 × 640W)
- 인버터: {s.get('inverterKw', '-')} kW
- 연간 발전량: **{_fmt(s.get('yearlyTotal'), suffix=' kWh')}** (월 평균 {_fmt(s.get('monthlyAvg'), suffix=' kWh')})
{monthly_str}

## 재무 분석

- 총 설치비용: **{_fmt(f.get('installCost'), divisor=10000, suffix='만원')}**
- 연간 수익: **{_fmt(f.get('yearlyRevenue'), divisor=10000, suffix='만원/년')}**
- 투자 회수: **{f.get('paybackYear', '-')}년**
- 20년 순수익: **{_fmt(f.get('netProfit20y'), divisor=10000, suffix='만원')}**

---

아래 5개 섹션을 한국어로 작성하세요. 각 섹션 제목은 반드시 `## ` 로 시작하세요.

## 📊 입지 적합성 평가
100점 만점 점수와 판정 근거를 2~3문장으로 설명.

## ✅ 강점
3~5가지를 `- ` bullet으로 구체적으로 작성.

## ⚠️ 약점 · 리스크
2~4가지를 `- ` bullet으로 실질적 리스크 중심으로 작성.

## 💡 투자 권고
**추천 / 보통 / 비권고** 중 하나로 명확히 판정하고 2~3문장 근거 제시.

## 📋 주의사항
시공·법규·유지보수 관련 실무 주의사항 2~4가지를 `- ` bullet으로 작성."""


# ── Gemini 스트리밍 (동기, 스레드 풀에서 실행) ─────────────────────────────────

def _iter_gemini_chunks(prompt: str, api_key: str):
    """Gemini SSE 스트림을 동기적으로 이터레이션, 텍스트 청크 yield."""
    url = _GEMINI_STREAM_URL.format(key=api_key)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": 1800,
            "temperature":     0.7,
        },
        "systemInstruction": {
            "parts": [{
                "text": (
                    "당신은 대한민국 태양광 발전 투자 전문가입니다. "
                    "간결하고 실용적인 평가를 제공합니다. "
                    "숫자는 구체적으로 언급하고, 불필요한 서론은 생략합니다."
                )
            }]
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
    """Gemini 1.5 Flash로 태양광 입지 종합 평가 (SSE 스트리밍)."""
    from config import GEMINI_API_KEY
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail=(
                "GEMINI_API_KEY가 설정되지 않았습니다. "
                "Railway 환경변수에 GEMINI_API_KEY를 추가해주세요."
            ),
        )

    prompt   = _build_prompt(req)
    api_key  = GEMINI_API_KEY
    # thread-safe queue: Gemini 동기 I/O → async generator로 전달
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    loop  = asyncio.get_event_loop()

    def _producer():
        """스레드 풀: Gemini 청크를 queue에 push."""
        try:
            for text in _iter_gemini_chunks(prompt, api_key):
                loop.call_soon_threadsafe(queue.put_nowait, text)
        except _req.exceptions.HTTPError as exc:
            msg = f"Gemini API 오류 ({exc.response.status_code}): {exc.response.text[:200]}"
            loop.call_soon_threadsafe(queue.put_nowait, f"\n\n⚠️ {msg}")
        except Exception as exc:
            loop.call_soon_threadsafe(queue.put_nowait, f"\n\n⚠️ 오류: {exc}")
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

    asyncio.get_event_loop().run_in_executor(None, _producer)

    async def event_stream():
        while True:
            item = await queue.get()
            if item is None:
                yield "data: [DONE]\n\n"
                break
            yield f"data: {json.dumps({'text': item}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
