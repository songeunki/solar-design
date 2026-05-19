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

  const rawBody = await resp.text();

  if (!resp.ok) {
    throw new Error(`Gemini HTTP ${resp.status}: ${rawBody.slice(0, 300)}`);
  }

  let data;
  try {
    data = JSON.parse(rawBody);
  } catch (e) {
    throw new Error(`Gemini 응답 JSON 파싱 실패: ${rawBody.slice(0, 200)}`);
  }

  const text = data?.candidates?.[0]?.content?.parts?.[0]?.text || '';
  if (!text) {
    const blockReason  = data?.promptFeedback?.blockReason;
    const finishReason = data?.candidates?.[0]?.finishReason;
    throw new Error(
      `Gemini 응답 텍스트 없음 — blockReason=${blockReason ?? 'none'}, finishReason=${finishReason ?? 'none'}, raw=${JSON.stringify(data).slice(0, 200)}`
    );
  }

  const match = text.match(/\{[\s\S]*\}/);
  if (!match) {
    throw new Error(`Gemini 응답에 JSON 블록 없음 — text=${text.slice(0, 200)}`);
  }

  try {
    return JSON.parse(match[0]);
  } catch (e) {
    throw new Error(`Gemini JSON 파싱 실패 — ${e.message} — matched=${match[0].slice(0, 200)}`);
  }
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

  // ?debug=1 → 환경변수·API 호출 진단 정보 반환
  if (req.query.debug === '1') {
    const dbg = { GEMINI_API_KEY_set: !!geminiKey, GEMINI_API_KEY_prefix: geminiKey.slice(0, 8) + '...', sido, sigungu };
    if (geminiKey) {
      try {
        const region = [sido, sigungu].filter(Boolean).join(' ') || '서울특별시 강남구';
        const testResp = await fetch(`${GEMINI_URL}?key=${geminiKey}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ contents: [{ parts: [{ text: `"${region}" 태양광 조례 한 줄 요약` }] }], generationConfig: { maxOutputTokens: 100 } }),
        });
        const rawText = await testResp.text();
        dbg.gemini_http_status = testResp.status;
        dbg.gemini_ok = testResp.ok;
        if (testResp.ok) {
          let parsed;
          try { parsed = JSON.parse(rawText); } catch (_) { /* ignore */ }
          dbg.gemini_response_preview = parsed?.candidates?.[0]?.content?.parts?.[0]?.text?.slice(0, 200)
            ?? rawText.slice(0, 300);
          dbg.gemini_block_reason  = parsed?.promptFeedback?.blockReason ?? null;
          dbg.gemini_finish_reason = parsed?.candidates?.[0]?.finishReason ?? null;
        } else {
          dbg.gemini_error_body = rawText.slice(0, 400);
        }
      } catch (e) {
        dbg.gemini_fetch_error = e.message;
      }
    }
    return res.status(200).json(dbg);
  }

  console.log('[ordinance] key_set=%s sido=%s sigungu=%s', !!geminiKey, sido, sigungu);

  if (!geminiKey) return res.status(200).json({ ...empty, source: 'no_api_key' });
  if (!sido) return res.status(200).json(empty);

  let result = null;
  let geminiError = null;
  try {
    result = await queryGemini(geminiKey, sido, sigungu);
    console.log('[ordinance] gemini ok, ordinances=%d', result?.ordinances?.length ?? 0);
  } catch (e) {
    geminiError = e.message;
    console.error('[ordinance] gemini error:', e.message);
  }

  if (!result) return res.status(200).json({ ...empty, source: 'gemini_error', error: geminiError });

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
