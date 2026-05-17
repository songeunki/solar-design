"""용도지역·토지특성 규제 분석."""
from __future__ import annotations
import xml.etree.ElementTree as ET
import requests
from dataclasses import dataclass, field
from config import LURIS_API_KEY, VWORLD_LAND_API_KEY

LURIS_URL       = "https://apis.data.go.kr/1613000/arLandUseInfoService/DTarLandUseInfo"
VWORLD_LAND_URL = "https://api.vworld.kr/ned/data/getLandCharacteristics"

_ZONE_RULES: dict[str, tuple[str, str]] = {
    "계획관리지역":      ("가능",    "계획관리지역 — 개발행위허가 후 태양광 설치 가능"),
    "생산관리지역":      ("조건부",  "생산관리지역 — 농업 보전 목적, 개발행위허가 필요"),
    "보전관리지역":      ("조건부",  "보전관리지역 — 행위제한 사항 개별 확인 필요"),
    "제1종전용주거지역":  ("조건부", "전용주거지역 — 건축법령 허용 조건 확인 필요"),
    "제2종전용주거지역":  ("조건부", "전용주거지역 — 건축법령 허용 조건 확인 필요"),
    "제1종일반주거지역":  ("조건부", "일반주거지역 — 건물 옥상·지붕 설치는 허용 가능"),
    "제2종일반주거지역":  ("조건부", "일반주거지역 — 건물 옥상·지붕 설치는 허용 가능"),
    "제3종일반주거지역":  ("조건부", "일반주거지역 — 건물 옥상·지붕 설치는 허용 가능"),
    "준주거지역":         ("조건부", "준주거지역 — 건축허가 조건 확인 필요"),
    "중심상업지역":      ("조건부", "상업지역 — 건축허가 조건 확인 필요"),
    "일반상업지역":      ("조건부", "상업지역 — 건축허가 조건 확인 필요"),
    "근린상업지역":      ("조건부", "상업지역 — 건물 부착형 태양광 허용 가능"),
    "유통상업지역":      ("조건부", "상업지역 — 건축허가 조건 확인 필요"),
    "전용공업지역":      ("조건부", "전용공업지역 — 용도 적합성 확인 필요"),
    "일반공업지역":      ("가능",   "공업지역 — 태양광 설치 유리한 환경"),
    "준공업지역":        ("가능",   "준공업지역 — 태양광 설치 가능"),
    "자연녹지지역":      ("조건부", "자연녹지지역 — 개발행위허가 필요"),
    "생산녹지지역":      ("조건부", "생산녹지지역 — 개발행위허가 필요"),
    "보전녹지지역":      ("불가",   "보전녹지지역 — 행위 제한, 설치 곤란"),
    "농림지역":          ("불가",   "농림지역 — 농업진흥구역 내 태양광 설치 불가"),
    "자연환경보전지역":  ("불가",   "자연환경보전지역 — 절대 보전, 설치 불가"),
}

_FEASIBILITY_ORDER = {"불가": 3, "조건부": 2, "가능": 1, "확인불가": 0}

_JIMOK_MAP: dict[str, str] = {
    "전": "전(밭)", "답": "답(논)", "과": "과수원",
    "목": "목장용지", "임": "임야", "광": "광천지",
    "염": "염전", "대": "대(주택·상가)", "공": "공장용지",
    "학": "학교용지", "주": "주차장", "유": "유원지",
    "종": "종교용지", "사": "사적지", "묘": "묘지", "잡": "잡종지",
}


@dataclass
class RegulationResult:
    pnu:             str
    zones:           list[str] = field(default_factory=list)
    zone_feasibility: str = "확인불가"
    zone_note:       str  = ""
    restrictions:    list[str] = field(default_factory=list)
    land_category:   str  = ""
    land_use_status: str  = ""
    terrain:         str  = ""
    is_farmland:     bool = False
    is_forest:       bool = False
    risk_level:      str  = "확인불가"
    risk_reasons:    list[str] = field(default_factory=list)
    kepco_url:       str  = "https://kepco.net.works/portal/index.do"
    errors:          list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "pnu":             self.pnu,
            "zones":           self.zones,
            "zoneFeasibility": self.zone_feasibility,
            "zoneNote":        self.zone_note,
            "restrictions":    self.restrictions,
            "landCategory":    self.land_category,
            "landUseStatus":   self.land_use_status,
            "terrain":         self.terrain,
            "isFarmland":      self.is_farmland,
            "isForest":        self.is_forest,
            "riskLevel":       self.risk_level,
            "riskReasons":     self.risk_reasons,
            "kepcoUrl":        self.kepco_url,
            "errors":          self.errors,
        }


