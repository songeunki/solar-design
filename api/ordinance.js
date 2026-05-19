export const config = { regions: ['icn1'] };

const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent';

async function queryGemini(apiKey, sido, sigungu) {
  const region = [sido, sigungu].filter(Boolean).join(' ');
  const prompt = `당신은 대한민국 태양광 발전 관련 지자체 조례 전문가입니다.
${region}의 태양광 발전 설치 관련 주요 조례 내용을 아래 JSON 형식으로만 응답하세요.
마크다운 코드블록 없이 순수 JSON만 출력하세요.

{
  "region": "${region}",
  "permit_threshold_kw": 100,
  "setback_residential_m": 100,
  "setback_road_m": 20,
  "noise_limit_db": 45,
  "max_slope_deg": 15,
  "landscape_review": true,
  "notes": "주요 특이사항 1~2줄",
  "source": "조례 출처 또는 추정 근거",
  "confidence": "high/medium/low"
}`;

  const res = await fetch(`${GEMINI_URL}?key=${apiKey}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: { temperature: 0.2, maxOutputTokens: 1024 }
    })
  });

  const data = await res.json();
  if (data.error) throw new Error(data.error.message);
  return data?.candidates?.[0]?.content?.parts?.[0]?.text || '';
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  if (req.method === 'OPTIONS') return res.status(200).end();

  const { sido, sigungu, debug } = req.query;

  const response = {
    GEMINI_API_KEY_set: !!GEMINI_API_KEY,
    GEMINI_API_KEY_prefix: GEMINI_API_KEY ? GEMINI_API_KEY.substring(0, 10) + '...' : null,
    sido,
    sigungu
  };

  if (!GEMINI_API_KEY) {
    return res.status(500).json({ ...response, error: 'GEMINI_API_KEY 환경변수 미설정' });
  }

  if (!sido || !sigungu) {
    return res.status(400).json({ ...response, error: 'sido, sigungu 파라미터 필요' });
  }

  try {
    const start = Date.now();
    const text = await queryGemini(GEMINI_API_KEY, sido, sigungu);
    const elapsed = Date.now() - start;

    let ordinance;
    try {
      ordinance = JSON.parse(text.replace(/```json|```/g, '').trim());
    } catch {
      ordinance = { raw: text };
    }

    return res.status(200).json({
      ...response,
      gemini_ok: true,
      model_used: 'gemini-2.5-flash',
      elapsed_ms: elapsed,
      ordinance,
      ...(debug === '1' ? { raw_text: text } : {})
    });
  } catch (err) {
    return res.status(500).json({
      ...response,
      gemini_ok: false,
      error: err.message
    });
  }
}
