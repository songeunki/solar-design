import { useEffect, useRef, useState } from 'react';

const KAKAO_APP_KEY = '1a26482813f863a4da8896cde91a820e';

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

export default function KakaoMap({
  center,
  markerPos,
  onMapClick,
  height = 340,
  buildingPolygon = null,
}) {
  const mapRef       = useRef(null);
  const mapObjRef    = useRef(null);
  const overlayRef   = useRef(null);
  const polygonRef   = useRef(null);
  const markerPosRef   = useRef(markerPos);
  markerPosRef.current = markerPos;
  const [mapType, setMapType] = useState('skyview');

  // ── 초기화 ──────────────────────────────────────────────────────────────
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

      // SDK가 비동기로 초기화되는 동안 markerPos가 이미 설정된 경우
      // useEffect([markerPos])는 map이 null이라 조기 종료됐으므로 여기서 직접 적용
      const mp = markerPosRef.current;
      if (mp) {
        const pos = new kakao.maps.LatLng(mp.lat, mp.lng);
        if (overlayRef.current) overlayRef.current.setMap(null);
        const content = `<div style="background:#1E6FD9;color:white;padding:6px 12px;border-radius:20px;font-size:13px;font-weight:600;font-family:'Noto Sans KR',sans-serif;white-space:nowrap;box-shadow:0 4px 16px rgba(30,111,217,0.4);position:relative;">
          📍 ${mp.label || '분석 위치'}
          <div style="position:absolute;bottom:-6px;left:50%;transform:translateX(-50%);width:0;height:0;border-left:6px solid transparent;border-right:6px solid transparent;border-top:6px solid #1E6FD9;"></div>
        </div>`;
        const overlay = new kakao.maps.CustomOverlay({ position: pos, content, yAnchor: 1.4 });
        overlay.setMap(map);
        overlayRef.current = overlay;
        map.setCenter(pos);
        map.setLevel(1);
      }

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
    }).catch((e) => console.error(e));
  }, []);

  // ── 지도 타입 전환 ──────────────────────────────────────────────────────
  const handleTypeChange = (type) => {
    const map = mapObjRef.current;
    if (!map || !window.kakao?.maps) return;
    map.setMapTypeId(
      type === 'skyview' ? window.kakao.maps.MapTypeId.HYBRID : window.kakao.maps.MapTypeId.ROADMAP
    );
    setMapType(type);
  };

  // ── 마커 + panTo ────────────────────────────────────────────────────────
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
    map.setLevel(1);
  }, [markerPos]);

  // ── 중심 이동 ────────────────────────────────────────────────────────────
  useEffect(() => {
    const map = mapObjRef.current;
    if (!map || !center || markerPos || !window.kakao?.maps) return;
    map.panTo(new window.kakao.maps.LatLng(center.lat, center.lng));
  }, [center]);

  // ── 건물 윤곽 폴리곤 ─────────────────────────────────────────────────────
  // panel_layout.py에서 azimuth 회전이 roof_polygon 좌표에 이미 반영됨 → 그대로 사용
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
  }, [buildingPolygon]);

  // ── 토글 버튼 스타일 ──────────────────────────────────────────────────────
  const btnStyle = (type) => ({
    padding: '5px 12px', fontSize: 12, fontWeight: 700,
    fontFamily: "'Noto Sans KR', sans-serif", border: 'none', cursor: 'pointer',
    transition: 'all 0.15s',
    ...(mapType === type
      ? { background: type === 'skyview' ? '#1E6FD9' : '#fff', color: type === 'skyview' ? '#fff' : '#1a202c', boxShadow: '0 1px 4px rgba(0,0,0,0.18)' }
      : { background: 'transparent', color: '#718096' }),
  });

  return (
    <div className="map-wrapper" style={height != null ? { height } : undefined}>
      <div ref={mapRef} style={{ width: '100%', height: '100%' }} />
      <div className="map-type-toggle">
        <button className="map-toggle-btn" style={{ ...btnStyle('roadmap'), borderRadius: '7px 0 0 7px' }} onClick={() => handleTypeChange('roadmap')} title="일반 지도">🗺 일반</button>
        <div style={{ width: 1, background: 'rgba(0,0,0,0.1)', alignSelf: 'stretch' }} />
        <button className="map-toggle-btn" style={{ ...btnStyle('skyview'), borderRadius: '0 7px 7px 0' }} onClick={() => handleTypeChange('skyview')} title="위성 지도">🛰 위성</button>
      </div>
    </div>
  );
}