class RegulationAPI:
    def fetch(self, address: str, pnu: str | None = None) -> RegulationResult:
        result = RegulationResult(pnu=pnu or "")
        if pnu:
            self._fetch_luris(pnu, result)
            self._fetch_vworld(pnu, result)
        else:
            result.errors.append("PNU 미확보 — 용도지역 조회 불가")
        self._assess_risk(result)
        return result

    def _fetch_luris(self, pnu: str, result: RegulationResult) -> None:
        """LURIS API — XML 응답 파싱."""
        import warnings
        from requests.exceptions import ConnectionError as ReqConnError
        from http.client import RemoteDisconnected

        if not LURIS_API_KEY:
            result.errors.append("LURIS_API_KEY 미설정")
            return
        try:
            params = {
                "serviceKey": LURIS_API_KEY,
                "pnu":        pnu,
                "numOfRows":  10,
                "pageNo":     1,
            }
            resp = requests.get(LURIS_URL, params=params, timeout=15)

            # 디버그: 실제 요청 URL + 응답 상태 + 응답 앞부분
            warnings.warn(
                f"[LURIS] PNU={pnu} status={resp.status_code} url={resp.url}",
                stacklevel=2,
            )
            warnings.warn(
                f"[LURIS] 응답 앞 500자: {resp.text[:500]}",
                stacklevel=2,
            )

            resp.raise_for_status()
            # XML 선언(<?xml ... encoding="UTF-8"?>)을 그대로 str에 넣으면
            # expat "multi-byte encodings not supported" 에러 발생 → 선언 제거 후 파싱
            resp.encoding = "utf-8"
            xml_text = resp.text.strip()
            if xml_text.startswith("<?xml"):
                xml_text = xml_text[xml_text.index("?>") + 2:].lstrip()
            root = ET.fromstring(xml_text or "<response/>")
        except (ReqConnError, RemoteDisconnected, OSError) as e:
            result.errors.append(f"외부 API 일시적 오류 (Railway 네트워크 불안정): {e}")
            return
        except Exception as e:
            result.errors.append(f"LURIS 조회 실패: {e}")
            return

        # 에러 코드 확인
        result_code = root.findtext("./header/resultCode") or ""
        if result_code not in ("00", "0000", ""):
            result_msg = root.findtext("./header/resultMsg") or ""
            result.errors.append(f"LURIS 오류 (resultCode={result_code}): {result_msg}")
            return

        items_el = root.findall("./body/items/item")
        if not items_el:
            result.errors.append("LURIS 용도지역 데이터 없음")
            return

        zones_set: set[str]    = set()
        restrictions: list[str] = []

        for item in items_el:
            dtype   = (item.findtext("prposAreaDstrcNm") or "").strip()
            area_nm = (item.findtext("prposAreaNm")      or "").strip()
            if not area_nm:
                continue
            if dtype == "용도지역":
                zones_set.add(area_nm)
            else:
                restrictions.append(area_nm)

        result.zones        = sorted(zones_set)
        result.restrictions = list(dict.fromkeys(restrictions))

        best      = "확인불가"
        best_note = ""
        for zone in result.zones:
            feasibility, note = _ZONE_RULES.get(zone, ("조건부", f"{zone} — 개별 확인 필요"))
            if _FEASIBILITY_ORDER.get(feasibility, 0) > _FEASIBILITY_ORDER.get(best, 0):
                best      = feasibility
                best_note = note

        if result.zones:
            result.zone_feasibility = best if best != "확인불가" else "조건부"
            result.zone_note        = best_note or f"{result.zones[0]} — 개별 확인 필요"
        else:
            result.zone_feasibility = "확인불가"
            result.zone_note        = "용도지역 데이터 없음"

    def _fetch_vworld(self, pnu: str, result: RegulationResult) -> None:
        """V-World NED 토지특성 API — JSON 응답 파싱."""
        if not VWORLD_LAND_API_KEY:
            result.errors.append("VWORLD_LAND_API_KEY 미설정")
            return
        import os
        domain = os.environ.get("VWORLD_DOMAIN", "solar-design-production.up.railway.app")
        try:
            resp = requests.get(
                VWORLD_LAND_URL,
                params={
                    "key":        VWORLD_LAND_API_KEY,
                    "pnu":        pnu,
                    "domain":     domain,
                    "format":     "json",
                    "numOfRows":  1,
                    "pageNo":     1,
                },
                timeout=12,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            result.errors.append(f"V-World 토지특성 조회 실패: {e}")
            return

        # 응답 구조: landCharacteristics.field[] 또는 response.result.landCharacteristics.field[]
        lc = (
            data.get("landCharacteristics")
            or data.get("response", {}).get("result", {}).get("landCharacteristics")
            or {}
        )
        fields = lc.get("field", [])
        if not fields:
            result.errors.append("V-World 토지특성 결과 없음")
            return

        for f in fields:
            name = (f.get("name")  or "").strip()
            val  = (f.get("value") or "").strip()
            if not val or val in ("-", "null", ""):
                continue
            if name == "jimok":
                result.land_category = _JIMOK_MAP.get(val, val)
                result.is_farmland   = val in ("전", "답", "과", "목")
                result.is_forest     = val == "임"
            elif name == "landUseStatus":
                result.land_use_status = val
            elif name == "heightDegree":
                result.terrain = val

    def _assess_risk(self, result: RegulationResult) -> None:
        reasons: list[str] = []

        if result.zone_feasibility == "불가":
            result.risk_level = "높음"
            reasons.append(result.zone_note or "설치 불가 용도지역")
        elif result.is_farmland:
            result.risk_level = "높음"
            reasons.append("농지 — 농지전용허가 필요, 농업진흥구역은 설치 불가")
        elif result.is_forest:
            result.risk_level = "높음"
            reasons.append("임야 — 산지전용허가 필요, 보전산지는 설치 불가")
        elif result.zone_feasibility == "조건부":
            result.risk_level = "보통"
            reasons.append(result.zone_note or "조건부 허용 지역 — 개별 허가 필요")
        elif result.zone_feasibility == "가능":
            result.risk_level = "낮음"
        else:
            result.risk_level = "확인불가"
            reasons.append("용도지역 정보 미확보 — 개별 확인 필요")

        result.risk_reasons = reasons
