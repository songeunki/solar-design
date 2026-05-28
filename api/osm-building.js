// OSM Overpass 프록시: Vercel icn1에서 Overpass 호출 후 elements 반환
// GET /api/osm-building?lat=37.5&lng=127.04&radius=50
// Render 서버가 overpass-api.de에 직접 접근 불가할 때 사용

export const config = { regions: ['icn1'] };

const OVERPASS_URL = 'https://overpass-api.de/api/interpreter';

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  if (req.method === 'OPTIONS') return res.status(200).end();

  const lat    = parseFloat(req.query.lat);
  const lng    = parseFloat(req.query.lng);
  const radius = parseInt(req.query.radius || '50', 10);

  if (isNaN(lat) || isNaN(lng)) {
    return res.status(400).json({ success: false, error: 'lat, lng 파라미터 필수', elements: [] });
  }

  const query = `[out:json][timeout:25];way["building"](around:${radius},${lat},${lng});out body geom;`;

  try {
    const r = await fetch(OVERPASS_URL, {
      method:  'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body:    `data=${encodeURIComponent(query)}`,
      signal:  AbortSignal.timeout(28_000),
    });
    if (!r.ok) {
      return res.status(502).json({ success: false, error: `Overpass HTTP ${r.status}`, elements: [] });
    }
    const data     = await r.json();
    const elements = data.elements || [];
    return res.status(200).json({ success: true, elements });
  } catch (e) {
    return res.status(502).json({ success: false, error: e.message, elements: [] });
  }
}
