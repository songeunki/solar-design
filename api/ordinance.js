// Vercel Serverless Function — 태양광 자치법규 조회 (Gemini AI 기반)
// IP 제한 없이 어디서나 호출 가능

export const config = { regions: ['icn1'] };

const GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent';

async function queryGemini(apiKey, sido, sigungu) {
  const region = [sido, sigungu].filter(Boolean).join(' ');

  const prompt = `당신은 한국 태양광 정책 전문가입니다.
${region}의 태양광 관련 자치법규(조례) 정보를 제공해주세요.

반드시 아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{
  "ordinances": [
    {
      "title": "실제 조례명 (정확히)",
      "organ": "${sigungu || sido}",
      "date": "공포일자 YYYYMMDD (모르면 빈문자열)",
      "note": "조례 주요 내용 한 줄"
    }
  ],
  "restrictions": "태양광 설치 제한 사항 1-2문장",
  "support": "보조금·융자 등 지원 내용 1-2문장",
  "procedure": "허가·신고 절차 요약 1-2문장"
}

조건:
- 실제 존재하는 조례만 포함 (확실하지 않으면 제외)
- 없으면 ordinances: []
- 광역시도 조례와 시군구 조례 모두 포함`;

  const resp = await fetch(`${GEMINI_URL}?key=${apiKey}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: { temperature: 0.1, maxOutputTokens: 1024 },
    }),
  });

  if (!resp.ok) return null;

  const data  = await resp.json();
  const text  = data?.candidates?.[0]?.content?.parts?.[0]?.text || '';
  const match = text.match(/\{[\s\S]*\}/);
  if (!match) return null;

  return JSON.parse(match[0]);
}

export default async function handler(req, res) {
  const { sido = '', sigungu = '' } = req.query;
  const geminiKey = process.env.GEMINI_API_KEY || '';

  const fallbackUrl = `https://www.law.go.kr/ordinSc.do?query=${encodeURIComponent('태양광')}`;

  const empty = {
    found: false,
    message: '해당 지역 관련 조례를 찾지 못했습니다.',
    ordinances: [], summary: null,
    fallback_url: fallbackUrl,
    sido, sigungu, source: 'none',
  };

  if (!geminiKey || !sido) return res.status(200).json(empty);

  let result = null;
  try {
    result = await queryGemini(geminiKey, sido, sigungu);
  } catch (_) {}

  if (!result) return res.status(200).json({ ...empty, source: 'gemini_error' });

  const ordinances = (result.ordinances || [])
    .map(o => ({
      title:  (o.title  || '').trim(),
      organ:  (o.organ  || sigungu || sido).trim(),
      date:   (o.date   || '').trim(),
      note:   (o.note   || '').trim(),
      link:   fallbackUrl,
    }))
    .filter(o => o.title && !/^\d+$/.test(o.title) && o.title.length >= 5);

  const hasSummary = result.restrictions || result.support || result.procedure;
  const summary = hasSummary
    ? { restrictions: result.restrictions || '', support: result.support || '', procedure: result.procedure || '' }
    : null;

  return res.status(200).json({
    found:        ordinances.length > 0,
    message:      ordinances.length === 0 ? '해당 지역 관련 조례를 찾지 못했습니다.' : '',
    ordinances:   ordinances.slice(0, 5),
    summary,
    fallback_url: fallbackUrl,
    sido, sigungu, source: 'gemini',
  });
}
