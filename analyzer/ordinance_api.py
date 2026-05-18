"""지자체 조례 실시간 조회 + Gemini 3줄 요약."""
from __future__ import annotations
import json, os, re
import requests
from config import GEMINI_API_KEY

LAW_API_KEY = os.environ.get("LAW_API_KEY", "")
_SEARCH_URL = "https://www.law.go.kr/DRF/lawSearch.do"
_KEYWORDS   = ["태양광", "신재생에너지"]


def fetch_ordinances(sido: str, sigungu: str) -> dict:
    """sido/sigungu 기반 자치법규 조회 후 Gemini 요약."""
    ordinances: list[dict] = []

    if LAW_API_KEY:
        for kw in _KEYWORDS:
            try:
                resp = requests.get(
                    _SEARCH_URL,
                    params={
                        "OC":      LAW_API_KEY,
                        "target":  "ordin",
                        "type":    "JSON",
                        "query":   kw,
                        "display": 20,
                        "page":    1,
                    },
                    timeout=8,
                )
                resp.raise_for_status()
                data  = resp.json()
                laws  = data.get("OrdinSearch", {}).get("law", [])
                if isinstance(laws, dict):
                    laws = [laws]
                for law in laws:
                    title = (law.get("자치법규명", "") or "").strip()
                    organ = (law.get("지자체기관명", "") or "").strip()
                    # 숫자만이거나 5자 미만이면 제외
                    if not title or title.isdigit() or len(title) < 5:
                        continue
                    # 같은 시/도 또는 시/군/구 조례만 포함
                    if sido and organ:
                        sido_match = sido[:2] in organ or organ[:2] in sido
                        sg_match   = bool(sigungu) and (sigungu in organ or organ in sigungu)
                        if not sido_match and not sg_match:
                            continue
                    mst = law.get("자치법규일련번호", "")
                    link = f"https://www.law.go.kr/ordinInfoP.do?ordinSeq={mst}" if mst else f"https://www.law.go.kr/ordinSc.do?query={kw}"
                    if not any(o["title"] == title for o in ordinances):
                        ordinances.append({
                            "title": title,
                            "organ": organ,
                            "date":  law.get("공포일자", ""),
                            "link":  link,
                        })
            except Exception:
                pass

    summary = _gemini_summarize(sido, sigungu, ordinances) if (ordinances and GEMINI_API_KEY) else None

    return {
        "found":        len(ordinances) > 0,
        "message":      "" if ordinances else "해당 지역 관련 조례를 찾지 못했습니다.",
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
