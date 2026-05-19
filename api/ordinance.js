// Vercel Serverless Function — 자치법규 조회
//
// 우선순위:
//   1. data.go.kr 법제처 자치법규 API (DATA_GO_KR_KEY) — IP 제한 없음
//   2. law.go.kr DRF lawSearch.do    (LAW_API_KEY)      — IP 등록 필요
//
// data.go.kr 키 발급: https://www.data.go.kr → 법제처 자치법규 검색 → 활용신청

const DATA_GO_KR_URL = 'http://apis.data.go.kr/1170000/law/lawSearchList.do';
const LAW_GO_KR_URL  = 'https://www.law.go.kr/DRF/lawSearch.do';
const KEYWORDS       = ['태양광', '신재생에너지'];

async function searchWithDataGoKr(key, sido, sigungu) {
  const results = [];
  for (const kw of KEYWORDS) {
    try {
      const params = new URLSearchParams({
        serviceKey: key,
        target: 'ordin', type: 'JSON', display: '20', page: '1', query: kw,
      });
      const resp = await fetch(`${DATA_GO_KR_URL}?${params}`);
      if (!resp.ok) continue;
      const data = await resp.json();
      _extractLaws(data, kw, sido, sigungu, results);
    } catch (_) {}
  }
  return results;
}

async function searchWithLawGoKr(key, sido, sigungu) {
  const results = [];
  for (const kw of KEYWORDS) {
    try {
      const params = new URLSearchParams({
        OC: key, target: 'ordin', type: 'JSON', display: '20', page: '1', query: kw,
      });
      const resp = await fetch(`${LAW_GO_KR_URL}?${params}`);
      if (!resp.ok) continue;
      const data = await resp.json();
      _extractLaws(data, kw, sido, sigungu, results);
    } catch (_) {}
  }
  return results;
}

function _extractLaws(data, kw, sido, sigungu, out) {
  // data.go.kr: OrdinSearch.law  /  law.go.kr: OrdinSearch.law (동일 구조)
  const raw  = data?.OrdinSearch?.law ?? [];
  const laws = Array.isArray(raw) ? raw : (raw ? [raw] : []);

  for (const law of laws) {
    const title = (law['자치법규명'] || '').trim();
    const organ = (law['지자체기관명'] || '').trim();

    if (!title || /^\d+$/.test(title) || title.length < 5) continue;

    if (sido && organ) {
      const sidoMatch = organ.includes(sido.slice(0, 2)) || sido.slice(0, 2) && sido.includes(organ.slice(0, 2));
      const sgMatch   = sigungu && (organ.includes(sigungu) || sigungu.includes(organ));
      if (!sidoMatch && !sgMatch) continue;
    }

    if (!out.find(o => o.title === title)) {
      const mst = law['자치법규일련번호'] || '';
      out.push({
        title,
        organ,
        date: law['공포일자'] || '',
        link: mst
          ? `https://www.law.go.kr/ordinInfoP.do?ordinSeq=${mst}`
          : `https://www.law.go.kr/ordinSc.do?query=${encodeURIComponent(kw)}`,
      });
    }
  }
}

export default async function handler(req, res) {
  const { sido = '', sigungu = '' } = req.query;

  const dataKey = process.env.DATA_GO_KR_KEY || '';
  const lawKey  = process.env.LAW_API_KEY    || '';

  const empty = {
    found: false, message: '해당 지역 관련 조례를 찾지 못했습니다.',
    ordinances: [], summary: null,
    fallback_url: 'https://www.law.go.kr/ordinSc.do?query=태양광',
    sido, sigungu, source: 'none',
  };

  if (!dataKey && !lawKey) return res.status(200).json(empty);

  let ordinances = [];
  let source = '';

  // 1순위: data.go.kr (IP 제한 없음)
  if (dataKey) {
    ordinances = await searchWithDataGoKr(dataKey, sido, sigungu);
    source = 'data.go.kr';
  }

  // 2순위: law.go.kr 폴백 (IP 등록 필요)
  if (ordinances.length === 0 && lawKey) {
    ordinances = await searchWithLawGoKr(lawKey, sido, sigungu);
    source = 'law.go.kr';
  }

  res.status(200).json({
    found:        ordinances.length > 0,
    message:      ordinances.length === 0 ? '해당 지역 관련 조례를 찾지 못했습니다.' : '',
    ordinances:   ordinances.slice(0, 5),
    summary:      null,
    fallback_url: 'https://www.law.go.kr/ordinSc.do?query=태양광',
    sido, sigungu, source,
  });
}
