"""지자체 조례 실시간 조회 + Gemini 3줄 요약."""
from __future__ import annotations
import json, os, re
import requests
from config import GEMINI_API_KEY

LAW_API_KEY = os.environ.get("LAW_API_KEY", "")
_LAW_URL    = "https://www.law.go.kr/DRF/lawService.do"
_KEYWORDS   = ["태양광", "신재생에너지"]


def fetch_ordinances(sido: str, sigungu: str) -> dict:
    """sido/sigungu 기반 자치법규 조회 후 Gemini 요약."""
    ordinances: list[dict] = []

    if LAW_API_KEY:
        for kw in _KEYWORDS:
            try:
                resp = requests.get(
                    _LAW_URL,
                    params={
                        "OC":      LAW_API_KEY,
                        "target":  "ordin",
                        "type":    "JSON",
                        "query":   f"{sigungu} {kw}",
                        "display": 3,
                        "page":    1,
                    },
                    timeout=8,
                )
                resp.raise_for_status()
                data  = resp.json()
                laws  = data.get("OrdinService", {}).get("law", [])
                if isinstance(laws, dict):
                    laws = [laws]
                for law in laws:
                    title = law.get("법령명한글", "")
                    if title and not any(o["title"] == title for o in ordinances):
                        ordinances.append({
                            "title": title,
                            "date":  law.get("공포일자", ""),
                            "link":  f"https://www.law.go.kr/ordinSc.do?query={kw}",
                        })
            except Exception:
                pass

    summary = _gemini_summarize(sido, sigungu, ordinances) if (ordinances and GEMINI_API_KEY) else None

    return {
        "found":        len(ordinances) > 0,
        "ordinances":   ordinances[:5],
        "summary":      summary,
        "fallback_url": "https://www.law.go.kr/ordinSc.do?query=태양광",
        "sido":         sido,
        "sigungu":      sigungu,
    }


def _gemini_summarize(sido: str, sigungu: str, ordinances: list[dict]) -> dict | None:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model  = genai.GenerativeModel("gemini-1.5-flash")
        titles = "\n".join(o["title"] for o in ordinances)
        prompt = (
            f"다음은 {sido} {sigungu}의 태양광 관련 조례 목록입니다:\n{titles}\n\n"
            "다음 3가지를 각각 1-2문장으로 요약하세요:\n"
            "1. 태양광 설치 관련 제한 사항\n"
            "2. 지원 내용 (보조금, 융자 등)\n"
            "3. 허가 절차 요약\n\n"
            '반드시 다음 JSON 형식으로만 응답: {"restrictions": "...", "support": "...", "procedure": "..."}'
        )
        resp  = model.generate_content(prompt)
        match = re.search(r'\{[^{}]+\}', resp.text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return None
