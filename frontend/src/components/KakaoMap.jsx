import { useEffect, useRef, useState } from 'react';

const KAKAO_APP_KEY = '1a26482813f863a4da8896cde91a820e';
const M_PER_DEG     = 111_320;

let kakaoSDKPromise = null;

function loadKakaoSDK() {
  if (kakaoSDKPromise) return kakaoSDKPromise;
  kakaoSDKPromise = new Promise((resolve, reject) => {
    if (window.kakao?.maps) { resolve(); return; }
    const script = document.createElement('script');
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${KAKAO_APP_KEY}&libraries=services&autoload=false`;
    script.onload = () => window.kakao.maps.load(resolve);
    script.onerror = () => { kakaoSDKPromise = null; reject(new Error('카카오맵 SDK 로드 실패')); };
    document.head.appendChild(script);
  });
  return kakaoSDKPromise;
}

const PANEL_STYLE = {
  active: { strokeColor: '#1E6FD9', fillColor: '#1E6FD9', fillOpacity: 0.5, strokeOpacity: 0.9 },
  shade:  { strokeColor: '#FF8C00', fillColor: '#FF8C00', fillOpacity: 0.5, strokeOpacity: 0.9 },
  north:  { strokeColor: '#718096', fillColor: '#718096', fillOpacity: 0.3, strokeOpacity: 0.6 },
};

const LEGEND = [
  { color: '#1E6FD9', label: '활성 패널' },
  { color: '#FF8C00', label: '그늘 예상' },
  { color: '#718096', label: '북향' },
];

function fitZoomLevel(minLat, maxLat, minLng, maxLng) {
  const midLat   = (minLat + maxLat) / 2;
  const spanLatM = (maxLat - minLat) * M_PER_DEG;
  const spanLngM = (maxLng - minLng) * M_PER_DEG * Math.cos(midLat * Math.PI / 180);
  const spanM    = Math.max(spanLatM, spanLngM) * 1.7;
  if (spanM < 35)  return 1;
  if (spanM < 90)  return 2;
  if (spanM < 220) return 3;
  return 4;
}

export default function KakaoMap({
  center,
  markerPos,
  onMapClick,
  height = 340,
  buildingPolygon = null,
  panels = null,
  panelAzimuth = null,
}) {
  const mapRef        = useRef(null);
  const mapObjRef     = useRef(null);
  const overlayRef    = useRef(null);
  const polygonRef    = useRef(null);
  const panelPolysRef = useRef([]);
  const azOverlayRef  = useRef(null);
  const [mapType,  setMapType]  = useState('skyview');
  const [mapReady, setMapReady] = useState(false); // 지도 초기화 완료 트리거

  // ── 1. 초기화 (지도 생성만, 그리기는 각 useEffect에서) ──────────────────────
  useEffect(() => {
    loadKakaoSDK().then(() => {
      if (!mapRef.current) return;
      const { kakao } = window;
      const map = new kakao.maps.Map(mapRef.current, {
        center: new kakao.maps.LatLng(center?.lat ?? 37.5665, center?.lng ?? 126.978),
        level: 4,
        mapTypeId: kakao.maps.MapTypeId.HYBRID,
      });
      mapObjRef.current = map;

      if (onMapClick) {
        const geo = new kakao.maps.services.Geocoder();
        kakao.maps.event.addListener(map, 'click', (e) => {
          geo.coord2Address(e.latLng.getLng(), e.latLng.getLat(), (res, st) => {
            if (st === kakao.maps.services.Status.OK) {
              const addr = res[0]?.road_address?.address_name || res[0]?.address?.address_name || '';
              if (addr) onMapClick(addr);
            }
          });
        });
      }

      // 모든 그리기 useEffect를 재실행시킴
      setMapReady(true);
    }).catch(console.error);
  }, []);

  // ── 2. 지도 타입 전환 ────────────────────────────────────────────────────────
  const handleTypeChange = (type) => {
    const map = mapObjRef.current;
    if (!map || !window.kakao?.maps) return;
    map.setMapTypeId(
      type === 'skyview' ? window.kakao.maps.MapTypeId.HYBRID : window.kakao.maps.MapTypeId.ROADMAP
    );
    setMapType(type);
  };

  // ── 3. 마커 + panTo (mapReady 포함 → 마운트 시점 데이터도 처리) ─────────────
  useEffect(() => {
    const map = mapObjRef.current;
    if (!map || !markerPos || !window.kakao?.maps) return;
    const { kakao } = window;
    const pos = new kakao.maps.LatLng(markerPos.lat, markerPos.lng);
    if (overlayRef.current) overlayRef.current.setMap(null);
    const content = `<div style="background:#1E6FD9;color:white;padding:6px 12px;border-radius:20px;font-size:13px;font-weight:600;font-family:'Noto Sans KR',sans-serif;white-space:nowrap;box-shadow:0 4px 16px rgba(30,111,217,0.4);position:relative;">
      📍 ${markerPos.label || '분석 위치'}
      <div style="position:absolute;bottom:-6px;left:50%;transform:translateX(-50%);width:0;height:0;border-left:6px solid transparent;border-right:6px solid transparent;border-top:6px solid #1E6FD9;"></div>
    </div>`;
    const overlay = new kakao.maps.CustomOverlay({ position: pos, content, yAnchor: 1.4 });
    overlay.setMap(map);
    overlayRef.current = overlay;
    map.setCenter(pos);
    // panels 있으면 zoom은 panels useEffect가 담당, 없으면 level 1
    if (!panels?.length) map.setLevel(1);
  }, [markerPos, mapReady]); // mapReady 추가 ← 핵심 수정

  // ── 4. 중심 이동 ─────────────────────────────────────────────────────────────
  useEffect(() => {
    const map = mapObjRef.current;
    if (!map || !center || markerPos || !window.kakao?.maps) return;
    map.panTo(new window.kakao.maps.LatLng(center.lat, center.lng));
  }, [center, mapReady]);

  // ── 5. 건물 윤곽 폴리곤 ──────────────────────────────────────────────────────
  useEffect(() => {
    const map = mapObjRef.current;
    if (!map || !window.kakao?.maps) return;
    const { kakao } = window;
    if (polygonRef.current) { polygonRef.current.setMap(null); polygonRef.current = null; }
    if (!buildingPolygon || buildingPolygon.length < 3) return;
    const poly = new kakao.maps.Polygon({
      path: buildingPolygon.map(p => new kakao.maps.LatLng(p.lat, p.lng)),
      strokeWeight: 2, strokeColor: '#FF6B35', strokeOpacity: 0.9,
      fillColor: '#FF6B35', fillOpacity: 0.12,
    });
    poly.setMap(map);
    polygonRef.current = poly;
  }, [buildingPolygon, mapReady]); // mapReady 추가 ← 핵심 수정

  // ── 6. 패널 폴리곤 ──────────────────────────────────────────────────────────
  useEffect(() => {
    const map = mapObjRef.current;
    if (!map || !window.kakao?.maps) return;
    const { kakao } = window;

    panelPolysRef.current.forEach(p => p.setMap(null));
    panelPolysRef.current = [];
    if (azOverlayRef.current) { azOverlayRef.current.setMap(null); azOverlayRef.current = null; }
    if (!panels?.length) return;

    let minLat = Infinity, maxLat = -Infinity;
    let minLng = Infinity, maxLng = -Infinity;

    for (const panel of panels) {
      const st = PANEL_STYLE[panel.status];
      if (!st) continue; // buffer: 표시 안 함
      const path = (panel.corners ?? []).map(c => {
        if (c.lat < minLat) minLat = c.lat;
        if (c.lat > maxLat) maxLat = c.lat;
        if (c.lng < minLng) minLng = c.lng;
        if (c.lng > maxLng) maxLng = c.lng;
        return new kakao.maps.LatLng(c.lat, c.lng);
      });
      if (path.length < 3) continue;
      const poly = new kakao.maps.Polygon({
        path,
        strokeWeight: 1,
        strokeColor:  st.strokeColor,  strokeOpacity: st.strokeOpacity,
        fillColor:    st.fillColor,    fillOpacity:   st.fillOpacity,
      });
      poly.setMap(map);
      panelPolysRef.current.push(poly);
    }

    if (minLat === Infinity) return;

    // 패널 bbox 중심으로 지도 이동 후 줌 (geocoded 주소와 polygon 위치 최대 100m 차이 대응)
    const panelCenterLat = (minLat + maxLat) / 2;
    const panelCenterLng = (minLng + maxLng) / 2;
    map.setCenter(new kakao.maps.LatLng(panelCenterLat, panelCenterLng));
    map.setLevel(fitZoomLevel(minLat, maxLat, minLng, maxLng));

    // 방위각 텍스트
    if (panelAzimuth != null) {
      const content = `<div style="background:rgba(0,0,0,0.65);color:#fff;padding:3px 9px;border-radius:10px;font-size:11px;font-family:'Noto Sans KR',sans-serif;pointer-events:none;white-space:nowrap;">방위 ${panelAzimuth.toFixed(1)}°</div>`;
      const pos = new kakao.maps.LatLng(panelCenterLat, panelCenterLng);
      const ov  = new kakao.maps.CustomOverlay({ position: pos, content, yAnchor: -0.4 });
      ov.setMap(map);
      azOverlayRef.current = ov;
    }

    // polygon을 panels 위에 재렌더 (렌더 순서상 panels가 polygon을 덮어쓰는 문제 방지)
    if (polygonRef.current) {
      polygonRef.current.setMap(null);
      polygonRef.current.setMap(map);
    }
  }, [panels, panelAzimuth, mapReady]); // mapReady 추가 ← 핵심 수정

  // ── 토글 스타일 ──────────────────────────────────────────────────────────────
  const btnStyle = (type) => ({
    padding: '5px 12px', fontSize: 12, fontWeight: 700,
    fontFamily: "'Noto Sans KR', sans-serif", border: 'none', cursor: 'pointer',
    transition: 'all 0.15s',
    ...(mapType === type
      ? { background: type === 'skyview' ? '#1E6FD9' : '#fff', color: type === 'skyview' ? '#fff' : '#1a202c', boxShadow: '0 1px 4px rgba(0,0,0,0.18)' }
      : { background: 'transparent', color: '#718096' }),
  });

  const showLegend = panels?.some(p => p.status !== 'buffer');

  return (
    <div className="map-wrapper" style={{ position: 'relative', ...(height != null ? { height } : {}) }}>
      <div ref={mapRef} style={{ width: '100%', height: '100%' }} />

      {/* 지도 타입 토글 */}
      <div className="map-type-toggle">
        <button className="map-toggle-btn" style={{ ...btnStyle('roadmap'), borderRadius: '7px 0 0 7px' }} onClick={() => handleTypeChange('roadmap')} title="일반 지도">🗺 일반</button>
        <div style={{ width: 1, background: 'rgba(0,0,0,0.1)', alignSelf: 'stretch' }} />
        <button className="map-toggle-btn" style={{ ...btnStyle('skyview'), borderRadius: '0 7px 7px 0' }} onClick={() => handleTypeChange('skyview')} title="위성 지도">🛰 위성</button>
      </div>

      {/* 패널 범례 */}
      {showLegend && (
        <div style={{
          position: 'absolute', top: 8, right: 8, zIndex: 10,
          background: 'rgba(0,0,0,0.68)', color: '#fff',
          borderRadius: 6, padding: '5px 9px', fontSize: 11,
          fontFamily: "'Noto Sans KR', sans-serif",
          display: 'flex', flexDirection: 'column', gap: 3,
          pointerEvents: 'none',
        }}>
          {LEGEND.map(({ color, label }) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <div style={{ width: 12, height: 8, background: color, opacity: 0.9, borderRadius: 1, flexShrink: 0 }} />
              <span>{label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
