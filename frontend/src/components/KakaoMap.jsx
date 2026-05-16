import { useEffect, useRef, useState } from 'react';

/**
 * KakaoMap
 * props:
 *   center     - { lat, lng } 지도 중심 좌표
 *   markerPos  - { lat, lng, label } 마커 위치
 *   onMapClick - (address) => void  — 클릭 → 역지오코딩 → 주소 자동입력
 *   height     - 지도 높이 (기본 340px)
 */
export default function KakaoMap({
  center,
  markerPos,
  onMapClick,
  height = 340,
}) {
  const mapRef = useRef(null);
  const mapObjRef = useRef(null);
  const overlayRef = useRef(null);
  const [mapType, setMapType] = useState('skyview'); // 'roadmap' | 'skyview'

  // 카카오맵 SDK 초기화
  useEffect(() => {
    const initMap = () => {
      if (!mapRef.current || !window.kakao?.maps) return;

      const { kakao } = window;
      const defaultCenter = new kakao.maps.LatLng(
        center?.lat ?? 37.5665,
        center?.lng ?? 126.978
      );

      const map = new kakao.maps.Map(mapRef.current, {
        center: defaultCenter,
        level: 4,
        mapTypeId: kakao.maps.MapTypeId.SKYVIEW,
      });

      mapObjRef.current = map;

      // 클릭 → 역지오코딩
      if (onMapClick) {
        const geocoder = new kakao.maps.services.Geocoder();
        kakao.maps.event.addListener(map, 'click', (mouseEvent) => {
          const latlng = mouseEvent.latLng;
          geocoder.coord2Address(
            latlng.getLng(),
            latlng.getLat(),
            (result, status) => {
              if (status === kakao.maps.services.Status.OK) {
                const addr =
                  result[0]?.road_address?.address_name ||
                  result[0]?.address?.address_name ||
                  '';
                if (addr) onMapClick(addr);
              }
            }
          );
        });
      }
    };

    if (window.kakao?.maps) {
      window.kakao.maps.load(initMap);
    }
  }, []);

  // 지도 타입 전환
  const handleTypeChange = (type) => {
    const map = mapObjRef.current;
    if (!map || !window.kakao?.maps) return;
    const { kakao } = window;
    map.setMapTypeId(
      type === 'skyview'
        ? kakao.maps.MapTypeId.SKYVIEW   // 위성 (하이브리드 없이 순수 위성)
        : kakao.maps.MapTypeId.ROADMAP
    );
    setMapType(type);
  };

  // 마커/오버레이 업데이트 + panTo
  useEffect(() => {
    const map = mapObjRef.current;
    if (!map || !markerPos) return;

    const { kakao } = window;
    if (!kakao?.maps) return;

    const pos = new kakao.maps.LatLng(markerPos.lat, markerPos.lng);

    if (overlayRef.current) overlayRef.current.setMap(null);

    const content = `
      <div style="
        background:#1E6FD9;
        color:white;
        padding:6px 12px;
        border-radius:20px;
        font-size:13px;
        font-weight:600;
        font-family:'Noto Sans KR',sans-serif;
        white-space:nowrap;
        box-shadow:0 4px 16px rgba(30,111,217,0.4);
        position:relative;
      ">
        📍 ${markerPos.label || '분석 위치'}
        <div style="
          position:absolute;
          bottom:-6px;left:50%;transform:translateX(-50%);
          width:0;height:0;
          border-left:6px solid transparent;
          border-right:6px solid transparent;
          border-top:6px solid #1E6FD9;
        "></div>
      </div>
    `;

    const overlay = new kakao.maps.CustomOverlay({ position: pos, content, yAnchor: 1.4 });
    overlay.setMap(map);
    overlayRef.current = overlay;

    map.panTo(pos);
    map.setLevel(3);
  }, [markerPos]);

  // 중심 이동
  useEffect(() => {
    const map = mapObjRef.current;
    if (!map || !center || markerPos) return;
    const { kakao } = window;
    if (!kakao?.maps) return;
    map.panTo(new kakao.maps.LatLng(center.lat, center.lng));
  }, [center]);

  // ── 토글 버튼 스타일 헬퍼 ──────────────────────────────
  const btnStyle = (type) => ({
    padding: '5px 12px',
    fontSize: 12,
    fontWeight: 700,
    fontFamily: "'Noto Sans KR', sans-serif",
    border: 'none',
    cursor: 'pointer',
    transition: 'all 0.15s',
    // 선택된 쪽
    ...(mapType === type
      ? {
          background: type === 'skyview' ? '#1E6FD9' : '#ffffff',
          color:       type === 'skyview' ? '#ffffff' : '#1a202c',
          boxShadow: '0 1px 4px rgba(0,0,0,0.18)',
        }
      : {
          background: 'transparent',
          color: '#718096',
        }),
  });

  return (
    <div
      className="map-wrapper"
      style={height != null ? { height } : undefined}
    >
      {/* 지도 캔버스 */}
      <div ref={mapRef} style={{ width: '100%', height: '100%' }} />

      {/* 지도 타입 토글 — 우상단 */}
      <div className="map-type-toggle">
        <button
          className="map-toggle-btn"
          style={{ ...btnStyle('roadmap'), borderRadius: '7px 0 0 7px' }}
          onClick={() => handleTypeChange('roadmap')}
          title="일반 지도"
        >
          🗺 일반
        </button>
        <div style={{ width: 1, background: 'rgba(0,0,0,0.1)', alignSelf: 'stretch' }} />
        <button
          className="map-toggle-btn"
          style={{ ...btnStyle('skyview'), borderRadius: '0 7px 7px 0' }}
          onClick={() => handleTypeChange('skyview')}
          title="위성 지도"
        >
          🛰 위성
        </button>
      </div>
    </div>
  );
}
