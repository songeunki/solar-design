// 정식 프록시: Vercel icn1에서 V-World WFS 호출 후 GeoJSON 반환
// GET /api/vworld-polygon?lat=37.5108&lng=127.0643[&bbox_size=0.001][&layer=cbnd|building|both]

export const config = { regions: ['icn1'] };

const VWORLD_BASE = 'https://api.vworld.kr/req/wfs';
const FETCH_HEADERS = {
  'Referer':    'https://solar-design-opal.vercel.app/',
  'Origin':     'https://solar-design-opal.vercel.app',
  'User-Agent': 'Mozilla/5.0 (compatible; SolarDesign-Vercel/1.0)',
};

async function fetchLayer(apiKey, typename, bbox) {
  const url = new URL(VWORLD_BASE);
  url.searchParams.set('KEY',          apiKey);
  url.searchParams.set('SERVICE',      'WFS');
  url.searchParams.set('REQUEST',      'GetFeature');
  url.searchParams.set('TYPENAME',     typename);
  url.searchParams.set('BBOX',         bbox);
  url.searchParams.set('SRSNAME',      'EPSG:4326');
  url.searchParams.set('OUTPUTFORMAT', 'application/json');
  url.searchParams.set('MAXFEATURES',  '10');

  const r = await fetch(url.toString(), {
    headers: FETCH_HEADERS,
    signal:  AbortSignal.timeout(10_000),
  });

  const text = await r.text();
  let data;
  try { data = JSON.parse(text); } catch (_) {
    throw new Error(`V-World non-JSON (HTTP ${r.status}): ${text.slice(0, 200)}`);
  }

  // ServiceException 감지
  if (text.includes('ServiceException')) {
    const match = text.match(/code="([^"]+)">([^<]+)/);
    throw new Error(`V-World ServiceException ${match?.[1] ?? ''}: ${match?.[2] ?? text.slice(0, 100)}`);
  }

  return { features: data.features ?? [] };
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  if (req.method === 'OPTIONS') return res.status(200).end();

  const apiKey = process.env.VWORLD_API_KEY || '';
  if (!apiKey) {
    return res.status(500).json({ success: false, cbnd: null, building: null, error: 'VWORLD_API_KEY 미설정' });
  }

  const lat      = parseFloat(req.query.lat);
  const lng      = parseFloat(req.query.lng);
  const bboxSize = parseFloat(req.query.bbox_size || '0.001');
  const layer    = req.query.layer || 'both';

  if (isNaN(lat) || isNaN(lng)) {
    return res.status(400).json({ success: false, cbnd: null, building: null, error: 'lat, lng 파라미터 필수' });
  }

  const bbox = `${lng - bboxSize},${lat - bboxSize},${lng + bboxSize},${lat + bboxSize}`;

  const wantCbnd     = layer === 'both' || layer === 'cbnd';
  const wantBuilding = layer === 'both' || layer === 'building';

  const [cbndResult, buildingResult] = await Promise.all([
    wantCbnd
      ? fetchLayer(apiKey, 'lp_pa_cbnd_bubun', bbox).catch(e => ({ error: e.message }))
      : Promise.resolve(null),
    wantBuilding
      ? fetchLayer(apiKey, 'lt_c_bldginfo', bbox).catch(e => ({ error: e.message }))
      : Promise.resolve(null),
  ]);

  const cbndOk     = cbndResult && !cbndResult.error;
  const buildingOk = buildingResult && !buildingResult.error;
  const success    = cbndOk || buildingOk;

  const errors = [
    cbndResult?.error     ? `cbnd: ${cbndResult.error}`     : null,
    buildingResult?.error ? `building: ${buildingResult.error}` : null,
  ].filter(Boolean);

  return res.status(success ? 200 : 502).json({
    success,
    cbnd:     cbndOk     ? cbndResult     : null,
    building: buildingOk ? buildingResult : null,
    error:    errors.length ? errors.join(' | ') : null,
  });
}
