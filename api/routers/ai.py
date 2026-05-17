"""AI 종합 평가 — Claude API 스트리밍 연동."""
from __future__ import annotations
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(tags=["ai"])


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

    # 월별 발전량 요약
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


# ── 엔드포인트 ────────────────────────────────────────────────────────────────

@router.post("/api/ai-evaluate")
async def ai_evaluate(req: AiEvaluateRequest):
    """Claude API로 태양광 입지 종합 평가 (SSE 스트리밍)."""
    from config import ANTHROPIC_API_KEY
    if not ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=503,
            detail=(
                "ANTHROPIC_API_KEY가 설정되지 않았습니다. "
                "Railway 환경변수에 ANTHROPIC_API_KEY를 추가해주세요."
            ),
        )

    try:
        import anthropic as _anthropic
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="anthropic 패키지가 설치되지 않았습니다. 서버를 재배포해주세요.",
        )

    client = _anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = _build_prompt(req)

    async def event_stream():
        try:
            with client.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=1800,
                system=(
                    "당신은 대한민국 태양광 발전 투자 전문가입니다. "
                    "간결하고 실용적인 평가를 제공합니다. "
                    "숫자는 구체적으로 언급하고, 불필요한 서론은 생략합니다."
                ),
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for text in stream.text_stream:
                    yield f"data: {json.dumps({'text': text}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        except _anthropic.AuthenticationError:
            yield f"data: {json.dumps({'error': 'API 인증 오류: ANTHROPIC_API_KEY를 확인하세요.'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
