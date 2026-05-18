// Vercel Serverless Function — 자치법규 조회
// law.go.kr DRF lawSearch.do API 호출

const SEARCH_URL = 'https://www.law.go.kr/DRF/lawSearch.do';
const KEYWORDS   = ['태양광', '신재생에너지'];

export default async function handler(req, res) {
  const { sido = '', sigungu = '' } = req.query;
  const OC = process.env.LAW_API_KEY || '';

  const empty = {
    found: false,
    message: '해당 지역 관련 조례를 찾지 못했습니다.',
    ordinances: [],
    summary: null,
    fallback_url: 'https://www.law.go.kr/ordinSc.do?query=태양광',
    sido,
    sigungu,
  };

  if (!OC) return res.status(200).json(empty);

  const ordinances = [];

  for (const kw of KEYWORDS) {
    try {
      const params = new URLSearchParams({
        OC, target: 'ordin', type: 'JSON', display: '20', page: '1', query: kw,
      });
      const resp = await fetch(`${SEARCH_URL}?${params}`);
      if (!resp.ok) continue;
      const data = await resp.json();
      const raw  = data?.OrdinSearch?.law ?? [];
      const laws = Array.isArray(raw) ? raw : [raw];

      for (const law of laws) {
        const title = (law['자치법규명']   || '').trim();
        const organ = (law['지자체기관명'] || '').trim();

        if (!title || /^\d+$/.test(title) || title.length < 5) continue;

        if (sido && organ) {
          const sidoMatch = organ.includes(sido.slice(0, 2)) || sido.slice(0, 2).length > 0 && sido.includes(organ.slice(0, 2));
          const sgMatch   = sigungu && (organ.includes(sigungu) || sigungu.includes(organ));
          if (!sidoMatch && !sgMatch) continue;
        }

        if (!ordinances.find(o => o.title === title)) {
          const mst = law['자치법규일련번호'] || '';
          ordinances.push({
            title,
            organ,
            date: law['공포일자'] || '',
            link: mst
              ? `https://www.law.go.kr/ordinInfoP.do?ordinSeq=${mst}`
              : `https://www.law.go.kr/ordinSc.do?query=${encodeURIComponent(kw)}`,
          });
        }
      }
    } catch (_) { /* silent */ }
  }

  res.status(200).json({
    found:        ordinances.length > 0,
    message:      ordinances.length === 0 ? '해당 지역 관련 조례를 찾지 못했습니다.' : '',
    ordinances:   ordinances.slice(0, 5),
    summary:      null,
    fallback_url: 'https://www.law.go.kr/ordinSc.do?query=태양광',
    sido,
    sigungu,
  });
}
