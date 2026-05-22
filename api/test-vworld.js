// PoC: Vercel icn1에서 V-World WFS 직접 호출 검증 (임시 — 검증 후 삭제)
// 배포 전 Vercel 환경변수에 VWORLD_API_KEY 추가 필요

export const config = { regions: ['icn1'] };

const VWORLD_HEADERS = {
  'Referer':    'https://solar-design-opal.vercel.app/',
  'Origin':     'https://solar-design-opal.vercel.app',
  'User-Agent': 'Mozilla/5.0 (compatible; SolarDesign-Vercel/1.0)',
};

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');

  const apiKey = process.env.VWORLD_API_KEY || '';
  const envKeys = Object.keys(process.env).filter(k => k.includes('VWORLD') || k.includes('vworld'));
  // ?debug_all=1 → 모든 env key 이름 덤프 (값 제외, 진단용)
  if (req.query.debug_all === '1') {
    return res.status(200).json({
      all_env_keys: Object.keys(process.env).sort(),
      vworld_keys: envKeys,
      vercel_env: process.env.VERCEL_ENV || 'unknown',
      vworld_api_key_set: !!apiKey,
    });
  }
  if (!apiKey) {
    return res.status(500).json({
      error: 'VWORLD_API_KEY 환경변수 미설정',
      env_keys_with_vworld: envKeys,
      vercel_env: process.env.VERCEL_ENV || 'unknown',
    });
  }

  // 삼성동 169 좌표 (COEX)
  const lat = 37.5108, lng = 127.0643;
  const d   = 0.0005;
  const bbox = `${lng - d},${lat - d},${lng + d},${lat + d}`;

  const results = {};

  // (A) WFS — lp_pa_cbnd_bubun
  try {
    const url = new URL('https://api.vworld.kr/req/wfs');
    url.searchParams.set('KEY',          apiKey);
    url.searchParams.set('SERVICE',      'WFS');
    url.searchParams.set('REQUEST',      'GetFeature');
    url.searchParams.set('TYPENAME',     'lp_pa_cbnd_bubun');
    url.searchParams.set('BBOX',         bbox);
    url.searchParams.set('SRSNAME',      'EPSG:4326');
    url.searchParams.set('OUTPUTFORMAT', 'application/json');
    url.searchParams.set('MAXFEATURES',  '3');

    const r = await fetch(url.toString(), {
      headers: VWORLD_HEADERS,
      signal: AbortSignal.timeout(8000),
    });
    const body = await r.text();
    let parsed = null;
    try { parsed = JSON.parse(body); } catch (_) {}
    results.wfs_lp_pa_cbnd = {
      http:             r.status,
      feature_cnt:      parsed?.features?.length ?? null,
      response_headers: Object.fromEntries(r.headers.entries()),
      body_preview:     body.slice(0, 600),
    };
  } catch (e) {
    results.wfs_lp_pa_cbnd = { error: e.message };
  }

  // (B) WFS — lt_c_bldginfo (fallback 레이어)
  try {
    const url = new URL('https://api.vworld.kr/req/wfs');
    url.searchParams.set('KEY',          apiKey);
    url.searchParams.set('SERVICE',      'WFS');
    url.searchParams.set('REQUEST',      'GetFeature');
    url.searchParams.set('TYPENAME',     'lt_c_bldginfo');
    url.searchParams.set('BBOX',         bbox);
    url.searchParams.set('SRSNAME',      'EPSG:4326');
    url.searchParams.set('OUTPUTFORMAT', 'application/json');
    url.searchParams.set('MAXFEATURES',  '3');

    const r = await fetch(url.toString(), {
      headers: VWORLD_HEADERS,
      signal: AbortSignal.timeout(8000),
    });
    const body = await r.text();
    let parsed = null;
    try { parsed = JSON.parse(body); } catch (_) {}
    results.wfs_lt_c_bldginfo = {
      http:             r.status,
      feature_cnt:      parsed?.features?.length ?? null,
      response_headers: Object.fromEntries(r.headers.entries()),
      body_preview:     body.slice(0, 600),
    };
  } catch (e) {
    results.wfs_lt_c_bldginfo = { error: e.message };
  }

  // 서버 발신 IP 확인 (korean IP 여부 재확인)
  try {
    const r = await fetch('https://api.ipify.org?format=json', { signal: AbortSignal.timeout(5000) });
    const d = await r.json();
    results.server_ip = d.ip;
  } catch (e) {
    results.server_ip = `error: ${e.message}`;
  }

  return res.status(200).json({
    region:          process.env.VERCEL_REGION || 'unknown',
    key_prefix:      apiKey.slice(0, 8) + '...',
    request_headers: VWORLD_HEADERS,
    test_coords:     { lat, lng, bbox },
    results,
  });
}
